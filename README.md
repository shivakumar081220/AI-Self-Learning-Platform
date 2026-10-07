# AI Self-Learning Platform

AI-powered adaptive learning platform for the Generative AI track.

## Phase 1 through Phase 7 status

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
- OpenRouter AI provider integration through the OpenAI-compatible SDK
- Provider-error and invalid-output fallback to curated diagnostic questions
- Structured AI-assisted Learning Experience content with curated per-topic fallback
- Context-aware lesson generation using learner goal, level, weak concepts, completed topics, and recent assessments
- Topic progress lifecycle from `in_progress` to `completed`
- Learning page with objectives, explanations, examples, practical application, mistakes, recap, and completion action
- Post-learning MCQ assessment tied to the completed topic
- Deterministic concept scoring, weakness detection, skill updates, and adaptive remediation
- Assessment result UI that makes the changed recommendation visible

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

## Phase 5 OpenRouter AI provider

The existing diagnostic AI service uses OpenRouter through the OpenAI-compatible SDK. Configure these variables in a local, ignored `.env` file:

```text
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=openrouter/free
```

The provider is optional for local startup. Missing keys, provider errors, rate limits, network failures, empty responses, and invalid Pydantic output all fall back to the curated diagnostic question set. The application never returns or logs the provider key.

## Phase 6 Learning Experience

- `GET /api/learners/{learner_id}/learning-path/current` returns the current recommended topic.
- `GET /api/learners/{learner_id}/topics/{topic_id}/content` retrieves personalized lesson content and starts the topic.
- `POST /api/learners/{learner_id}/topics/{topic_id}/content/generate` generates the lesson through the same validated service.
- `POST /api/learners/{learner_id}/topics/{topic_id}/complete` persists completion and advances the path position without changing skill scores.

Learning content is validated with the `LearningContent` Pydantic schema. OpenRouter receives only curated topic metadata and deterministic learner context. Generated content must return the exact requested catalog topic ID and title. Missing keys, provider failures, malformed JSON, invalid schema, and attempted topic injection use curated topic content instead. Only the current recommended topic or a previously completed topic can be opened.

## Phase 7 Assessment and remediation

- `POST /api/learners/{learner_id}/topics/{topic_id}/assessment/generate` creates a topic-specific MCQ assessment after learning is completed.
- `GET /api/learners/{learner_id}/assessments/{assessment_id}` retrieves pending questions or the persisted result.
- `POST /api/learners/{learner_id}/assessments/{assessment_id}/submit` performs deterministic scoring and persists adaptation state.

Assessment answer keys and explanations remain server-side. OpenRouter may generate validated questions, but curated topic-specific MCQs are used when the provider is unavailable or output is invalid. The backend calculates the score and concept results using `<50% = weak`, `50–79% = developing`, and `>=80% = strong`.

Historical skills use the deterministic update formula `new_score = 0.6 * previous_score + 0.4 * latest_assessment_score`; a first observed score uses the latest result directly. Weak concepts create or update open `Weakness` records, while improved concepts resolve active weaknesses. Recommendations are deterministic: weak results remediate, developing results practice, and strong results continue. The current path is updated in place using the Phase 4 engine, so weak learners remain on remediation while strong learners advance.

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

## Submission Overview

### Problem

Most course sequences treat every learner identically. This project builds a Generative AI learning experience that measures a learner, teaches the next useful topic, evaluates understanding, and changes the next action based on evidence.

### Solution

The platform combines a curated Generative AI topic graph, structured OpenRouter generation, SQLite learner state, and deterministic adaptation. A new learner can complete the full journey from the browser without editing code or database records.

### Mandatory MVP features

- Learner profile and Generative AI goal selection
- Diagnostic MCQ assessment
- Concept-level skill analysis
- Personalized prerequisite-aware path
- AI-assisted learning content
- Post-learning topic assessment
- Weak-topic detection
- Adaptive remediation or progression

## Tech Stack

- Frontend: React, Vite, React Router, responsive CSS
- Backend: Python, FastAPI, Pydantic, SQLAlchemy
- Database: SQLite
- AI: OpenRouter through the OpenAI-compatible SDK
- Testing: Pytest and Vite production build

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the data flow and service boundaries. See [docs/AI_DESIGN.md](docs/AI_DESIGN.md) for prompts, validation, fallback behavior, and the deterministic/AI boundary.

## Local development

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --app-dir backend --reload
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

The frontend is normally available at `http://127.0.0.1:5173`; the API is at `http://127.0.0.1:8000`.

## API overview

- `POST /api/learners`: create a learner and goal
- `POST /api/learners/{id}/diagnostic/generate`: generate diagnostic MCQs
- `POST /api/learners/{id}/diagnostic/{assessment_id}/submit`: score diagnostic answers
- `GET /api/learners/{id}/summary`: persisted dashboard state
- `GET|POST /api/learners/{id}/learning-path`: retrieve or generate a path
- `GET /api/learners/{id}/learning-path/current`: retrieve the current topic
- `GET /api/learners/{id}/topics/{topic_id}/content`: load learning content
- `POST /api/learners/{id}/topics/{topic_id}/complete`: complete learning and start assessment in the UI
- `POST /api/learners/{id}/topics/{topic_id}/assessment/generate`: generate topic MCQs
- `GET /api/learners/{id}/assessments/{assessment_id}`: retrieve questions or persisted results
- `POST /api/learners/{id}/assessments/{assessment_id}/submit`: score and adapt

## Adaptive logic

The path engine ranks valid catalog topics using goal relevance, prerequisites, weak concepts, experience level, completed topics, and recent performance. Topic assessments classify concepts as weak, developing, or strong. Weak results keep the topic active for remediation; developing results request focused practice; strong results advance to the next topic.

Skill state is persisted. After the first observation, a topic-assessment skill score uses `0.6 * previous_score + 0.4 * latest_assessment_score`. This means one assessment updates the learner without erasing their history.

## AI versus deterministic logic

AI handles generated questions, explanations, learning content, examples, and alternate teaching material. Deterministic code handles scoring, skill state, weakness detection, prerequisites, path selection, progress, recommendations, authorization, and database updates. Every structured AI response is validated with Pydantic before use.

## Reliability and fallback

The application works without OpenRouter. Missing keys, provider failures, rate limits, network errors, empty responses, or invalid structured output use curated diagnostic questions, topic assessment questions, or curated learning content. Frontend failures use human-readable messages and do not expose stack traces or provider details.

## Demo steps

1. Open the frontend and create a learner profile.
2. Select a Generative AI goal and experience level.
3. Complete the diagnostic and inspect concept-level skill analysis.
4. Open the personalized path and select the current topic.
5. Read the personalized or curated learning content.
6. Mark the topic complete; the topic assessment opens automatically.
7. Submit weak answers to demonstrate remediation, or correct answers to demonstrate progression.
8. Inspect “What changed based on your result?” and the updated path/dashboard.
9. Refresh the result or path page to demonstrate persisted learner state.

## Testing

```powershell
$env:PYTHONPATH = "backend"
python -m pytest backend/tests -q
cd frontend
npm run build
```

All automated AI tests mock OpenRouter. No test makes a real provider request.

## Known limitations and future improvements

The MVP supports one Generative AI track and MCQ assessments. Authentication, conversational tutoring, retrieval over external sources, additional question types, and deployment are future improvements. SQLite startup creation is intentionally lightweight for this challenge; a migration tool would be appropriate for a larger production deployment.
