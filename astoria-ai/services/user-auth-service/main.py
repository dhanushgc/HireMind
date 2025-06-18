from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, EmailStr
import sqlite3
import os
from passlib.hash import bcrypt
import datetime
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../user_auth.db"))
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

class RecruiterSignup(BaseModel):
    email: EmailStr
    password: str
    name: str = ""
    company_name: str = ""

class CandidateSignup(BaseModel):
    email: EmailStr
    password: str
    name: str = ""

class UserLogin(BaseModel):
    email: EmailStr
    password: str


# --- Recruiter Signup ---
@app.post("/auth/recruiter/signup")
def recruiter_signup(data: RecruiterSignup):
    hashed = bcrypt.hash(data.password)
    try:
        cursor.execute('''
        INSERT INTO recruiters (email, password_hash, name, company_name)
        VALUES (?, ?, ?, ?)''',
        (data.email, hashed, data.name, data.company_name))
        conn.commit()
        return {"success": True, "message": "Recruiter created"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email already exists.")


# --- Candidate Signup ---
@app.post("/auth/candidate/signup")
def candidate_signup(data: CandidateSignup):
    hashed = bcrypt.hash(data.password)
    try:
        cursor.execute('''
        INSERT INTO candidates (email, password_hash, name)
        VALUES (?, ?, ?)''',
        (data.email, hashed, data.name))
        conn.commit()
        return {"success": True, "message": "Candidate created"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email already exists.")


# --- Recruiter Login ---
@app.post("/auth/recruiter/login")
def recruiter_login(data: UserLogin):
    cursor.execute('SELECT recruiter_id, password_hash, name, company_name FROM recruiters WHERE email = ?', (data.email,))
    row = cursor.fetchone()
    if not row or not bcrypt.verify(data.password, row[1]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return {
        "success": True,
        "recruiter_id": row[0],
        "email": data.email,
        "name": row[2],
        "company_name": row[3]
    }


# --- Candidate Login ---
@app.post("/auth/candidate/login")
def candidate_login(data: UserLogin):
    cursor.execute('SELECT candidate_id, password_hash, name FROM candidates WHERE email = ?', (data.email,))
    row = cursor.fetchone()
    if not row or not bcrypt.verify(data.password, row[1]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return {
        "success": True,
        "candidate_id": row[0],
        "email": data.email,
        "name": row[2]
    }


@app.get("/health")
def health():
    return {"status": "user-auth-service live"}
