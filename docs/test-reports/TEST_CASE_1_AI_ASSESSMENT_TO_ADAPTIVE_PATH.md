# Test Case 1 — AI Assessment to Adaptive Learning Path

## Current implementation verification — fresh browser run

**Outcome: FULL JOURNEY COMPLETED IN FALLBACK MODE; LIVE AI GENERATION DID NOT SUCCEED.** This run exercised the current code through the UI with a fresh account. The root `.env` reported `OPENROUTER_API_KEY = CONFIGURED`, `OPENROUTER_MODEL = openrouter/free`, and `OPENROUTER_BASE_URL = https://openrouter.ai/api/v1`. OpenRouter was actually called, but the provider returned HTTP 429 twice (initial attempt plus the single bounded retry) for each AI operation. Every affected endpoint returned usable fallback content; do not describe this run as successful AI-generated curriculum, diagnostic, lesson, assessment, interpretation, or remediation.

| Environment item | Observed |
|---|---|
| Browser run window | 2026-10-08, approximately 03:42–03:45 UTC (ordered sequence below; exact timestamp for every click was not captured) |
| Backend | Updated app process on `http://127.0.0.1:8001`, launched from `backend` with `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001`; `/api/health` returned 200 |
| Frontend | Updated Vite process on `http://127.0.0.1:5174`, launched with `VITE_API_BASE_URL=http://127.0.0.1:8001/api npm run dev -- --host 127.0.0.1 --port 5174` |
| Existing process | An unrelated-to-this-run server was already listening on port 8000; it was not stopped or modified |
| Database | Existing SQLite configured by the application; no database records were manually edited |
| OpenRouter | Key configured (value omitted); `openrouter/free`; standard OpenRouter API base URL |
| Latency | Per-provider and endpoint milliseconds were not captured in the server output. No latency improvement is claimed. |

### Fresh learner and result

- Registered through the UI; `POST /api/auth/register` returned **201**. No email, password, or bearer token is included.
- Learner **15**, track **Generative AI** (`generative_ai`), experience **beginner**, goal **Build an LLM-powered application**, target outcome **Build a validated LLM-powered application with measurable quality**.
- `POST /api/learners` returned **201**. `POST /api/curriculum/generate` returned **200**, persisted course **12**, but its `generation_source` was `deterministic_fallback`; it contained five topics.
- Diagnostic **31** contained eight questions from `curated_fallback`; a repeated diagnostic POST returned the same pending assessment ID and did not issue another provider request. Public questions omitted `correct_option` and `explanation`.
- Submitted four option-0 answers and four option-1 answers through the UI. `POST /api/learners/15/diagnostic/31/submit` returned **200** and **50% (4/8)**. This result was deterministic. The diagnostic interpretation used `deterministic_fallback`; at 50%, concepts were developing and no diagnostic weak-area classification was reported.
- `GET /api/learners/15/learning-path` returned **200**, path **16**, initially focused on the first generated topic, `Generative AI Foundations · 12-1`.
- Opening that topic invoked its content GET. It returned **200** with `source=curated_fallback` and displayed the explicit deterministic-fallback notice. Repeating the unchanged GET returned the persisted fallback content; the server log showed no second OpenRouter request. The API `source` continues to name the artifact's origin rather than a cache hit.
- Completing the topic returned **200**; generated topic assessment **32** returned **200** with three questions and `source=curated_fallback`. Its public questions also omitted answer keys.
- Submitted one correct and two incorrect answers. `POST /api/learners/15/assessments/32/submit` returned **200**, deterministic score **1/3 (33.3%)**, and weak concept `generative_ai`. The weak result triggered one remediation operation; after two provider 429 responses, deterministic remediation was displayed and saved in assessment feedback.
- Reloaded `/dashboard`: it showed the persisted **33.3%** latest assessment, weak concept `generative_ai`, the same topic held for remediation, and “Review weak concepts and reassess before continuing.” The refreshed path retained that topic and its rationale explicitly cited the weak concept. Summary and path GETs returned **200**.

### Observed API and provider sequence

All user-visible API requests below were made by the browser except the explicitly marked repeated diagnostic/content verification requests, which used the same authenticated API from the browser page. Passwords and tokens were not recorded.

| Sequence | Request | Status / observed response |
|---:|---|---|
| 1 | `POST /api/auth/register` | 201; fresh account |
| 2 | `GET /api/learners/me` | 404 before profile creation; expected for a new account with no learner profile |
| 3 | `GET /api/goals`, `GET /api/tracks` | 200; selectable options loaded |
| 4 | `POST /api/learners` | 201; learner 15, beginner, Generative AI, selected goal/outcome |
| 5 | `POST /api/curriculum/generate` | 200; course 12; five topics; `deterministic_fallback` |
| 6 | `POST /api/learners/15/diagnostic` | 200; eight questions; `curated_fallback` |
| 7 | Repeated `POST /api/learners/15/diagnostic` | 200; reused assessment 31; no duplicate generation |
| 8 | `GET /api/curriculum/current` | 200; course 12 and persisted fallback source |
| 9 | `POST /api/learners/15/diagnostic/31/submit` | 200; deterministic 50%; interpretation fallback |
| 10 | `GET /api/learners/15/learning-path` | 200; path 16 |
| 11 | `GET /api/learners/15/learning-path/current`, `GET /api/learners/15/topics/generated-d5256caf5d684897a56078a40cf31b1b/content` | 200; curated lesson |
| 12 | Repeated same lesson content GET | 200; persisted artifact reused; no second provider request in server log |
| 13 | `POST /api/learners/15/topics/generated-d5256caf5d684897a56078a40cf31b1b/complete` | 200 |
| 14 | `POST /api/learners/15/topics/generated-d5256caf5d684897a56078a40cf31b1b/assessment/generate` | 200; assessment 32; three fallback questions |
| 15 | `GET /api/learners/15/assessments/32` | 200; answer-key-free public assessment; `curated_fallback` |
| 16 | `POST /api/learners/15/assessments/32/submit` | 200; deterministic 33.3%; weak concept `generative_ai`; deterministic remediation |
| 17 | `GET /api/learners/15/summary`, `GET /api/learners/15/learning-path` | 200; persisted weak skill, recommendation, current topic and adapted rationale |

| AI operation | Provider result | Endpoint-visible source/result |
|---|---|---|
| `curriculum_generation` | 429 on attempts 1 and 2 | `deterministic_fallback`; course persisted |
| `diagnostic_questions` | 429 on attempts 1 and 2 | `curated_fallback`; eight questions persisted |
| `learning_interpretation` | 429 on attempts 1 and 2 | `deterministic_fallback`; deterministic score unchanged |
| `learning_content` | 429 on attempts 1 and 2 | `curated_fallback`; persisted content served on repeat |
| `topic_assessment_questions` | 429 on attempts 1 and 2 | `curated_fallback`; three questions persisted |
| `learning_remediation` | 429 on attempts 1 and 2 | Deterministic remediation displayed and persisted |

The provider logs contained operation names and HTTP status without credential or learner data. The separate `RUN_OPENROUTER_LIVE_TEST=1 pytest tests/test_openrouter_live.py -q` was not run after six independent browser operations had each already exhausted their single retry with 429; additional requests to the same rate-limited free model would not add useful evidence. This is a live-provider failure observation, not a successful live smoke test.

### Automated verification after implementation

- Full backend suite with OpenRouter explicitly disabled in the test process: **73 passed, 1 skipped**. The opt-in live test was skipped.
- Focused diagnostic/path suites: **15 passed**.
- Frontend `npm run build`: **passed** (43 modules transformed).
- `git diff --check`: **passed**.

### Current-run limitations

- The app correctly attempted OpenRouter, but all six operations were rate-limited; AI-generation acceptance criteria are therefore **not demonstrated by this run**.
- Exact per-step timestamps and millisecond latency/cache speedup were not captured. The date/time above is the browser/server-observed run window, not fabricated per-request timing.
- Diagnostic score was 50%, but its 50%-scored concepts were classified as developing rather than weak. The separate 33.3% topic score produced and persisted a clear weak concept.
- The summary endpoint exposes weakness and remediation recommendation text but does not return the detailed remediation artifact; the completed assessment response/UI displayed it, and it is stored in that assessment's feedback.

> **PRIOR LEARNER-14 RUN RESULT: PARTIAL REAL-AI SUCCESS — SUPERSEDED BY CURRENT FALLBACK-MODE RUN ABOVE**
>
> In that prior run, fresh learner 14 selected **Generative AI** and completed an 8-question diagnostic, scoring **50%**. OpenRouter generated and persisted the curriculum and diagnostic questions. Four later AI requests were rate-limited (HTTP 429), so interpretation, learning content, topic questions, and remediation used the existing fallbacks. The topic assessment scored **1/3 (33.3%)**; deterministic scoring updated skills and weaknesses and adapted the deterministic learning path.
>
> **Historical run note:** Sections 1–26 and the API timeline below document the earlier learner-12 run. The learner-14 run and final verification are historical; the current fresh learner-15 result at the top supersedes them.

