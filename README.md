# AI Self-Learning Platform

AI-powered adaptive learning platform for the Generative AI track.

## Phase 1 through Phase 4 status

This repository currently contains the project foundation and database catalog:

- React and Vite frontend
- FastAPI backend
- SQLite database configuration
- SQLAlchemy learner, goal, topic, prerequisite, skill, path, progress, assessment, weakness, and recommendation models
- Curated Generative AI topic catalog with prerequisite relationships
- Idempotent topic seeding during FastAPI startup
- FastAPI health endpoint
- Learner profile and Generative AI goal-selection API and UI
- OpenAI-backed, Pydantic-validated diagnostic generation with curated fallback
- Deterministic MCQ scoring and concept-level skill analysis
- SQLite persistence for diagnostic attempts and skill scores
- Responsive profile, diagnostic, and analysis screens
- Deterministic prerequisite-aware personalized learning-path engine
- Learning-path persistence, regeneration, current-topic tracking, and rationale
- Responsive Learning Path screen with progress and prerequisite visibility

The catalog currently contains nine Generative AI topics, from foundations and prompt engineering through RAG, evaluation, agents, and production systems.

## Phase 3 API

- `GET /api/goals` returns the supported Generative AI goals.
- `POST /api/learners` creates a learner profile and selected goal.
- `POST /api/learners/{learner_id}/diagnostic/generate` creates a diagnostic MCQ assessment.
- `POST /api/learners/{learner_id}/diagnostic/{assessment_id}/submit` scores answers and stores concept skills.
- `GET /api/learners/{learner_id}/skills` returns strong, developing, weak, and individual concept scores.

Diagnostic questions keep answer keys and concept metadata server-side. OpenAI-generated output is validated with Pydantic; if the API is unavailable, the curated catalog-backed question set allows the flow to continue.

## Phase 4 adaptive path

- `GET /api/learners/{learner_id}/learning-path` returns the persisted current path.
- `POST /api/learners/{learner_id}/learning-path/generate` creates a path from current learner state.
- `POST /api/learners/{learner_id}/learning-path/regenerate` recalculates the path while preserving the current topic when possible.

The path engine uses learner goal, experience level, concept scores, weak concepts, completed topics, prerequisite relationships, and recent topic assessment scores. It ranks only valid catalog topics, enforces prerequisite order, skips mastered topics from new recommendations, and stores a reason for every selected topic. No LLM is responsible for topic selection.

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
