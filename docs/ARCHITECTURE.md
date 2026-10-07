# Architecture

## System flow

```text
React + Vite
    |
    | REST/JSON
    v
FastAPI routers
    |
    +--> Deterministic adaptive engine
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

FastAPI routers own HTTP validation and learner/topic ownership checks. Services own domain behavior:

- `diagnostic_service.py`: diagnostic question generation and fallback
- `path_engine.py`: prerequisite-aware deterministic ranking
- `content_service.py`: personalized learning content and fallback
- `assessment_service.py`: topic assessment generation and fallback
- `assessment_result_service.py`: deterministic scoring, skill updates, weakness detection, recommendations, and path mutation

## Data flow

Learner profile and goal are stored first. Diagnostic answers create an `Assessment` record and concept-level `SkillScore` records. The path engine reads those scores, topic prerequisites, goal relevance, progress, and assessment history to persist a `LearningPath`.

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

The model never owns scores, permissions, prerequisites, topic selection, progress, weakness status, or recommendations. Those decisions remain deterministic and testable in the backend.
