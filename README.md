# HireMind – AI-Powered Interview Agent

**HireMind** is a full-stack AI interview platform that simulates real-time, intelligent interviews based on job descriptions and candidate resumes. It personalizes questions, evaluates answers, and generates structured reports — helping recruiters scale interviews without compromising quality.

---

## 🚀 Features

* ✅ Role-specific, LLM-generated interview questions (technical + behavioral)
* ✅ Real-time, voice-enabled interview experience
* ✅ Adaptive follow-ups based on answer quality
* ✅ Strict skill matching against job description and resume
* ✅ Transparent scoring and recommendation logic
* ✅ Recruiter dashboard with candidate reports
* ✅ Resume + JD parsing and embedding pipeline
* ✅ Scalable microservice backend with persistent vector DB

---

## 🛠️ Tech Stack

### 🧠 Backend (Python + FastAPI)

* FastAPI for all microservices
* OpenAI GPT-4o for interview generation and scoring
* PyMuPDF for PDF parsing
* ChromaDB for vector search
* SQLite for persistent caching
* HTTPX + Jinja2 for integrations

### 🎯 Frontend (React)

* React.js with Tailwind CSS
* Multi-role login (Recruiter, Candidate)
* Voice integration (Web Speech API: TTS + STT)
* Real-time interview Q\&A interface
* Scoring and skill report UI

---

## ⚙️ Architecture Overview

```
└── astoria-ai/                     # Backend monorepo
    ├── services/
    │   ├── document-parser         # Resume, JD, company profile parsers
    │   ├── interview-agent         # Interview session engine
    │   ├── adaptive-engine         # Evaluates answers and follow-ups
    │   ├── scoring-service         # Final scoring & skill match
    │   ├── report-generator        # Candidate report renderer
    │   ├── embedding-service       # ChromaDB vector store API
    │   └── user-auth-service       # Login/signup APIs
    └── database/                   # SQLite DB seeds
├── interview-ui/                  # React frontend
│   └── src/pages/              # UI components
└── requirements.txt               # Backend dependencies
```

---

## 👩‍💻 How It Works

1. **Recruiter uploads:**

   * Job Description (JD PDF)
   * Company Profile (optional)

2. **Candidate uploads:**

   * Resume (PDF)
   * Starts interview

3. **AI interview session:**

   * 2 technical + 2 behavioral questions generated
   * Follow-up questions triggered for vague answers
   * Voice-based Q\&A supported

4. **Scoring engine:**

   * Scores candidate on: Technical, Communication, Leadership, Completeness
   * Strict skill matching from JD vs. resume/interview
   * Verdict: `advance`, `maybe`, `do not advance`

5. **Recruiter dashboard:**

   * View candidate resume, interview status, full AI-generated report

---

## 📦 Installation & Setup

### 1. Clone the repo

```bash
git clone https://github.com/dhanushgc/HireMind.git
cd HireMind
```

### 2. Set up Python backend

```bash
cd astoria-ai
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
```

Create a `.env` file with your OpenAI API key:

```env
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
```

### 3. Run backend microservices

From `astoria-ai/`:

```bash
# Each service runs independently
uvicorn services/document-parser.main:app --port 8001
uvicorn services/interview-agent.main:app --port 8004
uvicorn services/adaptive-engine.main:app --port 8005
uvicorn services/scoring-service.main:app --port 8006
uvicorn services/report-generator-service.main:app --port 8007
uvicorn services/user-auth-service.main:app --port 8003
uvicorn services/embedding-service.main:app --port 8002
```

### 4. Set up frontend

```bash
cd interview-ui
npm install
npm start
```

Your app will run at:

> [http://localhost:3000](http://localhost:3000)

---

## 🔪 Example Use Case

* Upload JD for **Data Analyst**
* Upload resume for **DevOps Engineer**
* System still generates JD-aligned questions
* Scoring engine shows "maybe" or "do not advance" if core skills are missing

---

## 📈 Future Enhancements

* PDF export for reports
* Admin dashboard for analytics
* OAuth login
* Cloud-based file upload (e.g. S3)

---

## 👥 Test Users

### Recruiter

```
Email: recruiter@test.com
Password: recruiter123
```

### Candidate

```
Email: candidate@test.com
Password: candidate123
```

---

## 📄 License

MIT License
© 2025 Dhanush G. Chandrappa
