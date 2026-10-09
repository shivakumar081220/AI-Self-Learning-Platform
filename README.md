# AI Self-Learning Platform

A personalized learning application with eight AI-focused tracks. Learners complete a diagnostic, receive an ordered course, study topic-specific lessons, and use graded assessments to guide revision and progression.

## Learning flow

Learner profile and track → diagnostic assessment → skill analysis → persisted personalized course → ordered modules and lessons → topic assessment → skill and weakness updates → adaptive recommendation.

The course curriculum defines the module sequence. A module contains topics and teaching material; it does not contain a separate learning path.

## Features

- Eight selectable tracks: Python for AI, Machine Learning, Deep Learning, NLP, Generative AI, LLMs, RAG, and AI Agents.
- OpenRouter-backed structured curriculum, diagnostic, lesson, assessment, and tutor generation when configured.
- Validated, persisted curricula and lesson artifacts; matching saved content is reused.
- Curated or deterministic fallbacks for supported AI operations.
- Deterministic objective scoring, skill updates, prerequisite enforcement, progress, authorization, and persistence.
- Seven topic-assessment types: MCQ, conceptual, scenario, code output, coding, debugging, and comparison.
- Authenticated learner profiles, persistent tutor conversations, progress dashboard, and browser voice features.

## Technology

- Frontend: React, Vite, React Router
- Backend: Python, FastAPI, Pydantic, SQLAlchemy
- Database: SQLite by default
- AI provider: OpenRouter through the OpenAI-compatible SDK
- Tests: Pytest and Vite production build

## Local setup

Use Python 3.10+ and Node.js with npm.

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API defaults to `http://127.0.0.1:8000`; health check: `http://127.0.0.1:8000/api/health`.

### Frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Vite prints the frontend URL, normally `http://127.0.0.1:5173`.

## Configuration

Copy `.env.example` to a local `.env`. Do not commit `.env` or credentials.

```text
OPENROUTER_API_KEY=your_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=openrouter/free
JWT_SECRET_KEY=replace_with_a_long_random_local_secret
```

`OPENROUTER_API_KEY` is optional for local fallback operation. Configure a strong `JWT_SECRET_KEY` for authenticated features; the backend does not use an insecure default. Code-output, coding, and debugging assessments also require an isolated external service configured by `CODE_SANDBOX_URL`. Without it, code-bearing submissions fail explicitly; learner code is never executed in FastAPI.

## Tests and build

From the repository root:

```powershell
Set-Location backend
python -m pytest -q
Set-Location ..\frontend
npm run build
```

Tests mock OpenRouter by default. A live provider request is opt-in and may incur provider usage.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — service boundaries, data flow, and persistence
- [AI design](docs/AI_DESIGN.md) — provider context, validation, fallbacks, and deterministic responsibilities
- [AI API flow](docs/AI_API_FLOW.md) — learner actions, routes, and persistence
- [AI call map](docs/AI_CALL_MAP.md) — generation operations and context
- [Assessment architecture](docs/AI_ASSESSMENT_ARCHITECTURE.md) and [assessment types](docs/ASSESSMENT_TYPES.md)
- [AI Tutor architecture](docs/AI_TUTOR_ARCHITECTURE.md)
- [AI latency and cache report](docs/AI_LATENCY_REPORT.md)
- [Persistence audit](docs/PERSISTENCE_AUDIT_REPORT.md)
- [Test reports](docs/test-reports/)

## Security and limitations

Passwords are hashed and authenticated routes enforce learner ownership. API keys remain backend-only. Generated output is schema-validated, but validation does not guarantee factual accuracy. Fallback content is not live AI output. Production deployment should provide managed secrets, a migration strategy, and a securely isolated code sandbox.
