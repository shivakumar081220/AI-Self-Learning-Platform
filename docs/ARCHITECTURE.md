# Architecture

## System flow

```text
Public React + Vite
    |
    | JWT bearer REST/JSON
    v
FastAPI auth and protected routers
    |
    +--> User -> LearnerProfile -> GeneratedCourse -> GeneratedTopic
    |        |
    |        +--> Deterministic adaptive engine
    |        |
    |        +--> SQLAlchemy / SQLite learner state
    |
    +--> OpenRouter (OpenAI-compatible SDK)
             |
             +--> Pydantic validation
             |
             +--> Curated fallback when unavailable or invalid
```

## Frontend

Public routes provide landing, registration, and login. Authenticated routes are guarded by the React auth context and redirect unauthenticated users to login. The short-lived access token is restored on refresh and removed on logout.

The React application presents one learner journey:

1. Profile and Generative AI goal
2. Diagnostic MCQs
3. Skill analysis
4. Personalized path
5. Learning Experience
6. Topic assessment
7. Adaptive result and remediation

Routes call the FastAPI API through `frontend/src/api/client.js`. Loading, empty, network, validation, and server-error states are rendered in the relevant page instead of exposing implementation details.

## Backend

Registration hashes passwords with bcrypt. Login issues an expiring JWT signed with `JWT_SECRET_KEY`. A reusable FastAPI dependency validates the token and loads the account. Ownership checks prevent cross-user access to learner profiles, courses, progress, assessments, weaknesses, and recommendations.

FastAPI routers own HTTP validation and learner/topic ownership checks. Services own domain behavior:

- `diagnostic_service.py`: diagnostic question generation and fallback
- `path_engine.py`: prerequisite-aware deterministic ranking
- `content_service.py`: personalized learning content and fallback
- `assessment_service.py`: topic assessment generation and fallback
- `assessment_result_service.py`: deterministic scoring, skill updates, weakness detection, recommendations, and path mutation

## Data flow

An authenticated learner profile and goal are stored first. OpenRouter generates a validated course structure; the backend assigns generated topic IDs, persists `GeneratedCourse` and owned `Topic` rows, and writes generated prerequisite edges. Diagnostic answers create an `Assessment` record and concept-level `SkillScore` records. The path engine reads the learner's owned topics, prerequisites, scores, progress, and assessment history to persist a `LearningPath`.

Opening a current topic creates or updates `TopicProgress`. Completing the topic starts a topic assessment. Submission stores answers and score, updates skill evidence, creates or resolves `Weakness` records, stores a `Recommendation`, and updates the current path position. Refreshing any later page reads that state from SQLite.

## AI boundary

```text
FastAPI
    |
    +--> OpenRouter
    |       |
    |       +--> questions, explanations, learning content
    |
    +--> Pydantic validation
            |
            +--> curated fallback if invalid/unavailable
```

The model never owns authentication, scores, permissions, prerequisites, topic selection, progress, weakness status, or recommendations. Those decisions remain deterministic and testable in the backend. Legacy unowned prototype learners remain compatible; authenticated learners use their persisted generated curriculum.
