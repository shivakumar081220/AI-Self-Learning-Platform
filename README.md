# AI Self-Learning Platform

AI-powered adaptive learning across eight selectable tracks, from Python and machine learning to generative AI and agentic systems.

## Project status

This repository currently contains the project foundation and database catalog:

- React and Vite frontend
- FastAPI backend
- SQLite database configuration
- SQLAlchemy learner, goal, topic, prerequisite, skill, path, progress, assessment, weakness, and recommendation models
- Curated Generative AI topic catalog with prerequisite relationships
- Idempotent topic seeding during FastAPI startup
- FastAPI health endpoint
- Learner profile and AI track/goal-selection API and UI
- OpenRouter-backed, Pydantic-validated diagnostic generation with curated fallback
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
- Secure registration, bcrypt password hashing, JWT login, logout, and session restoration
- Authenticated learner ownership and cross-user data isolation
- AI-generated persisted per-learner curriculum with generated topics and prerequisites
- Eight selectable AI learning tracks with track-specific personalized curricula
- Resume dashboard for course, path, progress, skills, assessments, and recommendations

The legacy curated Generative AI topic catalog contains nine topics, from foundations and prompt engineering through RAG, evaluation, agents, and production systems. Authenticated learners can select from the eight tracks below and receive a personalized curriculum for their selection.

## AI learning tracks

1. Python for AI
2. Machine Learning
3. Deep Learning
4. Natural Language Processing
5. Generative AI
6. Large Language Models
7. Retrieval-Augmented Generation (RAG)
8. AI Agents / Agentic Systems

## Phase 3 API

- `GET /api/goals` returns the supported Generative AI goals.
- `POST /api/learners` creates a learner profile and selected goal.
- `POST /api/learners/{learner_id}/diagnostic/generate` creates a diagnostic MCQ assessment.
- `POST /api/learners/{learner_id}/diagnostic/{assessment_id}/submit` scores answers and stores concept skills.
- `GET /api/learners/{learner_id}/skills` returns strong, developing, weak, and individual concept scores.

Diagnostic questions keep answer keys and concept metadata server-side. OpenRouter-generated output is validated with Pydantic; if the provider is unavailable, the curated catalog-backed question set allows the flow to continue.

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

Authentication also requires a strong local `JWT_SECRET_KEY`. The backend intentionally refuses authenticated operations when it is missing instead of using an insecure default:

```text
JWT_SECRET_KEY=replace_with_a_long_random_local_secret
```

## Security notes and generated curriculum

Unauthenticated users see the landing, login, and registration pages. Authenticated routes require a bearer JWT. Passwords are bcrypt-hashed and never returned. Each account owns its learner profile, generated course, topics, path, progress, skills, assessments, weaknesses, and recommendations. Protected routes verify ownership before returning learner data.

The OpenRouter key is backend-only, `.env` is ignored, and authenticated routes fail closed when the JWT secret is missing. Automated ownership tests verify that one account cannot access another account's learner data.

After onboarding, OpenRouter generates a Pydantic-validated course structure. The backend assigns application-generated topic IDs, persists the course and prerequisite graph, and loads that same course after logout/login. When OpenRouter is unavailable, a deterministic goal-specific fallback is persisted per learner; the old global catalog is not the normal authenticated curriculum source.

## Planned MVP journey

Learner Profile -> Track and Goal Selection -> Personalized Curriculum -> Diagnostic Assessment -> Skill Analysis -> Adaptive Learning Path -> AI Learning Content -> Assessment -> Weakness Detection -> Remediation or Targeted Practice -> AI Tutor -> Progress.

## Submission Overview

### Problem

Most course sequences treat every learner identically. This project builds an AI learning experience that measures a learner, teaches the next useful topic, evaluates understanding, and changes the next action based on evidence.

### Solution