## 1. Test Objective

Trace a fresh learner from registration and track choice through curriculum and diagnostic generation, diagnostic evaluation, skill persistence, path creation, lesson completion, topic assessment, remediation, and path adaptation. The additional topic assessment is included because the diagnostic flow does not itself create `Weakness` or `Recommendation` rows.

The two assessment flows are distinct:

- **Diagnostic:** creates the onboarding assessment, stores per-concept `SkillScore` records, returns classifications, and is followed by a GET that creates the initial path. It does not create weakness or recommendation rows.
- **Topic assessment:** follows lesson completion; scores the answers, updates skills and progress, creates/updates weaknesses and recommendation state, and adapts an existing path in its result transaction.

## 2. Test Environment

| Item | Observed |
|---|---|
| OS / date | Windows; 2026-10-08 |
| Backend command | From `backend`: `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000` |
| Backend URL / port | `http://127.0.0.1:8000`; `/api/health` returned `200 {"status":"ok","service":"adaptive-learning-api"}` |
| Frontend command | Existing project Vite process; project command is `npm run dev -- --host 127.0.0.1` from `frontend` |
| Frontend URL / port | `http://127.0.0.1:5173`; this same-project Vite process was already running and was reused |
| Database | SQLite, `backend/adaptive_learning.db` |
| Frontend API base | `http://127.0.0.1:8000/api` |
| Python | 3.10.9 |
| `OPENROUTER_API_KEY` | **CONFIGURED** (value redacted) |
| `OPENROUTER_MODEL` | `openrouter/free` |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` |

The key was configured and the running backend loaded it. OpenRouter was actually called. The curriculum request returned usable structured content; diagnostic generation and interpretation logged structured-response validation failures; remediation and a later lesson reload logged empty structured content. Fallbacks were used only for operations that did not receive usable structured output. No API key, password, token, or test email is included here.

## 3. Test Learner

- Registered through the UI using `POST /api/auth/register`; response status `201 Created`.
- Registration created user row **9**. The returned bearer token was stored by the frontend and is omitted.
- Learner ID: **12**.
- Name: `Test Learner` (synthetic).
- Track: `generative_ai` (`Generative AI`).
- Goal: `Learn reliable prompt and output patterns`.
- Target outcome: `Build a reliable structured-output assistant`.
- Experience level: `beginner`.
- Associated active `LearningGoal` row: **15**.
- No database rows were manually edited. The DB confirmation was performed read-only.

Before onboarding, the UI queried `GET /api/learners/me` and received `404` because the new account did not yet have a learner profile. This was expected and led to profile setup.

## 4. Selected Course/Track

The UI loaded real options using `GET /api/tracks` and `GET /api/goals`. `Generative AI` was an implemented selectable track. The user selected that track and `Learn reliable prompt and output patterns`, kept beginner experience, and entered the target outcome.

**No network request occurs at track selection; the selection is stored in frontend state.** `ProfilePage.selectTrack()` and `selectTrackGoal()` update the form state. `ProfilePage.handleSubmit()` later sends the selected values in `POST /api/learners`.

## 5. Expected Flow

`RegisterPage.submit()` → `AuthProvider.register()` → `registerAccount()` → `POST /api/auth/register` → user creation → profile selection in local React state → `ProfilePage.handleSubmit()` → `POST /api/learners` → `DiagnosticPage` mount → curriculum POST → diagnostic POST → answer submission → deterministic scoring and skill update → path GET/create → lesson GET/completion → topic assessment generate/submit → deterministic weakness/recommendation update and path adaptation.

## 6. Actual Flow

The UI journey completed end to end. OpenRouter generated the personalized curriculum and returned structured topic-assessment questions. The diagnostic-question request and diagnostic interpretation request returned unusable structured output and used the existing curated/deterministic fallbacks. The initial lesson was returned as `PERSONALIZED LESSON`; a later post-assessment reload returned `CURATED LESSON` after an empty structured response. Both assessment scores were calculated deterministically by backend answer-key comparison.

The diagnostic produced four weak concepts, including `prompt_design`; the LLM-generated curriculum includes topics tagged with `prompt_design`. The first path therefore already targeted weak prompt design. After the topic quiz, `few_shot_learning` was also weak and the current topic moved to remediation. Its order stayed first, the path item status changed to remediation, and the recommendation named the weak concept.

## 7. Step-by-Step Execution

### Step 1 — Register account

- **User action:** Submitted the Create Account form.
- **Frontend page/component/function:** `RegisterPage.submit()` in `frontend/src/App.jsx`; `AuthProvider.register()` in `frontend/src/auth.jsx`.
- **API client:** `registerAccount()` in `frontend/src/api/client.js`.
- **Request:** `POST /api/auth/register`; status `201`.
- **Request body:** Synthetic name, unique test email, password and confirmation. Email/password omitted from this report.
- **Backend route/function:** `backend/app/routers/auth.py::register`.
- **Database/service:** `security.hash_password()` hashes the password; a `User` row is created, committed and refreshed.
- **Response/state:** Auth response contains access token and user; token redacted and held by frontend auth state/storage. UI navigated to `/dashboard`.
- **Next:** The new account had no learner; profile onboarding followed.

### Step 2 — Load and select track/goal

- **User action:** Opened profile and selected the actual `Generative AI` card, selected the goal, kept `beginner`, and entered target outcome.
- **Frontend:** `ProfilePage`; `getTracks()`, `getGoals()`, `selectTrack()`, and `selectTrackGoal()`.
- **Requests:** `GET /api/tracks` and `GET /api/goals`; both returned `200`.
- **Track selection request:** **No API call.** Selected values were kept in React form state.
- **Next:** Clicking **Begin diagnostic** submitted the learner profile.

### Step 3 — Create learner profile

- **User action:** Clicked **Begin diagnostic** on the profile form.
- **Frontend function/API client:** `ProfilePage.handleSubmit()` → `createLearner(profile)`.
- **Request:** `POST /api/learners`; status `201`.
- **Safe body summary:** `name="Test Learner"`, `experience_level="beginner"`, `track_id="generative_ai"`, selected goal and target outcome.
- **Backend route/function:** `backend/app/routers/learners.py::create_learner`.
- **Database:** Created `Learner` ID **12** (user ID **9**) and active `LearningGoal` ID **15**.
- **Response/state:** Learner response; UI navigated to `/diagnostic/12`.

### Step 4 — Generate personalized curriculum

- **Trigger/frontend:** `DiagnosticPage` mount effect calls `generateMyCurriculum()` before `generateDiagnostic(learnerId)`.
- **Request:** `POST /api/curriculum/generate`; status `200`.
- **Backend:** `curriculum.generate_my_curriculum()` → `curriculum_service.persist_curriculum()` → `generate_curriculum()` → `_openrouter_curriculum()` → `request_structured_json()`.
- **Safe LLM input summary:** Learner goal, target outcome, beginner experience, `generative_ai` track and track prerequisites; existing skill gaps, open weaknesses, completed topics, recent assessments, previous course/track context; available topic catalogue and prerequisite relationships; required 4–8 modules and `GeneratedCurriculum` JSON schema. At first generation this learner had no prior skill, weakness, completed-topic, or assessment history.
- **System instruction summary:** Generate a personalized curriculum for exactly the selected track, honor the learner’s goal/level and diagnostic evidence, preserve prerequisite ordering, and return the supplied schema without inventing database IDs.
- **Output/validation:** A structured response passed Pydantic validation and the service's learner goal/level/track consistency checks. The persisted `GeneratedCourse` has `generation_source="openrouter"`.
- **Observed output:** Course ID **9**, title `Reliable Prompting and Structured Output Patterns for Generative AI`, beginner level, six generated topics. They include Generative AI Foundations, Prompt Engineering Basics, Structured Outputs and JSON Formatting, Iterative Prompt Refinement, LLM Application Patterns, and Building a Structured-Output Assistant. Their concept tags include `prompt_design` and `few_shot_learning`.
- **Database:** Created `GeneratedCourse` ID **9**, six owner-specific `Topic` rows and prerequisite edges.
- **Frontend state:** Curriculum response was accepted; the page continued to diagnostic generation.

### Step 5 — Generate diagnostic assessment

- **Trigger/frontend:** `DiagnosticPage` mount effect calls `generateDiagnostic(12)`.
- **API client/request:** `generateDiagnostic()` → `POST /api/learners/12/diagnostic/generate`; status `200`.
- **Backend:** `diagnostic.generate_learner_diagnostic()` → `diagnostic_service.generate_diagnostic()` → `_openrouter_questions()` → `request_structured_json()`.
- **Safe LLM input summary:** Beginner experience, goal, target outcome, track, six curriculum topics and available concept tags, weak concepts/history, eight-MCQ requirement, zero-based internal answer metadata and `DiagnosticQuestionSet` schema. The system instruction says answer keys are server-side metadata.
- **Provider result:** Backend logged `OpenRouter structured response failed validation; model=openrouter/free`. There was no usable parsed `DiagnosticQuestionSet`.
- **Fallback:** Service used `_fallback_questions()` and returned `source="curated_fallback"`.
- **Database:** Created pending diagnostic `Assessment` ID **26**, with eight questions and private answer keys.
- **Frontend state/response:** UI received and rendered public question IDs, question text and options. The answer key and explanations were absent.

### Step 6 — Verify keys are hidden before submission

- **Result:** **PASS**.
- **Browser:** Before submission, the diagnostic UI showed each question and options only.
- **Backend response construction:** Diagnostic route maps to `DiagnosticQuestionPublic` fields, omitting `correct_option` and `explanation`.
- **Topic assessment equivalent:** `_public_response()` maps to `AssessmentQuestionPublic`, also omitting key and explanation.
- **After submission:** Result review intentionally includes selected option, correct option, correctness and explanation.

### Step 7 — Submit diagnostic answers and evaluate

- **User action:** Selected four correct and four incorrect options, then clicked **See my skill analysis**. No answer key was consulted before submission.
- **Frontend/API:** `DiagnosticPage.handleSubmit()` → `submitDiagnostic()` → `POST /api/learners/12/diagnostic/26/submit`, JSON body `{ "answers": [{ "question_id": ..., "selected_option": ... }] }`; status `200`.
- **Backend:** `diagnostic.submit_learner_diagnostic()` validates learner ownership, assessment ID/type/completion, then calls `score_diagnostic()`.
- **Answer selections and post-submit results:**

| Question | Selected option | Result | Concept |
|---|---:|---|---|
| Which statement best describes a generative AI model? | 0 | Correct | `llm_fundamentals` |
| Which prompt is most likely to produce a consistent structured response? | 0 | Incorrect | `prompt_design` |
| What is the role of tokenization in a language-model workflow? | 0 | Correct | `tokenization` |
| What are embeddings most commonly used for in a RAG system? | 1 | Incorrect | `embeddings` |
| What does self-attention help a transformer model do? | 0 | Correct | `self_attention` |
| What is the primary purpose of retrieval in retrieval-augmented generation? | 1 | Incorrect | `grounding` |
| Which practice is most useful for evaluating an LLM application? | 0 | Correct | `evaluation` |
| What distinguishes an AI agent from a one-shot text generation call? | 1 | Incorrect | `tool_use` |

- **Scoring:** `score_diagnostic()` requires exactly one unique answer for every question, validates indices, then compares each selected index with stored `correct_option`. Four of eight were correct: `4/8 = 0.5`, returned as **50%**.
- **Database:** Assessment 26 updated with answers, score `0.5` and completion timestamp; eight diagnostic `SkillScore` records created.
- **AI interpretation:** `interpret_skill_results()` was called after deterministic scoring. OpenRouter returned a structured response that failed validation; `_interpretation_fallback()` supplied the `deterministic_fallback` interpretation and did not change the score.
- **Response/frontend:** Returned score, concept classifications and feedback; the UI navigated to `/analysis/12?assessment_id=26` with response in router state.

### Step 8 — Create and display the initial path

- **Frontend:** After diagnostic submission, `DiagnosticPage` requests `generateMyCurriculum()` again (existing matching curriculum returned as `persisted`) and `getLearningPath(12)`.
- **Request:** `GET /api/learners/12/learning-path`; status `200`.
- **Backend:** `learning_path.get_learning_path()` → `_persist_path()` → `generate_path_plan()` → `_serialize_path()`.
- **Database:** No path existed, so created `LearningPath` ID **14**, containing three selected topics and current index 0.
- **Initial path order:** Prompt Engineering Basics (current), Structured Outputs and JSON Formatting (pending), Iterative Prompt Refinement (pending). The path engine omitted already-mastered Generative AI Foundations (`llm_fundamentals=1.0`) from the sequence.
- **Adaptation evidence:** The first path item reason explicitly targeted weak `prompt_design`; that concept was represented in the diagnostic result and in the OpenRouter-generated curriculum tags.
- **Frontend:** `LearningPathPage` displayed the persisted path and learner summary.

### Step 9 — Load and complete the current topic

- **Frontend/API:** `LearningExperiencePage` loads `getCurrentTopic()` and `getLearningContent()`.
- **Requests:** `GET /api/learners/12/learning-path/current`; `GET /api/learners/12/topics/generated-1fa7157f5d114f1589ee4124ee076613/content`; both returned `200`.
- **Lesson generation:** `generate_learning_content()` called `_openrouter_content()` using learner goal/level/track, current topic/tags, diagnostic weak concepts, completed topics, recent assessment history and prerequisites. The UI marked the initial response **PERSONALIZED LESSON**; the service validates returned topic identity and required lesson fields before returning `source="openrouter"`.
- **User action:** Clicked **Mark topic complete**.
- **Frontend/API:** `LearningExperiencePage.handleComplete()` → `completeTopic()` → `POST /api/learners/12/topics/generated-1fa7157f5d114f1589ee4124ee076613/complete`; status `200`.
- **Backend/database:** `learning.complete_topic()` set `TopicProgress` to completed, advanced path index for assessment flow, and committed.
- **Next:** Same UI flow called `generateAssessment()` to create a topic assessment.

### Step 10 — Generate and read topic assessment

- **Request:** `POST /api/learners/12/topics/generated-1fa7157f5d114f1589ee4124ee076613/assessment/generate`; status `200`.
- **Backend:** `assessment.generate_topic_assessment()` → `_get_assessment_context()` checks ownership, path membership and completed progress → `generate_assessment_questions()` → `_openrouter_questions()` → `request_structured_json()`.
- **Safe LLM input summary:** Learner level, goal and target outcome; topic ID/title/description/concept tags/difficulty; weak concepts; exactly three MCQs; previous questions to avoid; `AssessmentQuestionSet` schema. The system instruction limits questions to the supplied topic and concepts and requires zero-based answer keys.
- **Output/validation:** Three topic-specific questions were returned and passed response-schema, concept-allowlist and duplicate-question checks. The questions do not match this generated topic's deterministic fallback templates; no provider error was logged for this request. The service's successful output source is `openrouter`.
- **Database:** Created topic `Assessment` ID **27**, associated with topic `generated-1fa7157f5d114f1589ee4124ee076613` (`Prompt Engineering Basics · 9-1`).
- **Read request:** `GET /api/learners/12/assessments/27`; status `200`; UI rendered public questions only.
- **Questions displayed:**
  1. Effective-prompt guideline; concept `prompt_design`.
  2. Purpose of few-shot examples; concept `few_shot_learning`.
  3. Technique for required JSON fields; concept `prompt_design`.

### Step 11 — Submit topic assessment and adapt state

- **User action:** Chose two incorrect and one correct answer and clicked **Submit assessment**.
- **Frontend/API:** `AssessmentPage.handleSubmit()` → `submitAssessment()` → `POST /api/learners/12/assessments/27/submit`; submitted question IDs and selected option indices; status `200`.
- **Selections/results (correct answers became visible only after submit):**

| Question | Selected answer | Correct answer after submission | Concept | Result |
|---|---|---|---|---|
| Effective prompt guideline | Use vague language to allow model creativity | Clearly state the desired output format and constraints | `prompt_design` | Incorrect |
| Purpose of few-shot examples | To increase the model's training time | To demonstrate the pattern or format the model should follow | `few_shot_learning` | Incorrect |
| JSON required fields | Providing a few-shot example of the expected JSON structure | Providing a few-shot example of the expected JSON structure | `prompt_design` | Correct |

- **Backend chain:** `assessment.submit_assessment()` → result/ownership validation → `apply_assessment_result()` → `score_assessment()` → skill/classification, weakness, topic progress, path adaptation, recommendation and optional remediation text → transaction commit → `AssessmentResultResponse`.
- **Result:** **1/3 correct; 33.3%**. `prompt_design` concept score 1/2 = 0.5 (developing); `few_shot_learning` 0/1 = 0 (weak).
- **LLM remediation:** `generate_remediation_aid()` attempted a structured OpenRouter call. Backend logged `OpenRouter returned empty structured content`; `_remediation_fallback()` supplied the explanation and targeted practice. The fallback did not control score or action.
- **Database:** Assessment 27 updated; `SkillScore` records updated/created; progress row ID 10 reset to remediation; two open weaknesses and recommendation ID 7 persisted; existing path ID 14 updated in the same transaction.
- **Frontend result:** Displayed 33.3%, concept performance, remediation recommendation, deterministic remediation wording and question feedback.

### Step 12 — Verify final adapted path

- **Request:** `GET /api/learners/12/learning-path` and `GET /api/learners/12/summary`; status `200`.
- **Observed:** The first topic remained current but now had `remediation` status and reason: “Your recent assessment shows this topic needs focused practice.” Recommendation: `remediate` Prompt Engineering Basics because of `few_shot_learning`.
- **Path order:** Still Prompt Engineering Basics → Structured Outputs and JSON Formatting → Iterative Prompt Refinement. Prerequisite order did not change.
- **Progress:** Topic was initially marked complete to unlock its quiz, then after the low result the row became `remediation` and the UI showed 0/3 topics completed.
- **Post-result content re-read:** A later direct reload of the current lesson returned `CURATED LESSON`; provider log recorded empty structured content and the curated fallback rendered. This was an additional read after the completed assessment, not a change to score/path state.

## 8. Complete API Sequence

`OPTIONS` requests in backend logs are CORS preflights, not business operations. Some effects made duplicate reads under React StrictMode. Table shows logical calls; duplicates are noted. Business requests in this journey used **GET and POST only**—no PUT, PATCH, or DELETE.

| Step | UI action | HTTP | Endpoint | Frontend function | Backend function | AI result / DB action |
|---:|---|---|---|---|---|---|
| 1 | Auth bootstrap | GET | `/api/auth/me` | `AuthProvider` load | auth current-user route | 200; user read |
| 2 | Register | POST | `/api/auth/register` | `RegisterPage.submit` → `AuthProvider.register` → `registerAccount` | `auth.register` | 201; create User |
| 3 | Check learner before onboarding | GET | `/api/learners/me` | dashboard/profile learner load | `learners.get_my_learner` | 404 expected; no learner yet |
| 4 | Load goals/tracks | GET | `/api/goals`, `/api/tracks` | `getGoals`, `getTracks` | `learners.list_goals`, `list_ai_tracks` | 200; catalogue reads |
| 5 | Select Generative AI/goal | — | **NO API CALL** | `ProfilePage.selectTrack`, `selectTrackGoal` | — | React state only |
| 6 | Submit profile | POST | `/api/learners` | `ProfilePage.handleSubmit` → `createLearner` | `learners.create_learner` | 201; create learner 12 and goal 15 |
| 7 | Generate curriculum | POST | `/api/curriculum/generate` | `generateMyCurriculum` | `curriculum.generate_my_curriculum` | OpenRouter structured output succeeded; create course 9 and six topics |
| 8 | Generate diagnostic | POST | `/api/learners/12/diagnostic/generate` | `generateDiagnostic` | `diagnostic.generate_learner_diagnostic` | OpenRouter validation failure; curated fallback; create assessment 26 |
| 9 | Submit diagnostic | POST | `/api/learners/12/diagnostic/26/submit` | `DiagnosticPage.handleSubmit` → `submitDiagnostic` | `diagnostic.submit_learner_diagnostic` → `score_diagnostic` | 200, 50%; update assessment/create skills; interpretation fallback |
| 10 | Reuse curriculum after diagnostic | POST | `/api/curriculum/generate` | `generateMyCurriculum` | `curriculum.generate_my_curriculum` | Existing matching course returned as `persisted`; no new generation |
| 11 | Create/display first path | GET | `/api/learners/12/learning-path` | `getLearningPath` | `learning_path.get_learning_path` → `_persist_path` → `generate_path_plan` | Create path 14; deterministic |
| 12 | Learner summary | GET | `/api/learners/12/summary` | `getLearnerSummary` | `learners.get_learner_summary` | Read; 200 |
| 13 | Load current topic | GET | `/api/learners/12/learning-path/current` | `getCurrentTopic` | `learning.get_current_topic` | Read; 200; duplicate effect observed |
| 14 | Load lesson | GET | `/api/learners/12/topics/{topic_id}/content` | `getLearningContent` | `learning.get_topic_content` → `generate_learning_content` | Initial personalized OpenRouter lesson; later reload used curated fallback |
| 15 | Complete lesson | POST | `/api/learners/12/topics/{topic_id}/complete` | `handleComplete` → `completeTopic` | `learning.complete_topic` | Update progress/path cursor; 200 |
| 16 | Generate topic quiz | POST | `/api/learners/12/topics/{topic_id}/assessment/generate` | `handleComplete` → `generateAssessment` | `assessment.generate_topic_assessment` → `generate_assessment_questions` | OpenRouter structured topic questions; create assessment 27 |
| 17 | Load pending quiz | GET | `/api/learners/12/assessments/27` | `AssessmentPage` effect → `getAssessment` | `assessment.get_assessment` | 200; public questions only; duplicate GET observed |
| 18 | Submit topic quiz | POST | `/api/learners/12/assessments/27/submit` | `AssessmentPage.handleSubmit` → `submitAssessment` | `assessment.submit_assessment` → `apply_assessment_result` | 200, 33.3%; skill/weakness/recommendation/progress/path updates; remediation fallback |
| 19 | Display adapted path | GET | `/api/learners/12/learning-path`, `/api/learners/12/summary` | `LearningPathPage` effects | path/summary routes | 200; updated path and summary |

## 9. Complete Frontend Call Chain

```text
Register form submit
  → frontend/src/App.jsx: RegisterPage.submit()
  → frontend/src/auth.jsx: AuthProvider.register()
  → frontend/src/api/client.js: registerAccount()
  → POST /api/auth/register
  → backend/app/routers/auth.py: register()
  → hash_password() + User INSERT
  → frontend stores auth state/token; token omitted

