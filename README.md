# AI Self-Learning Platform

AI-powered adaptive learning platform for the Generative AI track.

## Phase 1 status

This repository currently contains the project foundation:

- React and Vite frontend
- FastAPI backend
- SQLite database configuration
- SQLAlchemy initial learner model
- FastAPI health endpoint
- Basic frontend routing shell

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

## Environment variables

Copy `.env.example` to `.env` when configuring local development. Never commit `.env` or API keys.

## Planned MVP journey

Learner Profile -> AI Goal Selection -> Diagnostic Assessment -> Skill Analysis -> Personalized Learning Path -> AI Learning Content -> Assessment -> Weakness Detection -> Adaptive Remediation or Recommendation.