The platform combines eight selectable AI tracks, structured OpenRouter generation, SQLite learner state, and deterministic adaptation. A new learner can complete the full journey from the browser without editing code or database records.

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
uvicorn app.main:app --reload
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
- `POST /api/auth/register`: create an account and return a short-lived JWT
- `POST /api/auth/login`: authenticate and return a JWT
- `GET /api/auth/me`: restore the authenticated account
- `GET /api/tracks`: list the eight supported AI learning tracks
- `GET /api/learners/me`: load the authenticated learner profile
- `PUT /api/learners/me`: safely update the authenticated learner profile
- `POST /api/curriculum/generate`: generate and persist the authenticated learner's course once
- `GET /api/curriculum/current`: load the persisted authenticated course
- `POST /api/learners/{id}/diagnostic/generate`: generate diagnostic MCQs
- `POST /api/learners/{id}/diagnostic/{assessment_id}/submit`: score diagnostic answers
- `GET /api/learners/{id}/diagnostic/{assessment_id}`: reload submitted diagnostic feedback
- `GET /api/learners/{id}/summary`: persisted dashboard state
- `POST /api/learners/{id}/tutor`: ask a question using current topic and learner skill context
- `GET|POST /api/learners/{id}/learning-path`: retrieve or generate a path
- `GET /api/learners/{id}/learning-path/current`: retrieve the current topic
- `GET /api/learners/{id}/topics/{topic_id}/content`: load learning content
- `POST /api/learners/{id}/topics/{topic_id}/complete`: complete learning and start assessment in the UI
- `POST /api/learners/{id}/topics/{topic_id}/assessment/generate`: generate topic MCQs
- `GET /api/learners/{id}/assessments/{assessment_id}`: retrieve questions or persisted results
- `POST /api/learners/{id}/assessments/{assessment_id}/submit`: score and adapt

Submitted diagnostic and topic assessment results include per-question correctness, the correct option, and an explanation. Answer keys are not included in generated or pending assessments. The tutor uses OpenRouter when configured and returns a topic-aware deterministic fallback when the provider is unavailable. Assessment remediation and targeted-practice guidance use AI when available while progression and scoring remain deterministic.

## Adaptive logic

The path engine ranks valid catalog topics using goal relevance, prerequisites, weak concepts, experience level, completed topics, and recent performance. Topic assessments classify concepts as weak, developing, or strong. Weak results keep the topic active for remediation; developing results request focused practice; strong results advance to the next topic.

Skill state is persisted. After the first observation, a topic-assessment skill score uses `0.6 * previous_score + 0.4 * latest_assessment_score`. This means one assessment updates the learner without erasing their history.

## AI versus deterministic logic

AI handles generated questions, explanations, learning content, examples, and alternate teaching material. Deterministic code handles scoring, skill state, weakness detection, prerequisites, path selection, progress, recommendations, authorization, and database updates. Every structured AI response is validated with Pydantic before use.

## Reliability and fallback

The application works without OpenRouter. AI-generated curricula, questions, learning content, tutor replies, and remediation are validated where applicable. Missing keys, provider failures, rate limits, network errors, empty responses, or invalid structured output use deterministic curriculum generation, curated questions/content, or deterministic tutor/remediation guidance as appropriate. Scoring, skill updates, authorization, and path decisions are deterministic regardless of provider availability. Frontend failures use human-readable messages and do not expose stack traces or provider details.

For a credit-consuming provider smoke test, set `RUN_OPENROUTER_LIVE_TEST=1` and run `pytest backend/tests/test_openrouter_live.py -q` with `OPENROUTER_API_KEY` configured. The regular test suite never sends live OpenRouter requests.

## Demo steps

1. Register and log in.
2. Complete the learner profile and select a goal/level.
3. Complete the diagnostic and inspect concept-level skill analysis.
4. Open the generated personalized path and current topic.
5. Read AI content or deterministic fallback content.
6. Mark the topic complete; the topic assessment opens automatically.
7. Submit weak answers to demonstrate remediation, or correct answers to demonstrate progression.
8. Inspect “What changed based on your result?” and the updated path/dashboard.
9. Log out, log in again, and verify the same course and current state resume.

## Testing

```powershell
$env:PYTHONPATH = "backend"
python -m pytest backend/tests -q
cd frontend
npm run build
```

All automated AI tests mock OpenRouter. No test makes a real provider request.

## Known limitations and future improvements

The MVP supports eight AI learning tracks and MCQ assessments. Tutor responses are scoped to supplied learner and topic context; retrieval over external sources, additional question types, refresh-token rotation, and deployment remain future improvements. SQLite startup creation is intentionally lightweight for this challenge; a migration tool would be appropriate for a larger production deployment.
