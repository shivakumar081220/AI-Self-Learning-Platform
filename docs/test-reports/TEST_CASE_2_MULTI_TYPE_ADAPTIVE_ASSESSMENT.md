# Test Case 2: Multi-Type Adaptive Assessment

## Scope

This is an automated FastAPI integration test using a fresh SQLite database per test. It is not a live browser run. OpenRouter generation/evaluation and sandbox execution are mocked. No live provider request or external code execution is claimed.

At the time of the original focused run, `OPENROUTER_API_KEY` was configured, the model was `openrouter/free`, and `CODE_SANDBOX_URL` was not configured. No credential value is recorded. With no sandbox, an unmocked code-bearing submission correctly returns HTTP 503 instead of running learner code in FastAPI.

## Learner journey

1. Register a new account and create a Generative AI learner profile.
2. Generate a persisted curriculum and path using the application's fallback.
3. Complete a course topic and request MCQ, Scenario, Coding, and Debugging questions in one generation request.
4. Verify selected types, course/topic association, persisted question data, and omission of answer keys and hidden grading fields from the public response.
5. Assert one structured generation operation creates the full assessment.
6. Submit responses. MCQ scoring is deterministic; subjective evaluation and sandbox results are mocked.
7. Verify aggregated scores, type/concept results, skill and weakness updates, recommendation/path focus, and dashboard state.
8. Reopen the assessment and verify the saved result is returned without regeneration or reevaluation.

The controlled fixture scores 25% (one correct MCQ out of four one-point questions). This is a test fixture, not a live learner result.

## Additional coverage

- All seven assessment types and validation of type-specific fields.
- Hidden-answer protection, malformed-output fallback, and cache reuse.
- Grouped subjective evaluation and batched sandbox integration behavior using mocks.
- Code Output grading against captured sandbox stdout using a mock.
- Draft response save/resume and duplicate pending-assessment reuse.
- Cross-learner access rejection and backwards-compatible legacy MCQ tests.
- Explicit refusal to complete code-bearing work when no sandbox is configured.

## Implementation path

- UI: `LearningExperiencePage` and `AssessmentPage` in `frontend/src/App.jsx`
- Client: assessment functions in `frontend/src/api/client.js`
- API: assessment routes in `backend/app/routers/assessment.py`
- Generation, evaluation, and adaptive updates: `backend/app/services/multi_type_assessment_service.py`
- Persistence: `Assessment`, `AssessmentQuestionRecord`, and `AssessmentResponseRecord` in `backend/app/models.py`

## Verification record

The original focused run recorded **85 passed, 1 skipped**; the skipped test was the opt-in live OpenRouter smoke test. The frontend production build and `git diff --check` passed at that time. The later full backend run on 2026-10-09 reported **122 passed, 1 skipped**.

These tests establish mocked API behavior and frontend compilation, not live OpenRouter generation, sandbox isolation/performance, or browser interaction.
