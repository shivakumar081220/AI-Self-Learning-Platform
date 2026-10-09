# Architecture

## System overview

```text
React + Vite
    | authenticated REST/JSON
    v
FastAPI routers
    +-- authentication and ownership checks
    +-- curriculum, diagnostic, learning, assessment, tutor APIs
    |
    +-- domain services --> SQLAlchemy --> configured database
    |
    +-- AI provider --> OpenRouter (optional)
    |                    |
    |                    +--> schema validation and feature fallback
    |
    +-- code assessments --> external sandbox (optional deployment service)
```

SQLite is the default local database. Relative SQLite file URLs are resolved from the backend directory so the selected file does not change with the process working directory.

## Learner journey

1. Registration creates an account; profile setup saves the selected track, goal, and experience level.
2. The diagnostic service generates or retrieves questions. Submission is scored by backend logic and persists concept-level evidence.
3. Curriculum generation uses the saved learner and assessment context to create a track-specific ordered course. The course and module outline persist and are reused on later visits.
4. Opening a topic loads cached lesson content or generates and validates it. The module sequence comes from the curriculum; there is no separate path inside a module.
5. Topic assessment submission updates skills, weaknesses, progress, and recommendations. The curriculum remains stable unless explicitly adapted.
6. The dashboard and tutor reconstruct their views from saved learner, course, lesson, assessment, and conversation records.

## Service boundaries

| Concern | Implementation |
|---|---|
| Authentication and ownership | `routers/auth.py`, authentication dependencies, and learner ownership checks |
| Curriculum generation and persistence | `services/curriculum_service.py` |
| Diagnostic generation | `services/diagnostic_service.py` |
| Prerequisite-aware sequencing | `services/path_engine.py` |
| Topic lessons and validation | `services/content_service.py` |
| Legacy MCQ generation | `services/assessment_service.py` |
| Multi-type assessment generation/evaluation | `services/multi_type_assessment_service.py` |
| Skill, weakness, and recommendation updates | `services/assessment_result_service.py` and `services/learning_ai_service.py` |
| Tutor context and conversation replies | `services/tutor_conversation_service.py` |
| Structured OpenRouter requests and retries | `services/ai_provider.py` |
| Reusable generated artifacts | `services/ai_cache.py` |

Routers validate requests and enforce access; services implement domain operations. AI services return validated content or a defined fallback. They do not own authorization or learner-state transitions.

## Persistent state

| Data | Model/table |
|---|---|
| Accounts and learner profiles | `User`, `Learner` |
| Goals | `LearningGoal` |
| Personalized courses | `GeneratedCourse` |
| Ordered module outline | JSON on `GeneratedCourse` |
| Course topics and prerequisites | `Topic`, `TopicPrerequisite` |
| Cached lesson and other artifacts | `AIArtifactCache` |
| Current path and position | `LearningPath` |
| Topic status and completion | `TopicProgress` |
| Assessments and questions | `Assessment`, `AssessmentQuestionRecord` |
| Saved responses and evaluations | `AssessmentResponseRecord` |
| Skills, weaknesses, and recommendations | `SkillScore`, `Weakness`, `Recommendation` |
| Tutor history | `TutorConversation`, `TutorMessage` |

Dashboard metrics are derived from persisted records rather than maintained as a separate snapshot. Browser storage is used for authentication state, not as the source of course or lesson data.

## AI and deterministic responsibilities

OpenRouter can generate structured curricula, questions, lesson content, tutor responses, and selected interpretations/evaluations. Pydantic schemas and operation-specific checks validate output before persistence. Supported operations use curated or deterministic fallback behavior when generation is unavailable or invalid.

Application logic controls password/authentication checks, ownership, objective scoring, concept updates, progress, prerequisite order, and persistence. Subjective assessment evaluation may use AI; code questions use the configured external sandbox. Fallbacks are explicitly distinguished from AI-generated responses.

## Reliability and known deployment needs

Provider calls have a bounded retry policy and do not log prompts, response bodies, credentials, or learner identifiers. The frontend reports request failures rather than silently accepting empty results.

The current SQLite compatibility migration is hand-maintained; a production deployment should adopt a versioned migration system. Code execution requires an independently secured sandbox with process isolation, resource limits, network restrictions, and execution timeouts.