Track/goal selection
  → frontend/src/App.jsx: ProfilePage.selectTrack()/selectTrackGoal()
  → React state only; NO network request

Begin diagnostic
  → ProfilePage.handleSubmit()
  → frontend/src/api/client.js: createLearner()
  → POST /api/learners
  → Learner + LearningGoal persisted
  → DiagnosticPage mount
      → generateMyCurriculum() → POST /api/curriculum/generate
      → generateDiagnostic(12) → POST /api/learners/12/diagnostic/generate
  → public diagnostic questions stored in UI state and rendered

Diagnostic submit
  → DiagnosticPage.handleSubmit()
  → submitDiagnostic() → POST /api/learners/12/diagnostic/26/submit
  → response contains deterministic score and feedback
  → generateMyCurriculum() returns persisted matching course
  → getLearningPath(12) → GET path, creates first path
  → navigate /analysis/12?assessment_id=26

Path and topic quiz
  → LearningPathPage → getLearningPath()/getLearnerSummary()
  → LearningExperiencePage → getCurrentTopic()/getLearningContent()
  → handleComplete() → completeTopic() POST complete
  → generateAssessment() POST topic assessment
  → AssessmentPage → getAssessment() GET public questions
  → handleSubmit() → submitAssessment() POST answers
  → response rendered; backend commits updated learner state
  → LearningPathPage reloads path and summary
