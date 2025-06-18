import os
import logging
import traceback
import time
import sqlite3
import json
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from openai import OpenAI
import chromadb
import httpx
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("interview_agent.log")
    ]
)
logger = logging.getLogger(__name__)


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
load_dotenv()
openai_client = OpenAI()



# ---- Persistent SQLite for Interview Sessions ----
DB_PATH = os.getenv("INTERVIEW_SESSION_DB", "interview_sessions.db")

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
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
    return conn

db_conn = init_db()
db_cursor = db_conn.cursor()



# ---- Vector DB for context ----
chroma_path = os.getenv("CHROMA_PATH", "../vector-store/chroma_db")
collection_name = os.getenv("CHROMA_COLLECTION_NAME", "interview_vectors")
client = chromadb.PersistentClient(path=chroma_path)
collection = client.get_or_create_collection(collection_name)
logger.info(f"ChromaDB Path: {os.path.abspath(chroma_path)}")
logger.info(f"Collection Name: {collection_name}")

ADAPTIVE_ENGINE_URL = os.getenv("ADAPTIVE_ENGINE_URL", "http://localhost:8005/adaptive/evaluate")



# ==== Pydantic Schemas ====
class AnsweredQuestion(BaseModel):
    question: str
    answer: str
    category: str

class InterviewInput(BaseModel):
    candidate_id: str
    job_id: str
    previous_answers: list[AnsweredQuestion] = []

class AnswerInput(BaseModel):
    candidate_id: str
    job_id: str
    question: str
    answer: str

class SessionQuery(BaseModel):
    candidate_id: str
    job_id: str



# ==== Helper: get current index ====
def get_next_unanswered_index(answers):
    for idx, ans in enumerate(answers):
        if not ans.strip():
            return idx
    return len(answers)  # All answered


# ==== Helper: Append follow-up to session ====
def append_follow_up(session_key, follow_up_question, category="follow_up"):
    db_cursor.execute("SELECT questions, answers, categories FROM sessions WHERE session_key = ?", (session_key,))
    row = db_cursor.fetchone()
    if row:
        questions = json.loads(row[0])
        answers = json.loads(row[1])
        categories = json.loads(row[2])
        questions.append(follow_up_question)
        answers.append("")  # No answer yet
        categories.append(category)
        db_cursor.execute('''
            UPDATE sessions
            SET questions = ?, answers = ?, categories = ?
            WHERE session_key = ?
        ''', (
            json.dumps(questions),
            json.dumps(answers),
            json.dumps(categories),
            session_key
        ))
        db_conn.commit()
        logger.info(f"[FollowUp] Appended follow-up to session {session_key}: {follow_up_question}")



