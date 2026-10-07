# AI Self-Learning Platform

AI-powered adaptive learning platform for the Generative AI track.

## Phase 1 and Phase 2 status

This repository currently contains the project foundation and database catalog:

- React and Vite frontend
- FastAPI backend
- SQLite database configuration
- SQLAlchemy learner, goal, topic, prerequisite, skill, path, progress, assessment, weakness, and recommendation models
- Curated Generative AI topic catalog with prerequisite relationships
- Idempotent topic seeding during FastAPI startup
- FastAPI health endpoint
- Basic frontend routing shell

The catalog currently contains nine Generative AI topics, from foundations and prompt engineering through RAG, evaluation, agents, and production systems.

## Local setup

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The backend runs at `http://127.0.0.1:8000`.

Health check: `http://127.0.0.1:8000/api/health`

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

The frontend runs at the URL printed by Vite, normally `http://127.0.0.1:5173`.

### Backend tests

```powershell
$env:PYTHONPATH = "backend"
python -m pytest backend/tests -q
```

## Environment variables

Copy `.env.example` to `.env` when configuring local development. Never commit `.env` or API keys.

## Planned MVP journey

Learner Profile -> AI Goal Selection -> Diagnostic Assessment -> Skill Analysis -> Personalized Learning Path -> AI Learning Content -> Assessment -> Weakness Detection -> Adaptive Remediation or Recommendation.