```

## 10. Complete Backend Call Chain

### Curriculum

```text
POST /api/curriculum/generate
  → curriculum.generate_my_curriculum()
  → require_user / learner access
  → persist_curriculum()
  → no matching persisted course
  → generate_curriculum() → _openrouter_curriculum()
  → request_structured_json()
  → OpenRouter JSON-object response
  → Pydantic GeneratedCurriculum + goal/level/track checks
  → GeneratedCourse + owner Topics + prerequisite edges
  → response source="openrouter"
```

### Diagnostic

```text
POST /api/learners/{learner_id}/diagnostic/generate
  → diagnostic.generate_learner_diagnostic()
  → learner lookup + ensure_learner_access()
  → generate_diagnostic() → _openrouter_questions()
  → request_structured_json() → schema validation failure
  → _fallback_questions() → curated question set
  → Assessment INSERT/commit
  → public response omits answer key and explanations

POST /api/learners/{learner_id}/diagnostic/{assessment_id}/submit
  → diagnostic.submit_learner_diagnostic()
  → ownership/type/completion and request validation
  → score_diagnostic() compares selected index to correct_option
  → Assessment answers/score/completed_at update
  → SkillScore create/update per concept
  → interpret_skill_results() → provider structured validation failure
  → deterministic interpretation fallback
  → feedback persistence + DiagnosticSubmitResponse
```

### Topic assessment and path

```text
POST /api/learners/{learner_id}/topics/{topic_id}/assessment/generate
  → assessment.generate_topic_assessment()
  → _get_assessment_context() checks owner, path membership, completed progress
  → generate_assessment_questions() → _openrouter_questions()
  → request_structured_json() → AssessmentQuestionSet validation,
    concept allowlist and non-repetition checks
  → Assessment INSERT/commit
  → _public_response() strips correct_option/explanation

POST /api/learners/{learner_id}/assessments/{assessment_id}/submit
  → assessment.submit_assessment()
  → association/ownership and submission validation
  → apply_assessment_result()
      → score_assessment() exact selected-option comparison
      → _update_skill() + classify_score()
      → _update_weakness()
      → TopicProgress update
      → _adapt_path() → deterministic generate_path_plan()
      → _recommendation()
      → generate_remediation_aid() → empty structured provider response
        → deterministic remediation fallback
      → Recommendation persistence and transaction commit
  → AssessmentResultResponse returned to frontend

GET /api/learners/{learner_id}/learning-path
  → learning_path.get_learning_path()
  → ensure_learner_access()
  → no existing path: _persist_path()
  → generate_path_plan() reads skills/progress/assessments/goal/experience
  → validate_path_payload()
  → LearningPath INSERT / serialize response
