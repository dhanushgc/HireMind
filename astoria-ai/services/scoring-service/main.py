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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
client = OpenAI()

# --- Connect to the persistent interview session DB from interview-agent
INTERVIEW_DB = os.getenv("INTERVIEW_SESSION_DB", "../interview-agent/interview_sessions.db")
interview_conn = sqlite3.connect(INTERVIEW_DB, check_same_thread=False)
interview_cursor = interview_conn.cursor()

# --- Own scoring results DB
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../scoring_cache.db"))
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS scoring_results (
        session_key TEXT PRIMARY KEY,
        candidate_id TEXT,
        job_id TEXT,
        score_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

class ScoreInput(BaseModel):
    candidate_id: str
    job_id: str

@app.post("/score/candidate")
async def score_candidate(payload: ScoreInput):
    session_key = f"{payload.candidate_id}:{payload.job_id}"
    interview_cursor.execute("SELECT * FROM sessions WHERE session_key = ?", (session_key,))
    row = interview_cursor.fetchone()
    if not row:
        return {"error": "No interview data found for this candidate/job."}

    questions = json.loads(row[3])
    answers = json.loads(row[4])
    categories = json.loads(row[5])
    context = row[6]

    qa_pairs = [f"Q: {q}\nA: {a}" for q, a in zip(questions, answers)]
    qa_text = "\n\n".join(qa_pairs)

    json_example = """
        {
        "technical": 8,
        "communication": 9,
        "leadership": 7,
        "completeness": 8,
        "summary": "Candidate demonstrates solid technical understanding and communicates ideas clearly.",
        "verdict": "advance",
        "skill_match_graph": [
            { "skill": "REST APIs", "job_source": "required", "matched": true },
            { "skill": "Kubernetes", "job_source": "preferred", "matched": false }
        ]
        }
        """
    prompt = f"""
    You are an AI-powered candidate evaluation assistant designed to help recruiters make high-confidence decisions after a structured interview.

    You are evaluating whether the candidate is a strong fit **strictly based on the job description, company expectations, the candidate's resume, and their answers during the interview.**

    ---

    ## Evaluation Guidelines:

    You are provided with:
    - A job description that includes required, preferred, and responsibility-based skills.
    - A parsed resume (with structured skill and project data).
    - A company profile (with cultural and behavioral expectations).
    - An interview transcript — which is a sequence of question-answer pairs.

    ---

    ### 1. Scoring the Candidate

    Evaluate the candidate across 4 categories. Each score must be between **1 and 10**, and must be supported by actual evidence from the resume or interview transcript.

    - `"technical"`: To what extent did the candidate demonstrate job-relevant technical skills, tools, and methods that were explicitly listed in the job description?
    - `"communication"`: Was the candidate’s language clear, structured, and easy to follow? Did they organize their thoughts effectively?
    - `"leadership"`: Did the candidate show evidence of leadership, ownership, collaboration, or initiative — either in resume projects or behavioral interview responses?
    - `"completeness"`: Did the candidate actually answer each question in depth? If the response simply restated the question or lacked detail, score this category lower.

    **Important:**  
    - Review each answer **in context of the question** it was responding to.  
    - Do not give credit for answers that are vague, incomplete, or off-topic.  
    - Do not award points based on resume alone — focus on whether key signals are present in interview responses.

    ---

    ### 2. Summary (Output: `"summary"`)

    Write a 2–3 sentence summary that directly reflects the candidate’s **alignment to the job requirements**.  
    Mention specific strengths or red flags.  
    Avoid generic filler like "seems capable" or "has potential" — be specific and evidence-based.

    ---

    ### 3. Verdict (Output: `"verdict"`)

    Choose one of:
    - `"advance"` — Candidate demonstrates strong alignment with most or all key job criteria.
    - `"maybe"` — Candidate shows partial or inconsistent alignment; could be reconsidered under flexible criteria.
    - `"do not advance"` — Candidate clearly lacks critical skills or traits based on resume and interview performance.

    ---

    ### 4. Skill Match Graph (Output: `"skill_match_graph"`)

    Match each required or preferred skill in the job description against the resume and the candidate's interview responses.

    Instructions:
    - Only mark `"matched": true` if the skill is mentioned directly (or very clearly implied) in the **resume** or the **candidate’s interview answers**.
    - **Do not infer** based on job title, general domain experience, or common role assumptions.
    - Skill match should be **case-insensitive**, but close variations are acceptable (e.g., `"Java Spring"` → `"Spring Boot"`).
    - Do not include skills in the output that are **not present in the job description**.

    ---

    ### Output Format:
    Return a single JSON object like this:
    {json_example}

    ---

    ### Interview Context:
    {context}

    ---

    ### Interview Transcript:
    {qa_text}
    """
    
    try:
        result = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a structured scoring bot."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        score_report_json = result.choices[0].message.content.strip()
        score_report = json.loads(score_report_json)

        cursor.execute("REPLACE INTO scoring_results (session_key, candidate_id, job_id, score_json) VALUES (?, ?, ?, ?)",
                       (session_key, payload.candidate_id, payload.job_id, json.dumps(score_report)))
        conn.commit()

        return {"score_report": score_report}
    except Exception as e:
        return {"error": str(e)}


@app.get("/score/candidate")
def get_score(candidate_id: str, job_id: str):
    session_key = f"{candidate_id}:{job_id}"
    cursor.execute("SELECT score_json FROM scoring_results WHERE session_key = ?", (session_key,))
    row = cursor.fetchone()
    if not row:
        return {"error": "Score report not found."}
    return {"score_report": json.loads(row[0])}


@app.get("/health")
def health():
    return {"status": "scoring-service live"}
