from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
import os
import sqlite3
import json
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware


load_dotenv()
app = FastAPI()
client = OpenAI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], #specify the exact internal IP in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== Persistent Storage Setup ==========
conn = sqlite3.connect("scoring_cache.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS interview_sessions (
        session_key TEXT PRIMARY KEY,
        candidate_id TEXT,
        job_id TEXT,
        questions TEXT,
        answers TEXT,
        categories TEXT,
        context TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

# ========== Input/Output Schemas ==========
class EvalInput(BaseModel):
    question: str
    answer: str
    category: str 
    candidate_id: str
    job_id: str
    context: str

@app.post("/adaptive/evaluate")
async def evaluate_response(payload: EvalInput):
    prompt = f"""
    You are a human-like AI interviewer evaluating a candidate's response.

    ## Task:
    1. Read the question and the candidate's answer carefully.
    2. Classify the quality of the answer as one of:
    - "strong"
    - "vague"
    - "incomplete"
    - "off-topic"
    3. Only suggest a **single follow-up** if the answer:
    - Misses key details relevant to the question
    - Is clearly weak or off-target

    4. **Do NOT suggest a follow-up**:
    - If the answer is brief but acceptable
    - If a follow-up would not add meaningful insight
    - If you've already followed up once before (assume 1 follow-up max)

    ## Output Format (JSON):
    {{
    "classification": "strong" | "vague" | "incomplete" | "off-topic",
    "follow_up": "..."  // optional, leave blank if not needed
    }}

    ## Context:
    - Question: {payload.question}
    - Answer: {payload.answer}
    - Category: {payload.category}
    """

    try:
        result = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You classify and generate follow-ups."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"} 
        )
        evaluation = result.choices[0].message.content.strip()
        evaluation_dict = json.loads(evaluation)

        
        session_key = f"{payload.candidate_id}:{payload.job_id}"
        cursor.execute("SELECT * FROM interview_sessions WHERE session_key = ?", (session_key,))
        existing = cursor.fetchone()

        question_list = [payload.question]
        answer_list = [payload.answer]
        category_list = [payload.category]

        if existing:
            existing_questions = json.loads(existing[3])
            existing_answers = json.loads(existing[4])
            existing_categories = json.loads(existing[5])

            existing_questions.append(payload.question)
            existing_answers.append(payload.answer)
            existing_categories.append(payload.category)

            cursor.execute('''
                UPDATE interview_sessions
                SET questions = ?, answers = ?, categories = ?, context = ?
                WHERE session_key = ?
            ''', (
                json.dumps(existing_questions),
                json.dumps(existing_answers),
                json.dumps(existing_categories),
                payload.context,
                session_key
            ))
        else:
            cursor.execute('''
                INSERT INTO interview_sessions (session_key, candidate_id, job_id, questions, answers, categories, context)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_key,
                payload.candidate_id,
                payload.job_id,
                json.dumps(question_list),
                json.dumps(answer_list),
                json.dumps(category_list),
                payload.context
            ))
        conn.commit()

        return {"evaluation": evaluation_dict}
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
def health():
    return {"status": "adaptive-engine live"}
