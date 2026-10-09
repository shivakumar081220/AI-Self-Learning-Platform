# AI Tutor Architecture

The tutor is integrated with the learner's saved course and topic. It uses the same persistent conversation for typed questions, voice transcripts, and lesson-section questions.

## Context

`build_tutor_context` in `backend/app/services/tutor_conversation_service.py` assembles current learner context from saved profile, course, topic, path, progress, skills, weaknesses, and recent assessments. The active lesson section and a bounded window of recent conversation messages are added for the current turn.

The context builder does not make an AI request. It verifies course/topic ownership and provides educational context only; authentication secrets and unrelated account data are excluded.

## Conversation API and persistence

All tutor routes require authenticated learner ownership. Foreign conversation IDs are returned as not found.

| Action | API |
|---|---|
| Build context | `GET /api/learners/{learner_id}/tutor/context` |
| Create conversation | `POST /api/learners/{learner_id}/tutor/conversations` |
| List conversations | `GET /api/learners/{learner_id}/tutor/conversations` |
| Resume conversation | `GET /api/learners/{learner_id}/tutor/conversations/{conversation_id}` |
| Send turn | `POST /api/learners/{learner_id}/tutor/conversations/{conversation_id}/messages` |

`TutorConversation` and `TutorMessage` persist conversation history. Closing the tutor UI does not delete the conversation. A fresh request rebuilds the learner context, so saved messages do not freeze stale skill or progress state.

## Response and fallback

Each learner turn may trigger one structured OpenRouter operation through `request_structured_json`. The response schema supports a direct answer, key points, steps, an example/application, common mistake, takeaway, teaching approach, and follow-up prompt. The service receives learner level, weak/strong areas, current lesson context, and recent assessment evidence.

Missing provider configuration, provider errors, timeouts, rate limits, or invalid structured output use the contextual deterministic fallback. Fallback replies are not represented as LLM output. Tutor conversation alone does not update skill scores, resolve weaknesses, or advance progress; graded assessment remains responsible for those changes.

## Lesson and voice integration

Lesson controls can send a topic section or subsection as additional bounded context. Suggested questions are built from the active lesson section without a separate AI call. Learners can request a different teaching style; the selected style is validated and included in the next turn.

Browser speech recognition converts speech to text, then sends it through the same tutor-message endpoint. Browser speech synthesis can read the response aloud. Raw audio is not stored by the application. If voice APIs are unsupported or permission is denied, typed interaction and visible text remain available.

## Limits

Schema validation checks response shape, not factual accuracy. Automated tests use mocked provider responses and do not establish live OpenRouter availability or browser microphone/speech behavior. Conversation messages are persistent; the prompt context window for each provider request is bounded.
