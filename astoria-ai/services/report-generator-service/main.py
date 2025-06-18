from fastapi import FastAPI
from pydantic import BaseModel
import os
from jinja2 import Template
import datetime
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

# Local DB for scores
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../scoring_cache.db"))
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# External paths to pull candidate and job data
PARSER_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "../document-parser/parser_cache.db"))
AUTH_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "../user-auth-service/user_auth.db"))

class ReportInput(BaseModel):
    candidate_id: str
    job_id: str
    score_report: dict | None = None

@app.post("/report/candidate")
async def generate_report(data: ReportInput):
    # Load score report if not provided
    if data.score_report is None:
        session_key = f"{data.candidate_id}:{data.job_id}"
        cursor.execute("SELECT score_json FROM scoring_results WHERE session_key = ?", (session_key,))
        row = cursor.fetchone()
        if not row:
            return {"error": "No score found in database for given candidate/job."}
        score_report = json.loads(row[0])
    else:
        score_report = data.score_report

   
    candidate_name = f"Candidate {data.candidate_id}"
    job_title = f"Job {data.job_id}"

    try:
        conn_p = sqlite3.connect(PARSER_DB, check_same_thread=False)
        cur_p = conn_p.cursor()
        cur_p.execute("SELECT parsed_resume FROM candidate_job_map WHERE candidate_id = ? AND job_id = ?", (data.candidate_id, data.job_id))
        r = cur_p.fetchone()
        if r:
            parsed = json.loads(r[0])
            candidate_name = parsed.get("full_name", candidate_name)
    except Exception as e:
        print("Failed to resolve candidate name:", e)

    try:
        cur_p.execute("SELECT parsed_json FROM job_posts WHERE id = ?", (data.job_id,))
        r = cur_p.fetchone()
        if r:
            parsed = json.loads(r[0])
            job_title = parsed.get("job_title", job_title)
    except Exception as e:
        print("Failed to resolve job title:", e)

    return {
    "candidate_name": candidate_name,
    "job_title": job_title,
    "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    "report": score_report
    }

@app.get("/health")
def health():
    return {"status": "report-generator live"}