```

## 11. Complete LLM Call Chain

All calls use `backend/app/services/ai_provider.py::request_structured_json()`: OpenAI-compatible Chat Completions request to the configured OpenRouter base URL/model, with `response_format={"type":"json_object"}`, system instructions, JSON user payload and Pydantic response validation. The provider timeout is configured in `backend/app/config.py`; no application-level retry loop was observed.

| AI operation | Caller/service | Safe input summary | Schema/output | Observed result |
|---|---|---|---|---|
| Curriculum | `curriculum.generate_curriculum()` → `_openrouter_curriculum()` | learner goal/outcome/level/track, prerequisites, topic catalogue, skill/history fields, required 4–8 modules | `GeneratedCurriculum` | **Success.** Stored `generation_source="openrouter"`; course 9 with six modules |
| Diagnostic questions | `diagnostic.generate_diagnostic()` → `_openrouter_questions()` | learner context, course topics, allowed concepts, history, eight MCQs and internal key metadata | `DiagnosticQuestionSet` | **Invalid structured response.** Validation warning; `_fallback_questions()` used |
| Diagnostic interpretation | `interpret_skill_results()` after score | learner context, deterministic 50% and concept classifications | `LearningInterpretation`; may explain but must not alter score | **Invalid structured response.** `_interpretation_fallback()` used |
| Initial lesson | `generate_learning_content()` → `_openrouter_content()` | learner context/weak concepts, current topic, prerequisites, progress and recent assessments | `LearningContent` | **Success observed in UI:** response labeled `PERSONALIZED LESSON`; content passed topic/required-field validation |
| Topic questions | `generate_assessment_questions()` → `_openrouter_questions()` | learner and goal, current topic/concepts/difficulty, weak concepts, previous questions, three-MCQ requirement | `AssessmentQuestionSet` | **Success observed:** topic-specific questions differ from code fallback templates; no provider failure logged |
| Remediation aid | `generate_remediation_aid()` after deterministic action | learner, topic, weak concepts, deterministic score and action | `RemediationAid` | **Empty structured response.** `_remediation_fallback()` used |
| Later lesson reload | `generate_learning_content()` → `_openrouter_content()` | current topic plus post-assessment skill/weakness/history | `LearningContent` | **Empty structured response.** `curated_fallback` rendered as `CURATED LESSON` |

### LLM request and response notes

- No API key or raw proprietary prompt is reproduced.
- Curriculum context initially had no assessment/skill/weakness history; it contained the chosen track, beginner level, goal and target outcome.
- Diagnostic response did not validate, so there is no successful diagnostic LLM output to report. The eight visible questions came from the curated fallback.
- Topic assessment response was a three-question structured set with topic concepts and hidden answer metadata. The set returned to the browser exposed only public fields.
- Content and remediation responses are validated by their Pydantic schemas and additional service-level checks. Provider exceptions/empty content/validation failures are caught by each service and return its labelled fallback.
- Assessment score, concept scores, skill state, recommendation action and path ranking were not produced by the LLM.

## 12. Assessment Generation

### Diagnostic assessment 26

- `POST /api/learners/12/diagnostic/generate`.
- `generate_diagnostic()` tried `_openrouter_questions()`; Pydantic structured validation failed; curated fallback returned `source="curated_fallback"`.
- Persisted `Assessment` ID **26**, type `diagnostic`, eight MCQs.
- Public response: assessment ID and question IDs/text/options; no `correct_option` or explanation.

### Topic assessment 27

- `POST /api/learners/12/topics/generated-1fa7157f5d114f1589ee4124ee076613/assessment/generate`.
- `generate_assessment_questions()` returned a validated OpenRouter question set, source `openrouter`.
- Persisted `Assessment` ID **27**, type `topic`, attached to Prompt Engineering Basics.
- Public response included three question IDs/text/options/concepts/difficulty and source; answer key remained server-side.

## 13. Assessment Evaluation

**Evaluation type: deterministic backend logic, not LLM grading.**

For diagnostic and topic assessments, the server compares each submitted selected-option index to the stored `correct_option`. It validates full answer coverage, duplicate IDs and option range; no AI call determines correctness or changes the score.

```text
User answer
  → POST submission API
  → request/ownership validation
  → deterministic selected_option == correct_option comparison
  → score = correct_count / total_questions
  → per-concept scores and classifications
  → persisted learner state
