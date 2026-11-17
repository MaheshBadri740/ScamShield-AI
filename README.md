# ScamShield AI

> **"Verify Every Opportunity. Protect Your Future."**

ScamShield AI is an intelligent career opportunity fraud detection and student protection platform designed to safeguard students, fresh graduates, and job seekers from fraudulent job offers, fake internship postings, credential theft, and predatory recruitment schemes.

---

## 🚀 Overview

Employment scams targeting students and early-career candidates have surged, with bad actors impersonating legitimate organizations, demanding upfront fees for training or equipment, and harvesting sensitive personal or financial information.

**ScamShield AI** brings cutting-edge artificial intelligence to the forefront of student defense:
- **Comprehensive Opportunity Verification**: Instantly inspect job listings, offer letters, email correspondences, and company domains.
- **Student Protection Shield**: Proactive warnings, financial risk score indicators, and guidance on standard recruitment compliance.
- **Scam Connection Detection**: Uncover cross-platform patterns, linked contact numbers, fraudulent domains, and recurring syndicate signatures.
- **AI Investigation Assistant**: Conversational agent powered by Google Gemini to analyze suspicious communication, extract hidden red flags, and provide step-by-step counter-action recommendations.

---

## 🛠️ Tech Stack

- **Frontend**: [Next.js](https://nextjs.org/) (React, TypeScript, Tailwind CSS)
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11, SlowAPI, Pydantic v2)
- **AI Engine**: [Google Gemini API](https://ai.google.dev/) (`google-genai` SDK)
- **Database**: SQLite (Local development) / PostgreSQL (Production deployment via SQLAlchemy)
- **Deployment**: Vercel (Frontend) + Render / Container Runtime (Backend)

---

## 📁 Repository Structure

```text
Scamshield-Ai/
├── .gitignore
├── README.md
├── ARCHITECTURE.md
└── backend/
    ├── .env.example
    ├── Dockerfile
    ├── requirements.txt
    └── app/
        ├── __init__.py
        ├── main.py
        ├── core/
        │   ├── __init__.py
        │   └── config.py
        ├── agents/
        │   └── __init__.py
        ├── models/
        │   └── __init__.py
        ├── routes/
        │   └── __init__.py
        └── services/
            └── __init__.py
```

---

## ⚙️ Quick Start (Backend Scaffold)

### 1. Configuration
Copy the sample environment file in `backend/`:
```bash
cp backend/.env.example backend/.env
```
Provide your Google Gemini API key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=sqlite:///./scamshield.db
ALLOWED_ORIGINS=http://localhost:3000
```

### 2. Backend Setup
Create and activate a virtual environment:
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

Install backend dependencies:
```bash
pip install -r backend/requirements.txt
```

Launch the FastAPI development server:
```bash
uvicorn app.main:app --reload --app-dir backend --port 8000
```

Access API health check:
- `http://localhost:8000/health`
- Interactive Swagger docs: `http://localhost:8000/docs`

---

## 🛡️ License

Distributed under the Apache 2.0 License. See `LICENSE` for more information.
