# Test Case 1: Diagnostic to Adaptive Learning

## Result

The learner journey completed in fallback mode. OpenRouter was configured and the application attempted real calls, but the provider returned HTTP 429 for the tested operations. The application used its supported fallbacks. This is not evidence of successful live AI generation.

This is a historical browser run from 2026-10-08. Runtime URLs and provider observations below describe that run only.

| Item | Observed |
|---|---|
| Frontend | `http://127.0.0.1:5174` |
| Backend | `http://127.0.0.1:8001` |
| OpenRouter model | `openrouter/free` |
| OpenRouter key | Configured; value omitted |
| Provider result | HTTP 429 through the single bounded retry |
| Database | Existing configured SQLite database; no manual row edits |

## Journey and evidence

1. Registered a fresh account through `POST /api/auth/register`.
2. Loaded implemented tracks/goals from `GET /api/tracks` and `GET /api/goals`; selected Generative AI, beginner level, and an LLM-application goal.
3. Saved the learner profile using `POST /api/learners`.
4. Generated and persisted the selected-track course using `POST /api/curriculum/generate`. OpenRouter returned 429; a deterministic track-specific curriculum was saved and returned.
5. Started the diagnostic using `POST /api/learners/{learner_id}/diagnostic`. OpenRouter returned 429; eight curated questions were returned. A repeated request reused the pending diagnostic. Public questions did not include answer keys.
6. Submitted the diagnostic using `POST /api/learners/{learner_id}/diagnostic/{assessment_id}/submit`. Backend scoring produced 50% (4/8). Interpretation fell back to deterministic guidance.
7. Loaded the persisted path and opened its current topic. The lesson used curated fallback content. Repeating the unchanged content request returned saved content without another provider call.
8. Marked the lesson complete and generated a three-question topic assessment. Curated questions were returned without exposing answer keys.
9. Submitted one correct and two incorrect answers. Backend scoring produced 1/3 (33.3%). A weak concept was persisted, deterministic remediation was shown, and the same topic remained the learner's remediation focus.
10. Reloaded the dashboard and path. The saved assessment result, weakness, recommendation, and current topic were visible.

## Requests observed

The journey used registration, track/goal reads, learner creation, curriculum generation, diagnostic generation and submission, curriculum/path reads, lesson retrieval and completion, topic-assessment generation and submission, and dashboard reads. Successful application endpoints returned HTTP 200 or the expected registration/creation status. A pre-profile `GET /api/learners/me` returned 404, which was expected for the new account.

Passwords, bearer tokens, account email, and learner/database identifiers are intentionally omitted from this report.

## AI versus deterministic behavior

| Operation | Provider observation | Result used by the application |
|---|---|---|
| Curriculum | HTTP 429 after retry | Deterministic track-specific curriculum |
| Diagnostic questions | HTTP 429 after retry | Curated questions |
| Diagnostic interpretation | HTTP 429 after retry | Deterministic interpretation |
| Lesson | HTTP 429 after retry | Curated, persisted lesson |
| Topic assessment questions | HTTP 429 after retry | Curated questions |
| Topic remediation | HTTP 429 after retry | Deterministic guidance |
| Diagnostic/topic scoring | Not delegated to the LLM | Deterministic backend scoring |

OpenRouter calls were real attempts, but no operation above succeeded with a usable live model response in this run. The score, skill/weakness changes, and progress transition were backend decisions.

## Verification and limits

The original implementation run recorded 73 backend tests passing and one opt-in live-provider test skipped; the frontend production build passed. A later full backend run on 2026-10-09 reported **122 passed, 1 skipped**, and the frontend production build and `git diff --check` passed.

The browser run does not establish successful AI generation, numeric latency improvement, sandbox execution, or behavior for every track. It verifies the observed fallback journey and persistence reads described above.
