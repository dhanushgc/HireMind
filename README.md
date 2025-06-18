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
python database/db_init()
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

ScreenShots of the Application:
![image](https://github.com/user-attachments/assets/8866900a-578e-498f-ae35-d6731f27de3b)
![image](https://github.com/user-attachments/assets/4e50e3c0-4864-4700-9112-e608cd03e4c5)
![image](https://github.com/user-attachments/assets/5e8bd92a-d0ea-4b9a-8cd5-fa8957dad6c5)
![image](https://github.com/user-attachments/assets/c59d8084-94a3-473d-985f-95b40dca35a0)
![image](https://github.com/user-attachments/assets/85015714-fad0-418e-9820-c35911401d55)
![image](https://github.com/user-attachments/assets/a9931398-d15d-4d40-8e75-7be577d7cb05)



## 📈 Future Enhancements

* PDF export for reports
* Admin dashboard for analytics
* OAuth login
* Cloud-based file upload (e.g. S3)


---

## 📄 License

MIT License
© 2025 Dhanush G. Chandrappa
