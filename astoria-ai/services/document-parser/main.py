from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import fitz  # PyMuPDF
import uvicorn
from openai import OpenAI
import os
import sqlite3
import json
import httpx
import logging
import time
import traceback
from dotenv import load_dotenv
import uuid
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('parser_service.log')
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Document Parser Service", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow only internal IP address in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Load environment and initialize OpenAI client
load_dotenv()
client = OpenAI()
EMBEDDING_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8002/embed")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# Startup validation
def validate_startup():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.critical("OPENAI_API_KEY environment variable is not set")
        raise ValueError("OpenAI API key is required")
    logger.info(f"OpenAI API Key configured")
    logger.info(f"Embedding Service URL: {EMBEDDING_URL}")
    logger.info(f"Upload Dir: {UPLOAD_DIR}")
    return True

validate_startup()


# initialize SQLite DB with file_path
def init_database():
    db_path = "parser_cache.db"

    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_posts (
            id TEXT PRIMARY KEY,
            file_path TEXT,
            raw_text TEXT,
            parsed_json TEXT,
            company_id TEXT,
            recruiter_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS company_profiles (
            id TEXT PRIMARY KEY,
            file_path TEXT,
            raw_text TEXT,
            parsed_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS candidate_job_map (
        candidate_id TEXT,
        job_id TEXT,
        file_path TEXT,
        resume_text TEXT,
        parsed_resume TEXT,
        email TEXT,
        name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (candidate_id, job_id)
        )
    ''')
    conn.commit()
    logger.info("Database initialized with file_path support.")
    return conn

conn = init_database()


# Utility: Save uploaded file
async def save_uploaded_file(file: UploadFile, folder: str = UPLOAD_DIR) -> str:
    os.makedirs(folder, exist_ok=True)
    # UUID for file uniqueness and traceability
    file_id = str(uuid.uuid4())
    file_path = os.path.join(folder, f"{file_id}_{file.filename}")
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)
    logger.info(f"Saved uploaded file to {file_path}")
    return file_path, contents



# PDF to text
async def extract_text_from_pdf(contents: bytes) -> str:
    try:
        doc = fitz.open(stream=contents, filetype="pdf")
        if doc.page_count == 0:
            raise ValueError("PDF has no pages")
        text = ""
        for page_num in range(doc.page_count):
            page = doc[page_num]
            text += page.get_text()
        doc.close()
        if not text.strip():
            raise ValueError("No text could be extracted from PDF")
        logger.info(f"Extracted {len(text)} characters from PDF")
        return text.strip()
    except Exception as e:
        logger.error(f"PDF extraction failed: {str(e)}")
        raise ValueError(f"Failed to extract text from PDF: {str(e)}")



# Embedding service call
async def send_to_embedding_service(id: str, chunks: list[str], role: str, source_type: str):
    try:
        filtered_chunks = [chunk.strip() for chunk in chunks if chunk and chunk.strip()]
        if not filtered_chunks:
            logger.warning(f"[Embedding] No valid chunks to embed for {source_type} ID: {id}")
            return {"success": False, "error": "No valid chunks to embed"}
        payload = {
            "type": source_type,
            "id": id,
            "role": role,
            "chunks": filtered_chunks
        }
        logger.info(f"[Embedding] Starting embedding for {source_type} ID: {id} with {len(filtered_chunks)} chunks")
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(EMBEDDING_URL, json=payload)
            logger.info(f"[Embedding] Response status: {response.status_code} for {source_type} ID: {id}")
            if response.status_code == 200:
                result = response.json()
                embedded_ids = result.get("embedded_ids", [])
                error_count = sum(1 for _id in embedded_ids if str(_id).startswith("error:"))
                if error_count > 0:
                    logger.error(f"[Embedding] {error_count}/{len(embedded_ids)} embeddings failed for {source_type} ID: {id}")
                    return {"success": False, "error": f"{error_count} embeddings failed", "details": result}
                else:
                    logger.info(f"[Embedding] All {len(embedded_ids)} embeddings successful for {source_type} ID: {id}")
                    return {"success": True, "embedded_count": len(embedded_ids)}
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"[Embedding] {error_msg} for {source_type} ID: {id}")
                return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"[Embedding] {error_msg}")
        logger.error(f"[Embedding] Traceback: {traceback.format_exc()}")
        return {"success": False, "error": error_msg}



def parse_with_openai(prompt: str, model: str = "gpt-4o", use_json_mode: bool = False) -> Dict[str, Any]:
    try:
        request_params = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are an AI document parser that extracts structured information."},
                {"role": "user", "content": prompt}
            ]
        }
        if use_json_mode:
            request_params["response_format"] = {"type": "json_object"}
        result = client.chat.completions.create(**request_params)
        if not result.choices or not result.choices[0].message.content:
            raise ValueError("Empty response from OpenAI")
        content = result.choices[0].message.content.strip()
        if use_json_mode:
            try:
                parsed_json = json.loads(content)
                return {"success": True, "content": content, "parsed_json": parsed_json}
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed despite JSON mode: {e}")
                return {"success": False, "error": f"Invalid JSON response: {str(e)}", "raw_content": content}
        return {"success": True, "content": content}
    except Exception as e:
        error_msg = f"OpenAI API error: {str(e)}"
        logger.error(f"{error_msg}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {"success": False, "error": error_msg}




@app.post("/parse/resume")
async def parse_resume(
    file: UploadFile = File(...),
    candidate_id: str = Form(...),
    job_id: str = Form(...),
    email: str = Form(...),
    name: str = Form(...),  
    background_tasks: BackgroundTasks = None
) -> Dict:
    logger.info(f"[Resume] Starting parse for candidate: {candidate_id}, job: {job_id}")
    try:
        file_path, contents = await save_uploaded_file(file)
        text = await extract_text_from_pdf(contents)
        prompt = f"""
        Extract the following information from this resume and return as JSON:
        {{
        "full_name": "string",
        "education": [
            {{
            "institution": "string",
            "degree": "string", 
            "year": "string"
            }}
        ],
        "work_experience": [
            {{
            "company": "string",
            "title": "string",
            "duration": "string",
            "responsibilities": "string"
            }}
        ],
        "skills": ["array of strings"],
        "tools": ["array of strings"],
        "projects": [
            {{
            "name": "string",
            "tech_stack": ["array of strings"],
            "description": "string"
            }}
        ]
        }}
        Resume text:
        {text}
        """
        parse_result = parse_with_openai(prompt, model="gpt-4o", use_json_mode=True)
        if not parse_result["success"]:
            logger.error(f"[Resume] Parsing failed for candidate: {candidate_id}")
            raise HTTPException(status_code=500, detail=f"Resume parsing failed: {parse_result['error']}")
        parsed_content = parse_result["content"]
        parsed_json = parse_result.get("parsed_json", {})

        # Save to database
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO candidate_job_map (candidate_id, job_id, file_path, resume_text, parsed_resume, email, name) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (candidate_id, job_id, file_path, text, parsed_content, email, name)
            )
            conn.commit()
            logger.info(f"[Resume] Saved to database for candidate: {candidate_id}")
        except Exception as e:
            logger.error(f"[Resume] Database save failed: {str(e)}")


        # Prepare embedding chunks
        embed_chunks = []
        embedding_result = {"success": False, "error": "No embedding attempted"}
        try:
            if "work_experience" in parsed_json:
                for exp in parsed_json["work_experience"]:
                    responsibilities = exp.get("responsibilities", "")
                    if responsibilities and isinstance(responsibilities, str):
                        embed_chunks.append(responsibilities)
            if "projects" in parsed_json:
                for proj in parsed_json["projects"]:
                    description = proj.get("description", "")
                    if description and isinstance(description, str):
                        embed_chunks.append(description)
            if "skills" in parsed_json:
                skills = parsed_json["skills"]
                if isinstance(skills, list):
                    embed_chunks.extend([skill for skill in skills if skill and isinstance(skill, str)])
                elif isinstance(skills, str):
                    embed_chunks.append(skills)
            logger.info(f"[Resume] Prepared {len(embed_chunks)} chunks for embedding")
            if embed_chunks:
                embedding_result = await send_to_embedding_service(candidate_id, embed_chunks, "", "resume")
            else:
                logger.warning(f"[Resume] No valid chunks found for embedding")
        except Exception as e:
            logger.error(f"[Resume] Embedding preparation failed: {str(e)}")
            embedding_result = {"success": False, "error": f"Embedding failed: {str(e)}"}

        response = {
            "success": True,
            "candidate_id": candidate_id,
            "job_id": job_id,
            "file_path": file_path,
            "raw_text": text[:500] + "..." if len(text) > 500 else text,
            "parsed_resume": parsed_json,
            "embedding_result": embedding_result,
            "text_length": len(text),
            "chunks_prepared": len(embed_chunks)
        }
        logger.info(f"[Resume] Successfully processed candidate: {candidate_id}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Resume parsing failed: {str(e)}"
        logger.error(f"[Resume] {error_msg}")
        logger.error(f"[Resume] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)



@app.post("/parse/job_post")
async def parse_job_post(
    file: UploadFile = File(...),
    job_id: str = Form(...),
    company_id: str = Form(...),
    recruiter_id: str = Form(...),
    background_tasks: BackgroundTasks = None
    ) -> Dict:
    logger.info(f"[Job Post] Starting parse for job: {job_id}")
    try:
        file_path, contents = await save_uploaded_file(file)
        text = await extract_text_from_pdf(contents)
        prompt = f"""
        Extract the following information from this job posting and return as JSON:
        {{
        "job_title": "string",
        "employment_type": "string",
        "location": "string",
        "required_skills": ["array of strings"],
        "preferred_skills": ["array of strings"],
        "job_description": "string",
        "key_responsibilities": "string"
        }}
        Job posting text:
        {text}
        """
        parse_result = parse_with_openai(prompt, model="gpt-4o", use_json_mode=True)
        if not parse_result["success"]:
            logger.error(f"[Job Post] Parsing failed for job: {job_id}")
            raise HTTPException(status_code=500, detail=f"Job post parsing failed: {parse_result['error']}")
        parsed_content = parse_result["content"]
        parsed_json = parse_result.get("parsed_json", {})

        # Save to database
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO job_posts (id, file_path, raw_text, parsed_json, company_id, recruiter_id) VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, file_path, text, parsed_content, company_id, recruiter_id)
            )
            conn.commit()
            logger.info(f"[Job Post] Saved to database for job: {job_id}")
        except Exception as e:
            logger.error(f"[Job Post] Database save failed: {str(e)}")

        # Prepare embedding chunks
        embed_chunks = []
        embedding_result = {"success": False, "error": "No embedding attempted"}
        try:
            job_desc = parsed_json.get("job_description", "")
            if job_desc and isinstance(job_desc, str):
                embed_chunks.append(job_desc)
            key_resp = parsed_json.get("key_responsibilities", "")
            if key_resp and isinstance(key_resp, str):
                embed_chunks.append(key_resp)
            logger.info(f"[Job Post] Prepared {len(embed_chunks)} chunks for embedding")
            if embed_chunks:
                embedding_result = await send_to_embedding_service(job_id, embed_chunks, "", "job_post")
            else:
                logger.warning(f"[Job Post] No valid chunks found for embedding")
        except Exception as e:
            logger.error(f"[Job Post] Embedding preparation failed: {str(e)}")
            embedding_result = {"success": False, "error": f"Embedding failed: {str(e)}"}

        response = {
            "success": True,
            "job_id": job_id,
            "file_path": file_path,
            "raw_text": text[:500] + "..." if len(text) > 500 else text,
            "parsed_job_post": parsed_json,
            "embedding_result": embedding_result,
            "text_length": len(text),
            "chunks_prepared": len(embed_chunks)
        }
        logger.info(f"[Job Post] Successfully processed job: {job_id}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Job post parsing failed: {str(e)}"
        logger.error(f"[Job Post] {error_msg}")
        logger.error(f"[Job Post] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)



@app.post("/parse/company_profile")
async def parse_company_profile(
    file: UploadFile = File(...),
    company_id: str = Form(...),
    background_tasks: BackgroundTasks = None
    ) -> Dict:
    logger.info(f"[Company] Starting parse for company: {company_id}")
    try:
        file_path, contents = await save_uploaded_file(file)
        text = await extract_text_from_pdf(contents)
        prompt = f"""
        Extract the following information from this company profile and return as JSON:
        {{
        "company_name": "string",
        "industry": "string",
        "mission": "string",
        "vision": "string",
        "core_values": ["array of strings"],
        "culture_summary": "string"
        }}
        Company profile text:
        {text}
        """
        parse_result = parse_with_openai(prompt, model="gpt-4o", use_json_mode=True)
        if not parse_result["success"]:
            logger.error(f"[Company] Parsing failed for company: {company_id}")
            raise HTTPException(status_code=500, detail=f"Company profile parsing failed: {parse_result['error']}")
        parsed_content = parse_result["content"]
        parsed_json = parse_result.get("parsed_json", {})

        # Save to database
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO company_profiles (id, file_path, raw_text, parsed_json) VALUES (?, ?, ?, ?)",
                (company_id, file_path, text, parsed_content)
            )
            conn.commit()
            logger.info(f"[Company] Saved to database for company: {company_id}")
        except Exception as e:
            logger.error(f"[Company] Database save failed: {str(e)}")

        # Prepare embedding chunks
        embed_chunks = []
        embedding_result = {"success": False, "error": "No embedding attempted"}
        try:
            mission = parsed_json.get("mission", "")
            if mission and isinstance(mission, str):
                embed_chunks.append(mission)
            vision = parsed_json.get("vision", "")
            if vision and isinstance(vision, str):
                embed_chunks.append(vision)
            core_values = parsed_json.get("core_values", [])
            if core_values and isinstance(core_values, list):
                core_values_text = " ".join([str(val) for val in core_values if val])
                if core_values_text.strip():
                    embed_chunks.append(core_values_text)
            culture_summary = parsed_json.get("culture_summary", "")
            if culture_summary and isinstance(culture_summary, str):
                embed_chunks.append(culture_summary)
            logger.info(f"[Company] Prepared {len(embed_chunks)} chunks for embedding")
            if embed_chunks:
                embedding_result = await send_to_embedding_service(company_id, embed_chunks, "", "company_profile")
            else:
                logger.warning(f"[Company] No valid chunks found for embedding")
        except Exception as e:
            logger.error(f"[Company] Embedding preparation failed: {str(e)}")
            embedding_result = {"success": False, "error": f"Embedding failed: {str(e)}"}

        response = {
            "success": True,
            "company_id": company_id,
            "file_path": file_path,
            "raw_text": text[:500] + "..." if len(text) > 500 else text,
            "parsed_company_profile": parsed_json,
            "embedding_result": embedding_result,
            "text_length": len(text),
            "chunks_prepared": len(embed_chunks)
        }
        logger.info(f"[Company] Successfully processed company: {company_id}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Company profile parsing failed: {str(e)}"
        logger.error(f"[Company] {error_msg}")
        logger.error(f"[Company] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_msg)



@app.get("/jobs")
def get_jobs(recruiter_id: Optional[str] = Query(None)):
    cursor = conn.cursor()
    if recruiter_id:
        cursor.execute(
            "SELECT id, file_path, parsed_json, created_at FROM job_posts WHERE recruiter_id = ? ORDER BY created_at DESC",
            (recruiter_id,)
        )
    else:
        cursor.execute(
            "SELECT id, file_path, parsed_json, created_at FROM job_posts ORDER BY created_at DESC"
        )
    rows = cursor.fetchall()
    jobs = []
    for r in rows:
        # try to extract job title if present in parsed_json
        title = ""
        try:
            j = json.loads(r[2]) if r[2] else {}
            title = j.get("job_title") or ""
        except Exception:
            title = ""
        jobs.append({
            "job_id": r[0],
            "file_path": r[1],
            "title": title,
            "created_at": r[3]
        })
    return {"jobs": jobs}



# --- GET Company Profile---
@app.get("/company_profiles")
def get_company_profiles():
    cursor = conn.cursor()
    cursor.execute("SELECT id, file_path, parsed_json, created_at FROM company_profiles ORDER BY created_at DESC")
    rows = cursor.fetchall()
    profiles = []
    for r in rows:
        # try to extract company name if present
        company_name = ""
        try:
            j = json.loads(r[2]) if r[2] else {}
            company_name = j.get("company_name") or ""
        except Exception:
            company_name = ""
        profiles.append({
            "company_id": r[0],
            "file_path": r[1],
            "company_name": company_name,
            "created_at": r[3]
        })
    return {"company_profiles": profiles}



@app.get("/candidates_for_job")
def candidates_for_job(job_id: str):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT candidate_id, file_path, parsed_resume, email, name, created_at FROM candidate_job_map WHERE job_id=?",
        (job_id,)
    )
    rows = cursor.fetchall()
    candidates = []
    for r in rows:
        candidate_id = r[0]
        email = r[3] or ""
        name = r[4] or ""
        try:
            parsed = json.loads(r[2]) if r[2] else {}
            full_name = parsed.get("full_name", "") or name
        except Exception:
            full_name = name
        candidates.append({
            "candidate_id": candidate_id,
            "candidate_name": full_name,
            "candidate_email": email,
            "resume_file_path": r[1],
            "applied_at": r[5]
        })
    return {"candidates": candidates}



@app.get("/applications_for_candidate")
def applications_for_candidate(candidate_id: str):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT job_id, file_path, created_at, parsed_resume FROM candidate_job_map WHERE candidate_id=?",
        (candidate_id,)
    )
    rows = cursor.fetchall()
    applications = []
    for r in rows:
        # parse job_title from job_posts
        try:
            job_id = r[0]
            cursor.execute("SELECT parsed_json FROM job_posts WHERE id=?", (job_id,))
            job_row = cursor.fetchone()
            job_title = ""
            if job_row:
                job_json = json.loads(job_row[0]) if job_row[0] else {}
                job_title = job_json.get("job_title", "")
        except Exception:
            job_title = ""
        applications.append({
            "job_id": job_id,
            "job_title": job_title,
            "resume_file_path": r[1],
            "applied_at": r[2]
        })
    return {"applications": applications}




@app.get("/health")
def health():
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"error: {str(e)}"
    api_key_status = "configured" if os.getenv("OPENAI_API_KEY") else "missing"
    return {
        "status": "healthy",
        "service": "parser-service",
        "version": "1.1.0",
        "database": db_status,
        "openai_api_key": api_key_status,
        "embedding_service_url": EMBEDDING_URL,
        "upload_dir": UPLOAD_DIR,
        "timestamp": time.time()
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}")
    logger.error(f"Request: {request.method} {request.url}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": time.time()
        }
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