# ==== Endpoint: Generate Questions ====
@app.post("/interview/question")
async def generate_questions(payload: InterviewInput):
    session_key = f"{payload.candidate_id}:{payload.job_id}"
    company_id= await get_single_company_id()
    logger.info(f"[Interview] Generating questions for session {session_key} (company {company_id})")

   # --- Get context chunks from ChromaDB ---
    context_sections = {
    "resume": [],
    "job_post": [],
    "company_profile": []
    }
    for ref_type, ref_id in [("resume", payload.candidate_id), ("job_post", payload.job_id), ("company_profile", company_id)]:
        logger.info(f"[Interview] Querying ChromaDB for type: {ref_type}, id: {ref_id}")
        try:
            results = collection.get(where={"$and": [{"type": ref_type}, {"ref_id": ref_id}]})
            docs = results.get("documents", [])
            context_sections[ref_type].extend(docs)
        except Exception as e:
            logger.error(f"ChromaDB get failed for {ref_type}/{ref_id}: {e}")
    
    parts = []
    if context_sections["resume"]:
        parts.append("### Resume\n" + "\n".join(context_sections["resume"]))
    if context_sections["job_post"]:
        parts.append("### Job Description\n" + "\n".join(context_sections["job_post"]))
    if context_sections["company_profile"]:
        parts.append("### Company Profile\n" + "\n".join(context_sections["company_profile"]))

    context_text = "\n\n".join(parts).strip() if parts else "No context available." 
  
    logger.info(f"Total context size (characters): {len(context_text)}")


    # --- Generate Questions via LLM ---
    prompt = f"""
    You are an expert AI interview agent helping a company conduct first-round automated screening interviews.

    Your task is to generate a set of **4 highly relevant and job-aligned interview questions**:
    - 2 **technical** questions that are strictly based on the job description's required or preferred skills.
    - 2 **behavioral/leadership** questions that assess soft skills aligned with the company's values and responsibilities.

    Use the resume content **only to personalize** the question (e.g., framing it based on the candidate’s projects), **not to decide what skills to test**.

    If the candidate’s resume does not contain relevant projects for a particular required skill, still generate the question **based on the job’s requirement** — do not skip or substitute unrelated topics.

    ---

    ### GUIDELINES:

    - Do **not** infer any skills from the resume that are not mentioned in the job post.
    - Do **not** generate questions based on unrelated experience, even if the candidate has done impressive work in another domain.
    - You may tailor the language, context, or examples to the candidate’s experience **only if it aligns with the job's expected skills**.
    - If there is no relevant experience in the resume for a skill, phrase the question generally — as it would be asked to any candidate for that role.

    ---

    ### INPUT CONTEXT:
    {context_text}

    ---

    ### TECHNICAL QUESTIONS
    Generate 2 technical questions that:
    - Test the **required and preferred skills** in the job post (e.g., tools, platforms, design areas).
    - If a project/work in the resume matches the skill, reference it when framing the question.
    - If the candidate lacks relevant experience, phrase the question in a standard, professional way.

    ---

    ### BEHAVIORAL/LEADERSHIP QUESTIONS
    Generate 2 behavioral questions that:
    - Focus on soft skills and values mentioned in the company profile and job responsibilities, such as collaboration, ownership, adaptability, or leadership.
    - Can be asked based on the responsibilities described in the job, or personalized if the resume provides relevant context.

    ---
    ### OUTPUT FORMAT:
    Return the questions in the following JSON structure:
    {{
    "questions": [
        {{
        "type": "technical",
        "question": "..."
        }},
        ...
        {{
        "type": "leadership",
        "question": "..."
        }}
    ]
    }}
    """
    try:
        result = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You generate highly personalized, realistic interview questions based on resume, job description, and company culture."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        question_json = result.choices[0].message.content.strip()
        parsed = json.loads(question_json)
        questions = parsed.get("questions", [])

        question_list = [q["question"] for q in questions]
        category_list = [q["type"] for q in questions]
        answer_list = [""] * len(question_list)
        logger.info("[Interview] Questions generated.")

    except Exception as e:
        logger.error(f"[Interview] OpenAI question generation failed: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="AI question generation failed.")

    # --- Persist session to SQLite (main questions) ---
    db_cursor.execute('''
        INSERT OR REPLACE INTO sessions (session_key, candidate_id, job_id, questions, answers, categories, context, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        session_key,
        payload.candidate_id,
        payload.job_id,
        json.dumps(question_list),
        json.dumps(answer_list),
        json.dumps(category_list),
        json.dumps(context_text),
        time.time()
    ))
    db_conn.commit()

    return {
        "success": True,
        "questions": questions,
        "questions_total": len(question_list),
        "answered": 0
    }


# ==== Endpoint: Get Next Question ====
@app.post("/interview/next")
async def get_next_question(query: SessionQuery):
    session_key = f"{query.candidate_id}:{query.job_id}"
    logger.info(f"[Next] Next question requested for session {session_key}")

    db_cursor.execute("SELECT questions, answers, categories FROM sessions WHERE session_key = ?", (session_key,))
    row = db_cursor.fetchone()
    if not row:
        logger.warning("[Next] Session not initialized.")
        raise HTTPException(status_code=404, detail="Session not initialized.")

    questions = json.loads(row[0])
    answers = json.loads(row[1])
    categories = json.loads(row[2])

    idx = get_next_unanswered_index(answers)
    if idx >= len(questions):
        logger.info("[Next] Interview complete for session")
        return {
            "message": "Interview complete. All questions answered.",
            "interview_complete": True
        }

    logger.info(f"[Next] Returning question idx={idx}, category={categories[idx]}")
    return {
        "category": categories[idx],
        "question": questions[idx],
        "question_index": idx,
        "type": categories[idx],
        "interview_complete": False
    }



# ==== Endpoint: Submit Answer (append/persist, background follow-up) ====
@app.post("/interview/answer")
async def submit_answer(payload: AnswerInput, background_tasks: BackgroundTasks):
    session_key = f"{payload.candidate_id}:{payload.job_id}"
    logger.info(f"[Answer] Received answer for {session_key} - question: {payload.question}")

    # Find index of question being answered
    db_cursor.execute("SELECT questions, answers, categories, context FROM sessions WHERE session_key = ?", (session_key,))
    row = db_cursor.fetchone()
    if not row:
        logger.warning("[Answer] Session not found for answer submission.")
        raise HTTPException(status_code=404, detail="Session not found. Generate questions first.")

    questions = json.loads(row[0])
    answers = json.loads(row[1])
    categories = json.loads(row[2])
    context_list = json.loads(row[3]) if row[3] else []
    try:
        idx = questions.index(payload.question)
    except ValueError:
        idx = len(answers)
        questions.append(payload.question)
        answers.append("")
        categories.append("follow_up")

    answers[idx] = payload.answer
    db_cursor.execute('''
        UPDATE sessions
        SET answers = ?, questions = ?, categories = ?
        WHERE session_key = ?
    ''', (
        json.dumps(answers),
        json.dumps(questions),
        json.dumps(categories),
        session_key
    ))
    db_conn.commit()

    # --- Background: Score answer, generate follow-up if needed ---
    background_tasks.add_task(
        score_and_maybe_append_followup,
        session_key, payload, questions[idx], answers[idx], categories[idx], context_list
    )

    return {"success": True}



# ==== Background task: call adaptive engine and append follow-up if needed ====
def score_and_maybe_append_followup(session_key, payload, question, answer, category, context_list):
    answer_data = {
        "question": question,
        "answer": answer,
        "category": category,
        "candidate_id": payload.candidate_id,
        "job_id": payload.job_id,
        "context": "\n".join(context_list)
    }
    try:
        logger.info(f"[AdaptiveBG] Sending to Adaptive Engine for scoring: {question}")
        resp = httpx.post(ADAPTIVE_ENGINE_URL, json=answer_data, timeout=30)
        if resp.status_code != 200:
            logger.error(f"[AdaptiveBG] Adaptive Engine error {resp.status_code}: {resp.text}")
            return
        eval_result = resp.json()
        if isinstance(eval_result, dict) and "evaluation" in eval_result:
            evaluation = eval_result["evaluation"]
            if isinstance(evaluation, str):
                try:
                    evaluation = json.loads(evaluation)
                except Exception:
                    pass
            # Only append follow-up if needed and not already answered
            if (isinstance(evaluation, dict)
                and evaluation.get("follow_up")
                and evaluation.get("classification") in ("vague", "incomplete", "off-topic")
                and not already_followed_up(session_key)):
                    append_follow_up(session_key, evaluation["follow_up"])
    

            
    except Exception as e:
        logger.error(f"[AdaptiveBG] Error scoring answer or appending follow-up: {str(e)}")



def already_followed_up(session_key):
    db_cursor.execute("SELECT categories FROM sessions WHERE session_key = ?", (session_key,))
    row = db_cursor.fetchone()
    if not row:
        return False
    categories = json.loads(row[0]) if row[0] else []
    return "follow_up" in categories




@app.get("/health")
def health():
    logger.info("[Health] Health check requested")
    return {"status": "interview-agent live"}


# --- Global Exception Handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}")
    logger.error(f"Request: {request.method} {request.url}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc),
        }
    )

#helper function
async def get_single_company_id() -> str:
    try:
        resp = httpx.get("http://localhost:8001/company_profiles", timeout=10)
        data = resp.json()
        profiles = data.get("company_profiles", [])

        if not profiles:
            raise ValueError("No company profiles found")

        return profiles[0]["company_id"]
    except Exception as e:
        logger.error(f"Failed to fetch company_id: {e}")
        raise HTTPException(status_code=500, detail="Unable to fetch company_id")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