```

Diagnostic: 4/8 = **50%**. Topic assessment: 1/3 = **33.3%**. The interpretation/remediation LLM attempts were ancillary prose only; they cannot alter score/action.

## 14. Skill Analysis

Diagnostic classification in the diagnostic flow is `<0.50 weak`, `<0.75 developing`, otherwise strong. Each diagnostic concept had one question and no prior row, so its initial stored score equaled that question’s result. Diagnostic rows are in `skill_scores`.

| Concept | Before diagnostic | Diagnostic latest | After topic quiz | Final stored value | Final classification / record |
|---|---:|---:|---:|---:|---|
| `llm_fundamentals` | None | 1.0 | — | 1.0 | strong; row 87 |
| `prompt_design` | None | 0.0 | 0.5 across two quiz questions | 0.2 | weak stored skill; row 88 |
| `tokenization` | None | 1.0 | — | 1.0 | strong; row 89 |
| `embeddings` | None | 0.0 | — | 0.0 | weak; row 90 |
| `self_attention` | None | 1.0 | — | 1.0 | strong; row 91 |
| `grounding` | None | 0.0 | — | 0.0 | weak; row 92 |
| `evaluation` | None | 1.0 | — | 1.0 | strong; row 93 |
| `tool_use` | None | 0.0 | — | 0.0 | weak; row 94 |
| `few_shot_learning` | None | — | 0.0 | 0.0 | weak; row 95 |

For an existing topic-assessment skill with evidence, `_update_skill()` uses `round(0.6 * previous_score + 0.4 * latest_score, 4)`. `prompt_design` therefore moved from 0.0 to `0.6*0.0 + 0.4*0.5 = 0.2`. `few_shot_learning` had no prior row and stored its latest score 0.0 directly. The final learner summary displayed **44% skill readiness**; that summary metric is distinct from the latest quiz’s 33.3%.

## 15. Weakness Identification

- Diagnostic creates classified `SkillScore` values but does not create `Weakness` rows.
- Topic route calls `assessment_result_service._update_weakness()`.
- A weakness is open when the latest concept score is below 0.50 **or** the updated stored skill score is below 0.50.
- Severity is high when latest concept score is below 0.50; otherwise medium when stored skill remains below threshold.
- Observed rows:
  - `weaknesses.id=6`: `prompt_design`, topic generated-1fa…, score evidence 0.5, stored skill 0.2, **medium/open**.
  - `weaknesses.id=7`: `few_shot_learning`, score 0.0, **high/open**.
- Flow: deterministic assessment result → concept scores → classification → persisted weakness rows → remediation recommendation.

## 16. Recommendation Generation

`assessment_result_service._recommendation()` deterministically selects action from overall score:

- `<60`: `remediate`
- `60–<80`: `practice`
- `>=80`: `continue`

The 33.3% quiz selected `remediate`. Recommendation ID **7** targets the current generated topic and states that the weakness in `few_shot_learning` holds the topic for remediation. `generate_remediation_aid()` may generate optional explanation/practice prose; its OpenRouter response was empty, so deterministic remediation text was returned. The recommendation action and score remained application-controlled.

## 17. Learning Path Generation

**Path generation/ranking: deterministic.** The LLM generated the curriculum topics, not the path order.

- After diagnostic submit the frontend called `GET /api/learners/12/learning-path`. No path existed, so `get_learning_path()` called `_persist_path()` and `generate_path_plan()` and created path ID **14**.
- Inputs include learner track, goal and experience; active learner-owned topics and their concept tags; prerequisite edges; skill scores; topic progress; completed/mastered topics; assessment evidence.
- The engine selects relevant topics, skips mastered/completed topics where applicable, includes unmet prerequisite constraints, ranks with deterministic priority/relevance logic, and serializes the path.
- The initial course was LLM-generated. The path engine omitted the already-mastered Generative AI Foundations prerequisite (diagnostic `llm_fundamentals=1.0`) and placed Prompt Engineering Basics first because it matched weak `prompt_design`.
- Topic submission automatically invokes `_adapt_path()` in `apply_assessment_result()`; the frontend does not issue a separate path mutation request. The existing path JSON/status/reason are updated within the assessment transaction.
- The weak quiz did not reorder the three path items; it changed the current topic status to remediation and added focused-practice reason/recommendation. Prerequisite ordering among remaining topics stayed unchanged.
- Path ID **14** was returned to the frontend on its next GET and displayed with current status, reasons, strong/weak concepts and recommendation.

## 18. Before vs After Learning Path

There was no saved path before the first GET after diagnostic submission.

| Topic | Before any assessment/path | After diagnostic (initial path) | After topic assessment | Reason |
|---|---|---|---|---|
| Prompt Engineering Basics · 9-1 | No path | First/current; reason targets weak prompt design | Still first/current; status remediation | Quiz score 33.3%; few-shot learning weak; recommendation holds topic for remediation |
| Structured Outputs and JSON Formatting · 9-1 | No path | Second/pending | Second/pending | Prerequisite ordering retained |
| Iterative Prompt Refinement · 9-1 | No path | Third/pending; prompt design target | Third/pending | Prerequisite ordering retained |
| Generative AI Foundations · 9-1 | No path | Excluded from sequence as mastered prerequisite | Still excluded | Diagnostic `llm_fundamentals` score 1.0 |

Weak `prompt_design` was prioritized by the initial path; after the topic quiz, `few_shot_learning` was added to needs-attention and the current topic was explicitly held for remediation. The completed-topic action was reversed into `remediation` after the low assessment result; final progress returned to 0/3, not mastered. This learner’s course, skills, path, progress and recommendation are owned by learner 12.

## 19. Database Changes

All mutations below resulted from UI/API actions. The inspection used a SQLite read-only connection.

| Model/table | Operation | Observed state |
|---|---|---|
| `users` | CREATE | Registered user ID 9; password persisted as hash |
| `learners` | CREATE | Learner ID 12; beginner, `generative_ai`, chosen goal/outcome |
| `learning_goals` | CREATE | Active goal ID 15 |
| `generated_courses` | CREATE | Course ID 9, `generation_source="openrouter"` |
| `topics` | CREATE | Six LLM-generated learner-owned curriculum topics with concepts |
| `topic_prerequisites` | CREATE | Prerequisite relationships for generated topics |
| `assessments` | CREATE / UPDATE | Diagnostic 26 and topic assessment 27; submissions update answers, score, completion and feedback |
| `skill_scores` | CREATE / UPDATE | Rows 87–95; eight diagnostic concepts and topic scores for prompt design/few-shot learning |
| `learning_paths` | CREATE / UPDATE | Path 14 created after diagnostic, updated by topic submission |
| `topic_progress` | CREATE / UPDATE | Row 10; lesson completion followed by remediation, mastery 0.3333 |
| `weaknesses` | CREATE | Rows 6 (`prompt_design`, medium/open) and 7 (`few_shot_learning`, high/open) |
| `recommendations` | CREATE | Row 7, action `remediate`, target current topic |

## 20. AI vs Deterministic Responsibility

### AI / LLM responsibilities observed

- Curriculum topic proposal: successful structured OpenRouter response.
- Diagnostic MCQ generation: request made, response failed validation; fallback used.
- Diagnostic interpretation: request made, response failed validation; deterministic fallback used.
- Initial lesson content: successful personalized response observed in UI.
- Topic-assessment MCQs: successful topic-specific structured response.
- Remediation prose: request returned empty structured content; deterministic fallback used.
- Later lesson re-read: empty structured content; curated fallback used.

### Deterministic backend responsibilities

- Authentication, ownership, schema/request checks and answer-key protection.
- Diagnostic/topic scoring, concept aggregation/classification and skill updates.
- Weakness thresholds, remediation/practice/continue selection, topic progress updates.
- Path topic selection, mastery/prerequisite constraints, ranking, adaptation and persistence.
- Fallback curriculum/questions/content/interpretation/remediation when provider results are unavailable or invalid.

### Database responsibilities

Persist user, learner profile/goal, generated course/topics/prerequisites, assessments/answers/results, skills, path, progress, weaknesses and recommendations.

### Frontend responsibilities

Collect profile/track inputs, hold selection state, call APIs, render public questions, collect answers, navigate, and display returned analysis/path. Frontend does not compute authoritative score or see answer keys pre-submit.

### Architecture summary

Hybrid: successful LLM calls supplied curriculum and lesson/question content; service schemas/semantic checks gate those responses. Deterministic backend logic remains authoritative for evaluation and adaptive state. Invalid/empty LLM responses fall back without changing the deterministic score/path decision.

## 21. Error Handling / Fallback

- **Configured key:** backend attempted real OpenRouter requests. The key itself is not shown.
- **Observed structured failures:** diagnostic question generation and diagnostic interpretation logged structured validation failure; remediation and later content reload logged empty structured content.
- **Successful operations:** curriculum row persisted with `generation_source="openrouter"`; initial lesson UI source was `PERSONALIZED LESSON`; topic question content was not present in the deterministic fallback bank/templates and no provider error was logged, consistent with the service returning source `openrouter`.
- **Fallback behavior:** services catch provider/schema/semantic failures and return labelled fallback outputs; API requests still returned successful `200` responses.
- **Validation:** provider parses JSON against the requested Pydantic model; curriculum checks learner goal/level/track; diagnostic checks concepts against available concepts; topic assessment checks allowed concepts and repeated question fingerprints; lesson checks topic identity and required fields.
- **Missing key:** `request_structured_json()` raises `AIProviderError` if key is falsey; service callers use their fallback. Missing-key behavior was inspected, not induced.
- **Retries:** no service-level retry loop was observed; provider timeout is configured as 30 seconds. No retry count was established from runtime logs.
- **Application/API errors:** pre-profile `GET /api/learners/me` returned expected `404`; assessment generation/submissions, path and other business requests succeeded. Provider failures did not become user-facing API failures.
- **No intentionally induced provider outage or malformed payload** beyond the real invalid/empty provider responses observed.

## 22. Security / Ownership Checks

- Registration hashes password and returns auth response; password, test email, token and API key are omitted.
- Frontend attaches stored bearer authentication to API calls.
- Learner-scoped routes call `ensure_learner_access`; curriculum route requires an authenticated user.
- Diagnostic assessment retrieval/submission is scoped to learner and assessment, with type/completion checks.
- Topic assessment checks learner ownership, topic membership in that learner's path, and completion before generation; submit verifies assessment/learner association and pending state.
- Public question response schemas omit `correct_option` and explanations; result/review fields are returned after submission only.
- No cross-user access attempt was made in the browser journey.

## 23. Final Learner State

| Field | Final value |
|---|---|
| Learner ID | 12 |
| Track | `generative_ai` / Generative AI |
| Goal | Learn reliable prompt and output patterns |
| Target outcome | Build a reliable structured-output assistant |
| Experience | beginner |
| Course | ID 9; OpenRouter-generated; six topics |
| Diagnostic | ID 26; 8 questions; 4 correct, 4 incorrect; 50% |
| Topic assessment | ID 27; 3 questions; 1 correct, 2 incorrect; 33.3% |
| Strong concepts | `llm_fundamentals`, `tokenization`, `self_attention`, `evaluation` |
| Developing latest concept result | `prompt_design` at 50% on topic assessment (stored smoothed skill is 0.2/weak) |
| Weak concepts | `prompt_design`, `embeddings`, `grounding`, `tool_use`, `few_shot_learning` |
| Weakness records | `prompt_design` medium/open; `few_shot_learning` high/open |
| Recommendation | `remediate` Prompt Engineering Basics; focus `few_shot_learning` |
| Learning path | ID 14; three items; current item in remediation |
| First recommended topic | Prompt Engineering Basics · 9-1 |
| Reason | Current topic matches weak prompt design; topic quiz also found weak few-shot learning, so remediation holds it for focused practice |
| Summary readiness | 44% displayed |
| Final topic progress | 0/3 complete; assessment moved lesson from completed to remediation |

## 24. Expected vs Actual Result

| Expected behavior | Actual |
|---|---|
| Fresh account/learner and selectable AI track | PASS; new account and learner 12; Generative AI selected |
| AI curriculum generation | PASS; real OpenRouter structured output persisted as source `openrouter` |
| Diagnostic generation and hidden keys | PASS WITH FALLBACK; 8 public questions, no keys before submission |
| Deliberate mixed diagnostic score | PASS; 50% |
| Deterministic scoring confirmed | PASS; backend exact answer comparison, not LLM grading |
| Skill persistence/classification | PASS; 4 strong and 4 weak diagnostic concepts; topic quiz updated/added skills |
| Weak-topic detection and recommendation | PASS; prompt design/few-shot learning weaknesses and remediation recommendation |
| Learning path reflects diagnostic and quiz | PASS WITH OBSERVATIONS; initial path targeted weak prompt design; quiz retained prerequisite order but marked current topic remediation |
| Real OpenRouter use | PASS WITH OBSERVATIONS; curriculum, initial lesson and topic questions successful; several other calls failed validation/returned empty and fell back |
| No PUT/PATCH assumption | PASS; observed business requests were GET/POST only |

## 25. Historical Test Result — Learner 12

**PASS WITH OBSERVATIONS.**

The UI journey completed with fresh learner 12. OpenRouter generated the personalized curriculum and topic question set, while the diagnostic generator, diagnostic interpretation and remediation/content reload used fallbacks after invalid or empty structured responses. The diagnostic scored 50%; the topic assessment scored 33.3%, created two weaknesses and a remediation recommendation, and updated the path. Path generation and evaluation remained deterministic.

## 26. Evidence

- Browser flow: registration → `/dashboard` → `/profile` → `/diagnostic/12` → `/analysis/12?assessment_id=26` → `/learning-path/12` → `/learn/12` → `/assessment/12/27` → final `/learning-path/12`.
- Backend access logs recorded request methods/statuses listed above, plus CORS OPTIONS preflights.
- Provider logs recorded structured validation failures for diagnostic generation/interpretation and empty structured content for remediation and the later content reload.
- Read-only database inspection confirmed learner 12/user 9, goal 15, OpenRouter course 9, assessments 26/27, path 14, skills 87–95, topic progress 10, weaknesses 6/7 and recommendation 7.
- Diagnostic UI result: 8 questions, 50%, four strong and four weak concepts.
- Topic result UI: 1/3 correct, 33.3%, `prompt_design` 50% and `few_shot_learning` 0%; remediation output labelled deterministic.
- Pre-submit question displays contained no answer key; review responses after submit showed correctness and explanations.
- API key, email, password and bearer token were not included in this report.
- No production code was changed.

## Final Real AI Verification

This final rerun used fresh learner **14** on the existing **Generative AI** track, with beginner experience, the goal “Build an LLM-powered application,” and the outcome “Ship a validated assistant using a trusted knowledge source.” The configured model was `openrouter/free`; the API key was configured and was not exposed.

| AI Feature | OpenRouter Called | Response Validated | Real AI Used | Fallback |
|---|---|---|---|---|
| Curriculum — `backend/app/services/curriculum_service.py::_openrouter_curriculum` | Yes; `POST /api/curriculum/generate` | Yes; persisted `generation_source=openrouter` | Yes | No |
| Diagnostic questions — `backend/app/services/diagnostic_service.py::_openrouter_questions` | Yes; `POST /api/learners/14/diagnostic/generate` | Yes; 8 questions passed the strict response schema and concept-catalog checks | Yes | No |
| Learning content — `backend/app/services/content_service.py::_openrouter_content` | Yes; topic-content GET returned HTTP 429 | No response payload to validate | No | Yes; curated content |
| Topic assessment questions — `backend/app/services/assessment_service.py::_openrouter_questions` | Yes; assessment-generation POST returned HTTP 429 | No response payload to validate | No | Yes; deterministic question bank |
| Interpretation — `backend/app/services/learning_ai_service.py::interpret_skill_results` | Yes; diagnostic submission returned HTTP 429 for this operation | No response payload to validate | No | Yes; deterministic interpretation |
| Remediation — `backend/app/services/learning_ai_service.py::generate_remediation_aid` | Yes; assessment submission returned HTTP 429 for this operation | No response payload to validate | No | Yes; deterministic remediation |

### Structured-output changes and root cause

- `backend/app/services/ai_provider.py::request_structured_json` now sends a strict JSON Schema response format derived from the actual Pydantic response model, sets `additionalProperties=false` and requires each declared object property, and still performs application-side Pydantic validation. Prompts explicitly prohibit prose, Markdown, code fences, unsupported fields, and incorrect field types. A single real-OpenRouter retry at temperature zero is limited to empty, malformed, or schema-invalid responses; validation and fallback remain enabled.
- Safe diagnostics include the operation, configured model, HTTP status, attempt, response type, finish reason, parser/validation error, missing fields, and unexpected fields. They do not include response bodies, credentials, authorization headers, or learner secrets.
- Prior live traces identified two distinct failure causes. With a 300-token budget, OpenRouter returned no message content and `finish_reason=length`; the opt-in structured-output smoke test passed after allowing 1,200 tokens. A diagnostic attempt also returned a 17-character plain-text response (`finish_reason=stop`), which failed JSON parsing at line 1, column 1. The literal response was not retained or logged. The diagnostic/content/interpretation/remediation budgets were increased where needed, and current diagnostic generation passed the strict schema.
- In the final full UI run, the configured free-model route subsequently returned HTTP 429 for interpretation, content, topic-question generation, and remediation. These were genuine provider rate-limit responses, not schema-validation failures; the existing deterministic fallbacks were used and reported as such.

### End-to-end result and learner state

- UI registration succeeded; learner 14 selected Generative AI, beginner, the LLM application goal, and the stated outcome. No password, email, or token is included here.
- Curriculum generation returned HTTP 200 and persisted course 11 with `generation_source=openrouter`; the generated curriculum contained six topics.
- Diagnostic generation returned HTTP 200 with eight learner-facing questions and no answer keys. Submission returned HTTP 200 and scored **50%**. Deterministic comparison updated concept skills; four concepts were strong and four needed attention. Interpretation fell back after HTTP 429.
- The initial deterministic path had five selected topics from the six-topic course. It included the diagnostic's weak concepts in topic rationale while preserving prerequisite order.
- The lesson-content request returned HTTP 200 using curated fallback content after the provider returned HTTP 429. Completing the first topic succeeded.
- Topic assessment generation returned HTTP 200 using the deterministic question bank after HTTP 429. Submission returned HTTP 200 at **33.3%** (1/3). Deterministic scoring classified `generative_models` and `ai_fundamentals` as weak and `llm_fundamentals` as strong. Remediation returned the deterministic fallback with explanation, alternative explanation, example, practice, and next action.
- The final persisted path was path 15, readiness was **45%**, latest assessment was **33.3%**, and the current topic remained “Introduction to Generative AI and LLMs · 11-1” with a remediation reason explicitly tied to the recent assessment. The path therefore reflected the result; score, skill/weakness changes, and path adaptation remained deterministic.

### Final AI and test status

- **Live OpenRouter smoke:** passed after enabling strict JSON Schema output with sufficient generation budget.
- **Full Test Case 1:** completed in the UI with learner 14; **partial real-AI result** because OpenRouter rate-limited four later AI operations. No fallback is represented as real AI.
- **Prior successful behavior preserved:** the preceding report documents a real OpenRouter topic-question response; the final run's topic-question fallback was caused by the observed HTTP 429.
- Mocked tests cover valid/invalid diagnostic output, malformed JSON, missing and unexpected fields, invalid concept identifiers, valid/invalid interpretation, valid/invalid remediation, and valid/invalid learning content. They do not call OpenRouter.
- Backend suite with the live key disabled before test collection: **67 passed, 1 skipped, 1 warning**. The skip is the opt-in live test; the warning is the existing Starlette `TestClient` deprecation.
- Opt-in live OpenRouter JSON Schema smoke test: **passed**. Frontend `npm run build`: **passed** (43 modules). `git diff --check`: **passed**.
- No commits or pushes were made.

### Final run API timeline

| UI action | Method and endpoint | Result |
|---|---|---|
| Register fresh account | `POST /api/auth/register` | 201; credentials omitted |
| Load track and goal choices | `GET /api/tracks`, `GET /api/goals` | 200 |
| Create learner profile | `POST /api/learners` | 201; learner 14, Generative AI, beginner |
| Generate curriculum | `POST /api/curriculum/generate` | 200; course 11, `generation_source=openrouter` |
| Generate diagnostic | `POST /api/learners/14/diagnostic/generate` | 200; 8 questions; real AI output validated |
| Submit diagnostic | `POST /api/learners/14/diagnostic/29/submit` | 200; 50%; interpretation fallback after provider 429 |
| Read initial learning path | `GET /api/learners/14/learning-path` | 200; path adapted to diagnostic skills |
| Load current topic and lesson | `GET /api/learners/14/learning-path/current`, `GET /api/learners/14/topics/{topic_id}/content` | 200; curated lesson after provider 429 |
| Complete current topic | `POST /api/learners/14/topics/{topic_id}/complete` | 200 |
| Generate topic assessment | `POST /api/learners/14/topics/{topic_id}/assessment/generate` | 200; deterministic question bank after provider 429 |
| Retrieve and submit topic assessment | `GET /api/learners/14/assessments/30`, `POST /api/learners/14/assessments/30/submit` | 200; 1/3 correct; deterministic remediation after provider 429 |
| Read final path and summary | `GET /api/learners/14/learning-path`, `GET /api/learners/14/summary` | 200; path 15 remains focused on the weak current topic |

## Source Code Map

| Responsibility | File | Function/class | HTTP route | Method |
|---|---|---|---|---|
| UI startup/routing | `frontend/src/main.jsx`, `frontend/src/App.jsx` | `App`, `ProtectedRoute` | Browser routes | — |
| Registration/auth | `frontend/src/App.jsx`, `frontend/src/auth.jsx` | `RegisterPage.submit`, `AuthProvider.register` | `/api/auth/register` | POST |
| HTTP client | `frontend/src/api/client.js` | `request`, `registerAccount`, `createLearner`, generators/submission functions | `/api/*` | GET/POST |
| Track and goal options | `frontend/src/App.jsx`, `backend/app/routers/learners.py`, `backend/app/track_catalog.py` | `getTracks`, `getGoals`, `selectTrack`, `selectTrackGoal`; `list_ai_tracks`, `list_goals` | `/api/tracks`, `/api/goals` | GET |
| Learner profile | `frontend/src/App.jsx`, `backend/app/routers/learners.py` | `ProfilePage.handleSubmit`, `create_learner` | `/api/learners` | POST |
| Authentication | `backend/app/routers/auth.py`, `backend/app/security.py` | `register`, `hash_password`, `create_access_token` | `/api/auth/register` | POST |
| Curriculum | `backend/app/routers/curriculum.py`, `backend/app/services/curriculum_service.py` | `generate_my_curriculum`, `persist_curriculum`, `generate_curriculum`, `_openrouter_curriculum`, `_fallback_curriculum` | `/api/curriculum/generate` | POST |
| Diagnostic generation/scoring | `frontend/src/App.jsx`, `backend/app/routers/diagnostic.py`, `backend/app/services/diagnostic_service.py` | `DiagnosticPage`, `generate_learner_diagnostic`, `generate_diagnostic`, `_openrouter_questions`, `_fallback_questions`, `score_diagnostic`, `submit_learner_diagnostic` | `/api/learners/{id}/diagnostic/generate`, `/diagnostic/{assessment_id}/submit` | POST |
| Diagnostic result | `frontend/src/App.jsx`, `backend/app/routers/diagnostic.py` | `AnalysisPage`, `get_diagnostic_result` | `/api/learners/{id}/diagnostic/{assessment_id}` | GET (not direct-loaded during this run) |
| Skill analysis/interpretation | `backend/app/routers/learners.py`, `backend/app/services/learning_ai_service.py` | `build_skill_analysis`, `interpret_skill_results` | `/api/learners/{id}/summary`, diagnostic submit | GET; POST |
| Lesson/current topic | `frontend/src/App.jsx`, `backend/app/routers/learning.py`, `backend/app/services/content_service.py` | `LearningExperiencePage`, `get_current_topic`, `get_topic_content`, `generate_learning_content`, `_openrouter_content`, `_fallback_content` | `/api/learners/{id}/learning-path/current`, `/topics/{topic_id}/content` | GET |
| Topic completion | `frontend/src/App.jsx`, `backend/app/routers/learning.py` | `handleComplete`, `complete_topic` | `/topics/{topic_id}/complete` | POST |
| Topic quiz generation | `frontend/src/App.jsx`, `backend/app/routers/assessment.py`, `backend/app/services/assessment_service.py` | `generateAssessment`, `generate_topic_assessment`, `generate_assessment_questions`, `_openrouter_questions`, `_fallback_questions` | `/topics/{topic_id}/assessment/generate` | POST |
| Topic quiz retrieval/submission | `frontend/src/App.jsx`, `backend/app/routers/assessment.py`, `backend/app/services/assessment_result_service.py` | `AssessmentPage`, `get_assessment`, `submit_assessment`, `apply_assessment_result`, `score_assessment` | `/assessments/{id}`, `/assessments/{id}/submit` | GET; POST |
| Skill/weakness/recommendation/path adaptation | `backend/app/services/assessment_result_service.py` | `_update_skill`, `classify_score`, `_update_weakness`, `_recommendation`, `_adapt_path` | Called by submit route | POST submission |
| Learning path | `frontend/src/App.jsx`, `backend/app/routers/learning_path.py`, `backend/app/services/path_engine.py` | `LearningPathPage`, `get_learning_path`, `_persist_path`, `generate_path_plan`, `_topic_priority`, `_topic_reason` | `/api/learners/{id}/learning-path` | GET |
| OpenRouter provider | `backend/app/services/ai_provider.py` | `request_structured_json`, `AIProviderError` | Outbound Chat Completions | — |
| Schemas/models | `backend/app/schemas.py`, `backend/app/models.py` | Public assessment/result schemas; `User`, `Learner`, `GeneratedCourse`, `Topic`, `Assessment`, `SkillScore`, `LearningPath`, `TopicProgress`, `Weakness`, `Recommendation` | — | — |
| Ownership guard | `backend/app/security.py` | `get_optional_user`, `require_user`, `ensure_learner_access` | Route dependencies | — |

## AI Integration Map

| AI feature | File/function | Trigger | LLM called? | Observed result/fallback |
|---|---|---|---|---|
| Personalized curriculum | `curriculum_service._openrouter_curriculum` | `POST /api/curriculum/generate` | Yes | Valid OpenRouter curriculum persisted |
| Diagnostic questions | `diagnostic_service._openrouter_questions` | Diagnostic generate POST | Yes | Schema validation failed; curated questions |
| Diagnostic interpretation | `learning_ai_service.interpret_skill_results` | Diagnostic submit POST | Yes | Validation failed; deterministic interpretation |
| Personalized lesson | `content_service._openrouter_content` | Current topic content GET | Yes | Initial personalized lesson; later empty response used curated fallback |
| Topic questions | `assessment_service._openrouter_questions` | Topic assessment generate POST | Yes | Valid topic-specific questions |
| Remediation aid | `learning_ai_service.generate_remediation_aid` | Topic result below threshold | Yes | Empty structured response; deterministic remediation |
| Scoring | `diagnostic_service.score_diagnostic`, `assessment_result_service.score_assessment` | Assessment submit | **No** | Deterministic option comparison |
| Path generation/ranking | `path_engine.generate_path_plan` | Path GET / result adaptation | **No** | Deterministic selection/order |

## API Timeline

Assessment timestamps are stored as UTC. Uvicorn logs did not attach wall-clock timestamps to each access row; sequence labels are used for requests without a directly matched timestamp.

| # | Time (UTC) | UI action | Method | Endpoint | Result |
|---:|---|---|---|---|---|
| 1 | Sequence 1 | Register | POST | `/api/auth/register` | 201 |
| 2 | Sequence 2 | Load profile options | GET | `/api/goals`, `/api/tracks` | 200 |
| 3 | Sequence 3 | Select track/goal | — | **NO API CALL** | React state |
| 4 | Sequence 4 | Create learner | POST | `/api/learners` | 201; learner 12 |
| 5 | Sequence 5 | Generate curriculum | POST | `/api/curriculum/generate` | 200; course 9, `openrouter` |
| 6 | Sequence 6 | Generate diagnostic | POST | `/api/learners/12/diagnostic/generate` | 200; assessment 26; fallback |
| 7 | 2026-10-08 02:02:39 | Submit diagnostic | POST | `/api/learners/12/diagnostic/26/submit` | 200; 50% |
| 8 | Sequence 8 | Create first path | GET | `/api/learners/12/learning-path` | 200; path 14 |
| 9 | Sequence 9 | Load current topic/lesson | GET | `/learning-path/current`, `/topics/{topic_id}/content` | 200; personalized lesson |
| 10 | 2026-10-08 02:04 (sequence) | Complete topic | POST | `/topics/{topic_id}/complete` | 200 |
| 11 | Sequence 11 | Generate topic assessment | POST | `/topics/{topic_id}/assessment/generate` | 200; assessment 27 |
| 12 | Sequence 12 | Load pending assessment | GET | `/assessments/27` | 200; public questions |
| 13 | 2026-10-08 02:05:28 | Submit topic assessment | POST | `/assessments/27/submit` | 200; 33.3%, remediation |
| 14 | Sequence 14 | Display final path/summary | GET | `/api/learners/12/learning-path`, `/api/learners/12/summary` | 200; updated path |
| 15 | Post-result check | Reload lesson | GET | `/learning-path/current`, `/topics/{topic_id}/content` | 200; empty LLM response then curated fallback |

## Test Validation

- Backend: `backend\.venv\Scripts\python.exe -m pytest -q tests` with the configured `.env` key — **54 passed, 3 failed, 1 skipped, 1 warning** in 250.03 seconds.
- The three failures are provider-dependent test assumptions: `test_diagnostic_generation_hides_internal_metadata` and `test_assessment_requires_learned_topic_and_hides_answer_keys` expected `curated_fallback` but got `openrouter`; `test_weak_result_persists_skills_weakness_recommendation_and_remediation` expected 0% from a fixed fallback answer set but received 66.7% from the live-generated assessment.
- Warning: Starlette TestClient deprecation notice for `anyio.abc.BlockingPortal`.
- A fallback-only rerun was attempted by blanking `OPENROUTER_API_KEY` in the test process, but Pydantic settings ignored the empty value and continued loading the root `.env`; it was stopped after confirming provider calls were still active. No offline rerun result is claimed.
- At the time of this learner-12 run, the opt-in live OpenRouter smoke test (`RUN_OPENROUTER_LIVE_TEST=1`) had not been run separately; the browser journey itself made real OpenRouter calls.
- Frontend: `npm run build` — **passed**, 43 modules transformed.
- TypeScript check: no TypeScript source or dedicated TypeScript check script is defined; frontend production build compiled the JSX application.
- No production code was changed for the historical learner-12 run. Production fixes were made and revalidated in the final learner-14 verification below.
