# Multimodal Tutor and Sandbox Verification

**Date:** 2026-10-09
**Scope:** Image-aware tutor requests, private attachment storage, AI coding assistance, remote Python execution, browser behavior, and regression validation.

## Result summary

| Area | Result | Execution evidence |
|---|---|---|
| Backend regression suite | **PASS — verified by actual execution** | `134 passed, 3 skipped`; the three skips include opt-in provider/sandbox checks and pre-existing skipped coverage. |
| Frontend production build | **PASS — verified by actual execution** | `npm.cmd run build` completed after the workspace handler fix. |
| `git diff --check` | **PASS — verified by actual execution** | Completed with no whitespace errors. |
| OpenRouter text generation | **FAIL — provider rate limited** | A single `tutor_coding_generate` call through the existing coding service returned HTTP 429 (`RateLimitError`); no structured response was received or validated. |
| OpenRouter vision generation | **BLOCKED — no vision model configured** | `OPENROUTER_VISION_MODEL` is empty. Model capability lookup could not be verified; no image analysis was claimed. |
| OpenRouter API key | **PASS — configuration presence checked** | `OPENROUTER_API_KEY = CONFIGURED`; the value was not printed or recorded. |
| Image UI and failure behavior | **PASS — verified by actual browser execution** | Image preview worked; upload returned HTTP 503 with an actionable `OPENROUTER_VISION_MODEL` configuration message and retry/text-only controls. |
| Sandbox execution | **BLOCKED — no service configured** | `CODE_SANDBOX_URL` is empty. Clicking Run Code returned `unavailable` and the configuration error; no local execution occurred. |
| Browser assessment-to-lesson journey | **PASS — verified in fallback mode** | Registered an isolated learner, selected Generative AI, completed the diagnostic, saw deterministic scoring/weakness analysis and a personalized path, and opened the recommended lesson. |
| Browser tutor conversation | **PASS — fallback response persisted** | A text question received a context-aware fallback after OpenRouter returned HTTP 429; history was restored after refresh and login. This was not a live AI answer. |
| Cross-user tutor access | **PASS — denied in browser** | A second learner's attempt to open the first learner's tutor activity returned HTTP 403 and an unavailable-activity page. |
| Full requested browser workflow | **NOT TESTED — incomplete external prerequisites** | Live vision, successful AI coding response, real isolated execution, post-learning assessment/reassessment, and sandbox-backed debugging could not be verified. |

## Environment and commands

- The normal backend/frontend listeners on ports 8000 and 5173 were already occupied. Verification therefore used backend port 8011 and frontend port 5175.
- The verified backend used a dedicated SQLite database and private upload directory under the session's `files` folder; the repository's application database was not reset or selected for the isolated run.
- Backend: `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8011`
- Frontend: `$env:VITE_API_BASE_URL='http://127.0.0.1:8011/api'; npm.cmd run dev -- --host 127.0.0.1 --port 5175 --strictPort`
- Backend health and frontend HTML both returned HTTP 200.
- OpenRouter endpoint: `https://openrouter.ai/api/v1`
- Configured model: `nvidia/nemotron-3-ultra-550b-a55b:free`
- `OPENROUTER_API_KEY = CONFIGURED`; `OPENROUTER_VISION_MODEL = NOT CONFIGURED`; `CODE_SANDBOX_URL = NOT CONFIGURED`.
- A controlled request through `tutor_coding.assist_with_code` used action `generate`, a minimal Python addition-function request, and the configured model. OpenRouter returned HTTP 429 on the first attempt; the service was configured not to retry this coding request. The provider result was not parsed.
- Optional smoke command: `$env:RUN_LIVE_TUTOR_SMOKE='1'; .\.venv\Scripts\python.exe -m pytest -q tests\test_live_tutor_smoke.py`. Result: `2 skipped`; vision model and sandbox URL are missing.

Backend suite (run from `backend`):

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Frontend production build (run from `frontend`):

```powershell
npm.cmd run build
```

Git whitespace validation (repository root):

```powershell
git diff --check
```

## Browser execution details

The actual Chromium-based browser journey used the visible React UI against the isolated backend:

1. Home page rendered; registration returned HTTP 201 and the new learner authenticated.
2. Learner selected the real Generative AI track, beginner experience, and an LLM-app learning goal.
3. Diagnostic questions were returned after two provider HTTP 429 responses and an explicit backend log entry identified curated fallback. Submission produced a deterministic score of 0%; all eight sampled concepts were weak.
4. Learning interpretation and curriculum generation also logged deterministic fallback after provider HTTP 429 responses. The personalized path displayed all eight assessment weaknesses, ordered ten topics, and recommended Prompt Design first.
5. The lesson rendered through curated fallback content. The learner opened the integrated tutor, sent a text question, and received a context-aware fallback response.
6. The image view displayed a selected-image preview. Submitting it returned HTTP 503 because no vision model is configured; the UI offered retry and text-only continuation rather than claiming image analysis.
7. The coding workspace rendered after fixing the handler-scope error described below. Run Code returned status `unavailable` with the missing-`CODE_SANDBOX_URL` message. No output was fabricated and no code ran locally.
8. Tutor history remained visible after closing/reopening the tutor, reloading the lesson, and logging out and back in.
9. A second browser-registered account was denied access to the first learner's tutor activity with HTTP 403.
10. At a 390 x 844 mobile viewport, the tutor dialog and coding tab remained visible; document width was 375 CSS pixels and did not exceed the viewport's document width.

The browser emitted HTTP errors for expected missing-provider configuration/rate-limit cases and cross-user denial. During the initial run it also exposed a real JavaScript error in the coding workspace; that defect was fixed and the workspace was re-opened and exercised afterward. The mobile screenshot is saved outside the repository at:

`C:\Users\Shivakumar\.copilot\session-state\6f86c361-e7d8-49f3-8521-f2eaec75833c\files\multimodal-tutor-mobile.png`

### Test-data isolation note

Before checking port availability, an initial browser attempt reached the already-running service on port 8001 and registered an extra synthetic account there. The service's OpenAPI description exposes no account-deletion endpoint. That service was left running and its database was not edited directly; no further verification used that account or service. The successful verification used the isolated service and database on ports 8011/5175. The extra account's synthetic email was `multimodal-e2e-20261009@example.invalid`; no password or token is recorded.

## Defect fixed

Opening the Coding workspace initially raised `ReferenceError: runCodeInSandbox is not defined`. The `ensureActiveConversation`, `runCodeInSandbox`, and `askCodingAssistant` handlers had been declared inside `sendMessage`, so JSX could not access them. They were moved to `TutorPage` component scope. The browser then opened the workspace and showed the expected explicit unavailable state when the sandbox URL was absent.

## Limits and next actions

- Configure `OPENROUTER_VISION_MODEL` with a model available to the account whose `/models` metadata advertises image input, then rerun the optional live vision smoke test.
- Resolve the OpenRouter 429 condition (account quota/provider rate limit or model availability) before claiming any live text, vision, or coding-assistant response.
- Configure `CODE_SANDBOX_URL` to a separately deployed isolated service implementing the documented task contract; then run the harmless live sandbox smoke test. Unit mocks do not establish sandbox isolation.
- Repeat the complete browser flow with working provider and sandbox services, including a successful code-generation response, real isolated execution, post-learning assessment/reassessment, and sandbox-backed debugging.
- The initial extra account on the pre-existing port-8001 service requires cleanup through that service's administrator because no deletion API is exposed; no direct database edits were made.
