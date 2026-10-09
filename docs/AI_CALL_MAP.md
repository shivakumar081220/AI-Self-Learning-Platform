# AI Call Map

AI-backed services use `request_structured_json` from `backend/app/services/ai_provider.py`. The helper sends schema-constrained requests to the configured OpenRouter model and validates the parsed result against a Pydantic model. Operations run lazily when the learner reaches the relevant action.

| Operation | Service | Trigger | Context (summary) | Output / fallback |
|---|---|---|---|---|
| Curriculum | `curriculum_service.generate_curriculum` | Course enrollment or explicit curriculum generation | Selected track, goal, level, skill and assessment evidence, completed topics, prerequisites | Validated ordered curriculum; track-specific deterministic fallback |
| Diagnostic questions | `diagnostic_service.generate_diagnostic` | Start diagnostic | Learner profile, course concepts, prior diagnostic evidence | Validated question set; curated questions |
| Diagnostic interpretation | `learning_ai_service.interpret_skill_results` | After deterministic diagnostic scoring | Score, concept evidence, goal, level, track | Structured interpretation; deterministic interpretation |
| Topic lesson | `content_service.generate_learning_content` | Open a topic | Course/module/topic objectives, learner level, strengths/gaps, completed topics, recent course assessments | Validated lesson; curated topic-specific lesson |
| Legacy topic MCQs | `assessment_service.generate_assessment_questions` | Legacy MCQ generation route | Topic concepts, level, weak areas, prior topic questions | Validated MCQ set; curated MCQs |
| Multi-type assessment | `multi_type_assessment_service.generate_assessment` | Learner selects assessment types | Track/course/topic, learner context, selected types, completed work | Validated selected question types; curated fallback |
| Subjective answer evaluation | `multi_type_assessment_service.evaluate_open_responses` | Submit multi-type assessment with open responses | Topic concepts, learner context, answers, server-only rubric and expected concepts | Grouped structured scores/feedback; deterministic evaluation fallback |
| Remediation guidance | `learning_ai_service.generate_remediation_aid` | Assessment identifies weak evidence | Result, weak concepts, topic, learner goal and level | Targeted structured guidance; deterministic remediation |
| Tutor response | `tutor_conversation_service.generate_tutor_response` | Learner sends a tutor turn | Current course/module/topic, lesson section, skill state, recent assessments, bounded conversation | Structured contextual reply; deterministic tutor response |

## Other execution

Code Output, Coding, and Debugging assessment tasks use a batched request to the configured `CODE_SANDBOX_URL`; this is not an OpenRouter call. FastAPI does not execute learner code. If the sandbox is not configured, the code-bearing submission fails explicitly and is not marked complete.

Browser speech recognition and synthesis use browser APIs. Speech transcripts are submitted as regular tutor messages; raw audio is not stored by the application.

## Reuse and retries

Curricula, lesson content, and assessment generation use persisted context-aware artifacts or matching pending assessments where applicable. Tutor responses are not cached because they depend on the current conversation turn.

The provider permits at most one retry per operation, for a maximum of two HTTP attempts. Transient HTTP failures honor a bounded `Retry-After`; invalid structured output may be corrected once. No retry behavior is a guarantee of provider availability.

## Telemetry

Provider events include operation, start time, duration, source, model, status, HTTP status, and validation status. Cache/fallback outcomes are identifiable. Prompts, response bodies, credentials, and learner identifiers are excluded.
