# AI API Flow

This document maps the current learner journey to the implementation. AI output is never used as an assessment score or as authority for database ownership, progress, or prerequisite ordering.

## User-action flow

| User action | Frontend function/component | HTTP request | Backend route/function | Persistence | AI behavior / response |
|---|---|---|---|---|---|
| Submit profile and enroll | `ProfilePage.handleSubmit` in `frontend/src/App.jsx` | `POST /api/learners`, then `POST /api/curriculum/generate` | `create_learner`, then `generate_my_curriculum` | `Learner`, `LearningGoal`, `GeneratedCourse`, generated `Topic` rows, and `TopicPrerequisite` rows | One lazy curriculum operation at enrollment; `GeneratedCurriculum` is validated before writes. Existing matching curriculum returns as persisted. |
| Begin diagnostic | `DiagnosticPage` effect; `generateDiagnostic` in `frontend/src/api/client.js` | `POST /api/learners/{learner_id}/diagnostic` (`/generate` remains a hidden compatibility alias) | `generate_learner_diagnostic` → `generate_diagnostic` | Persist `Assessment.questions_json`; server-only answer keys and explanations stay in the row | Generates eight course-topic questions on demand. The durable AI artifact cache suppresses repeated equivalent generation; a pending diagnostic assessment is reused. |
| Submit diagnostic | `DiagnosticPage.handleSubmit` | `POST /api/learners/{learner_id}/diagnostic/{assessment_id}/submit` | `submit_learner_diagnostic` → `score_diagnostic` → `interpret_skill_results` | Assessment score/answers, `SkillScore`, and interpretation in `Assessment.feedback_json` | MCQ scoring is deterministic. One structured interpretation may run after the score is committed; invalid/unavailable output uses a deterministic interpretation. |
| Open a topic | Learning component effect; `getLearningContent` | `GET /api/learners/{learner_id}/topics/{topic_id}/content` | `get_topic_content` → `generate_learning_content` | Valid lesson in `AIArtifactCache`, keyed by learner/topic/profile/skill/progress state | First request is lazy; same valid result is returned as `source=cache`. Failed-provider fallback entries expire after 60 seconds. |
| Complete a topic | `handleComplete` | `POST /api/learners/{learner_id}/topics/{topic_id}/complete`, then `POST /api/learners/{learner_id}/topics/{topic_id}/assessment/generate` | `complete_topic`, then `generate_topic_assessment` | Topic progress/path state and pending `Assessment.questions_json` | Assessment is generated only for the completed topic. An existing pending assessment is reused. |
| Submit topic assessment | Assessment result `handleSubmit` | `POST /api/learners/{learner_id}/assessments/{assessment_id}/submit` | `submit_assessment` → `apply_assessment_result` | Deterministic score/answers, `SkillScore`, `Weakness`, `Recommendation`, path and progress; interpretation/remediation in feedback | Scoring and adaptive ordering are deterministic. Targeted remediation is generated only for a weak result and is persisted with the assessment. |
| Reopen dashboard/path | Dashboard/path effects | `GET /api/learners/{learner_id}/summary`, `GET /api/learners/{learner_id}/learning-path` | `get_learner_summary`, `get_learning_path` | Read persisted learner state | No generation is needed to display saved state. |

## Hybrid adaptive-path decision

`path_engine.generate_path_plan` consumes persisted skills, assessment history, progress, goal, experience, and prerequisite edges. If the latest completed diagnostic contains a schema-valid `ai_interpretation` with `source="openrouter"`, its exact known `focus_concepts` may break otherwise-equal topic-priority ties and are included in the matching topic rationale. Fallback interpretations are not labeled or used as AI path guidance. The path engine still owns topic validation, prerequisite ordering, completion filtering, and progress state; it makes no additional LLM request.

## Enrollment and lazy-generation contract

The profile submission waits for the curriculum response and disables the submit button. The diagnostic page no longer calls curriculum generation. Enrollment generates only the curriculum; diagnostic, lesson, topic assessment, interpretation, remediation, and tutor content run only at their user-triggered points. A generated lesson cache key changes when relevant skill, completed-topic, assessment, goal, or topic context changes.

When OpenRouter is unavailable, deterministic fallback curricula use a concept set specific to each selected track. Generated lesson key concepts are taken from that topic's saved concepts; fallback lessons do not append a generic concept to every topic.

## Validation and access

- Backend Pydantic schemas reject unsupported fields and invalid types before persistence.
- Diagnostic and topic-assessment public question schemas contain concept/difficulty but omit answer keys and explanations.
- Learner routes retain their existing ownership checks.
- Scores, concept updates, weaknesses, recommendation actions, and prerequisite ordering are application-controlled.
- Provider logs record operation timing, provider status, source, model, and schema validation status without request bodies or credentials.
