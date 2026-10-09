# Persistence Audit and Test Report

**Date:** 2026-10-09
**Scope:** Existing FastAPI/SQLAlchemy API, React/Vite persistence calls, database configuration, and automated persistence coverage.

## Executive summary

- The configured database is SQLite. The default relative URL previously depended on the process working directory; the active development database resolved under `backend/`. Relative SQLite file URLs now resolve from that backend directory, preserving the current backend-launched location when the process is started from another directory.
- The automated tests use temporary SQLite databases and dependency overrides. The persistence journey test closes its SQLAlchemy engine, creates a new engine for the same test file, logs the user in again, and reloads the saved records.
- No schema change was made. Course modules remain JSON on `generated_courses`; module content is cached as validated lesson JSON in `ai_artifact_cache`; progress and assessment state use relational rows.
- A live API persistence journey was run against the configured application database, followed by a complete stop/start of the audit backend and a fresh login. The course, cached topic lessons, topic progress, assessment results, tutor conversation, and dashboard history all reloaded.
- Final backend result: **122 passed, 1 skipped**. The skipped case is the explicitly opt-in live OpenRouter smoke test. Frontend production build passed; `git diff --check` and Pylance checks on changed Python files passed.
- The live journey added synthetic audit records to the shared application database through normal API calls. No database rows were manually edited or deleted. The database is shared, so unrelated concurrent writes cannot be excluded.

## Follow-up live persistence verification

### Runtime and database

- Backend command: `backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8002`, working directory `backend`.
- Ports 8000 and 8001 were already occupied by unrelated processes and were left untouched. The audit backend on 8002 was stopped by its verified process IDs; the port became free before it was started again.
- The same configured file was used before and after restart: `backend\adaptive_learning.db`. It was independently opened with SQLite `mode=ro` for verification; the database file remained present and was not removed or recreated.
- The audit server was configured to route OpenRouter requests to a closed local port. The course reported `deterministic_fallback`; the lessons and assessments reported `curated_fallback`; and the tutor reported `deterministic_fallback`. This was fallback-only verification, not a successful external LLM call.

### Journey and post-restart reads

All writes below were made by authenticated application APIs. Passwords and bearer tokens are intentionally omitted.

The live request flow was `POST /api/auth/register` → `POST /api/learners` → `POST /api/curriculum/generate` → `GET /api/curriculum/current` → `GET /api/learners/{learner_id}/learning-path?course_id=...` → per topic, `GET /api/learners/{learner_id}/topics/{topic_id}/content`, `POST /api/learners/{learner_id}/topics/{topic_id}/complete`, `POST /api/learners/{learner_id}/topics/{topic_id}/assessment/generate`, and `POST /api/learners/{learner_id}/assessments/{assessment_id}/submit`. Results were read with `GET /api/learners/{learner_id}/assessments/{assessment_id}`. Tutor data used `POST /api/learners/{learner_id}/tutor/conversations`, `POST /api/learners/{learner_id}/tutor/conversations/{conversation_id}/messages`, and `GET /api/learners/{learner_id}/tutor/conversations/{conversation_id}`. Dashboard data used `GET /api/learners/{learner_id}/dashboard?course_id=...`. After restart, authentication used `POST /api/auth/login` and `GET /api/auth/me`; the same profile, curriculum, path, topic, assessment, tutor, and dashboard GETs were repeated.

| Data | Live test result |
|---|---|
| Learner | User ID 22, learner ID 23; persisted experience `beginner`, goal text `Build a RAG application`, and target outcome `Build a persistent test RAG application`. |
| Course | Course ID 21, track `rag`, five ordered modules; generation source `deterministic_fallback`. A repeated course-generation request returned course 21 again. |
| Module/topics | First module had two topics, `Document Chunking` and `Document Metadata`. After both were completed and assessed, the reloaded course marked that module `completed`; the current position advanced to the next topic. |
| Lessons/cache | Both topic-content API responses contained the matching topic and `curated_fallback` content. Repeated content requests returned the same topic content. The scoped `ai_artifact_cache` count was four before and after restart/reloads. |
| Assessments | Topic attempts 49 and 50 each returned `curated_fallback`; repeating generation while each attempt was pending returned the same attempt ID. Both were submitted through the API and scored 100%. Fresh post-restart result requests returned both results. |
| Progress/adaptation | Two `topic_progress` rows were `completed`, two `skill_scores` rows and two recommendations were persisted, and the dashboard returned both assessment IDs and 20% overall course progress (two of ten course topics). |
| AI Tutor | Conversation 7 was created for the first module topic. A user question and assistant response were persisted; after restart and fresh login, the conversation returned both messages in order. Response source was `deterministic_fallback`. |
| Ownership | A second authenticated user received HTTP 403 for the learner dashboard, assessment result, and tutor conversation, both in the initial run and after restart. |

The backend was stopped completely and restarted on port 8002 against the same database. After restart, a fresh `POST /api/auth/login` and `GET /api/auth/me` succeeded. New API requests reloaded the learner profile, course, current learning position, both topic contents, both assessment results, tutor conversation, and dashboard. Repeated course/path reads preserved their IDs/current topic. Read-only database snapshots showed one scoped course, ten course topics, two assessments, two completed topic-progress rows, one tutor conversation, four artifact-cache rows, two skill scores, and two recommendations both before and after the restart. The tutor GET also returned the same two messages after restart.

The dashboard's 20% figure is consistent with the completed first module representing two of the ten course topics; only the first module was intentionally completed. This was a backend/API persistence run, not a browser-driven UI run. Browser refresh, logout/login through the UI, and visual rendering remain unverified.

### Test data left in the shared database

Three synthetic audit learner accounts were created during this continuation: learner IDs 21 and 22 belong to earlier interrupted attempts; learner 23 is the completed restart journey above. Three additional synthetic accounts were used only as the second user in ownership checks and have no learner profiles. These rows were preserved; no destructive cleanup was performed.

## Database configuration and lifecycle

- `Settings.database_url` defaults to `sqlite:///./adaptive_learning.db` in `backend/app/config.py`.
- Before the fix, SQLAlchemy interpreted that relative filename against the process current directory. The observed application database was `backend/adaptive_learning.db`.
- `backend/app/database.py::_resolve_database_url()` now anchors a relative SQLite file URL to the backend directory. Absolute paths, `:memory:`, and SQLite `file:` URIs are left as supplied.
- `backend/app/main.py` runs `ensure_legacy_columns()`, `Base.metadata.create_all()`, and idempotent topic seeding during application lifespan. `create_all()` does not drop existing tables.
- No Alembic or other migration framework is present. `ensure_legacy_columns()` is a SQLite-only, hand-maintained compatibility migration that adds columns/indexes and performs legacy data adjustments. It is not a general migration history system.
- Test fixtures use `tmp_path` databases. The end-to-end persistence test uses a dedicated temporary file and never routes test writes to the configured application engine.

## Persistence audit

| Entity/data | Database table/model | Create operation | Read operation | Update operation | Delete operation | Findings |
|---|---|---|---|---|---|---|
| User and credentials | `users` / `User` | `POST /api/auth/register` (`auth.register`) | `POST /api/auth/login`, `GET /api/auth/me` | No password/profile update route | No account-delete route | Passwords are stored as hashes. Logout is client-side token removal; issued JWTs are not server-revoked. |
| Learner profile | `learners` / `Learner` | `POST /api/learners` (`learners.create_learner`) | `GET /api/learners/me`, `GET /api/learners/{id}` | `PUT /api/learners/me` (`learners.update_my_learner`) | No learner-delete route | Goal and profile updates commit before the response. |
| Learning goals | `learning_goals` / `LearningGoal` | Learner creation and `_replace_active_goal()` | Learner/profile relationship; goal catalog is served separately | Active flags are changed and a new goal may be added | No goal-delete route | Historical/inactive goal rows can remain. |
| Diagnostic attempts and results | `assessments` / `Assessment` JSON fields | `POST /api/learners/{id}/diagnostic` (`generate_learner_diagnostic`) | `GET /api/learners/{id}/diagnostic/{assessment_id}` | Submit route stores answers, score, completion, and interpretation | No assessment-delete route | Diagnostic question/answer payloads are stored as JSON. Public generation responses omit answer keys; result responses expose review data after submission. |
| Concept skill scores | `skill_scores` / `SkillScore` | Diagnostic and assessment result services | Skills endpoint, dashboard, tutor context | Diagnostic and topic-assessment scoring update evidence and score | No skill-delete route | Scores are deterministic and persisted. A unique learner/concept constraint prevents duplicate skill rows. |
| Personalized course | `generated_courses` / `GeneratedCourse` | `POST /api/curriculum/generate` → `persist_curriculum()` | `GET /api/curriculum/current` | Profile changes may create a new course; no direct course-update route | No course-delete route | Learner/course ownership is checked. Repeated generation for the same profile reuses the saved row in sequential requests. Concurrent duplicate creation is not protected by a business-key unique constraint (see PERS-043). |
| Modules and curriculum ordering | `generated_courses.modules_json` | Built with the course by `persist_curriculum()` | Curriculum endpoints deserialize ordered JSON | No separate module update route | Deleted only with owning course through relationship cascade if deletion is introduced | No `Module` table exists; module IDs/order/topic IDs/prerequisites are embedded JSON. |
| Course topics and prerequisites | `topics`, `topic_prerequisites` / `Topic`, `TopicPrerequisite` | `seed_topics()` and `persist_curriculum()` | Curriculum, path, learning, and assessment routes | Seed/curriculum creation writes metadata; no learner-facing edit route | No topic/prerequisite delete route | Course topics have course/owner foreign keys. Topic title is globally unique; generated titles include an internal suffix. |
| Generated lesson content | `ai_artifact_cache` / `AIArtifactCache` | `get_or_generate_artifact()` in `ai_cache.py` | Same cache service from topic-content and tutor services | Cache status/source/result/expiry are updated | No cleanup/delete operation | Validated lesson JSON persists by learner/operation/cache key. Curated fallback lesson entries have no expiry; provider-generated artifacts are retained. |
| Topic completion and progress | `topic_progress` / `TopicProgress` | `GET /topics/{topic_id}/content` creates progress; completion route ensures a row | Current path, curriculum, dashboard | Content/complete/assessment services update status, completion, mastery, attempts, timestamp | No progress-delete route | Unique `(learner_id, topic_id)` prevents duplicate rows. Module completion is derived from its topic statuses, not a separate saved module row. |
| Learning path/current position | `learning_paths` / `LearningPath` | GET/generate path if absent | Learning path/current-topic/dashboard endpoints | `_persist_path()` and assessment adaptation update JSON/index | No path-delete route | Path ordering/current index persist. Assessment adaptation may advance or retain the current topic based on outcomes. |
| Assessment attempts/questions | `assessments`, `assessment_questions` / `Assessment`, `AssessmentQuestionRecord` | Assessment generation routes | Pending/result routes | Pending attempt metadata/answers are updated on save and submit | Child question records cascade with assessment | Legacy MCQ questions/answers are JSON on `Assessment`; multi-type attempts additionally use normalized question rows. |
| Assessment responses/evaluations | `assessment_responses` / `AssessmentResponseRecord` | `PUT /assessments/{id}/responses` | Persisted multi-type results | Saved answers and deterministic/AI evaluation fields are updated | Cascade with question | Unsubmitted answers are resumable. Final assessment scoring remains deterministic where defined by the question type. |
| Weakness/remediation state | `weaknesses` / `Weakness` | Assessment result services | Tutor context and adaptive flows | Open weakness evidence/severity is updated; status may become resolved | No weakness-delete route | Weakness rows preserve evidence and resolution state. |
| Recommendations | `recommendations` / `Recommendation` | Assessment result services | Assessment result and dashboard | `completed_at` exists but no acknowledgement/update route was found | No recommendation-delete route | Recommendation records persist; some dashboard content is also derived from latest assessment/path state. |
| Tutor conversations and messages | `tutor_conversations`, `tutor_messages` / `TutorConversation`, `TutorMessage` | Authenticated conversation/message endpoints | List/detail endpoints | Conversation title/timestamp and assistant/user message rows update on turns | No tutor delete route; declared FK cascade on conversation/topic | Message history survives reload/re-login. User turns commit before AI generation; assistant replies commit separately. |
| Voice transcripts/audio | No voice-specific table | Browser speech recognition produces text sent as a tutor message | Tutor conversation detail | Subsequent text messages append to conversation | No voice delete operation | The transcript is persisted through `tutor_messages`; raw audio is not stored by this application. |
| Dashboard and activity | No dashboard/activity table | No direct write; assembled from source entities | `GET /api/learners/{id}/dashboard` | Recomputed on request | Not applicable | Progress, assessments, tutor messages, skills, and recommendations are derived from persisted rows, not a snapshot table. |
| Frontend authentication/state | Browser `localStorage`/`sessionStorage` for access token only | `AuthProvider.register/login` | `restoreSession()` calls `/api/auth/me`; pages refetch profile/course/progress/content | Token placement/removal follows “remember me” | Logout removes browser token | No client-side lesson/course persistence cache was found; saved learning state is fetched from API. |

## Frontend persistence path

- `frontend/src/auth.jsx`: `AuthProvider.restoreSession()` reads the stored bearer token and requests `getCurrentUser()`. Login/register save the token; logout removes it.
- `frontend/src/api/client.js`: API calls cover learner profile, curriculum, diagnostic, learning path/content, topic completion, assessment save/result, tutor conversation, and dashboard reads/writes.
- `frontend/src/App.jsx`: route components fetch the saved data after mount/route changes. Tutor history is loaded through conversation list/detail APIs. Voice recognition submits its transcript through the tutor-message flow.
- No browser automation framework/test script was found in the frontend package. Browser refresh, account switching, and visible UI rollback were therefore not claimed as browser-tested.

## Persistence test cases

Status meanings: **PASS** means there is executed test evidence for the API/database behavior; **PARTIAL** means only part of the requested UI/process behavior was exercised; **BLOCKED** means the requested operation was not safely available; **NOT RUN** means no claim is made; **NOT APPLICABLE** means the requested feature is not implemented as a distinct operation.

| Case | Status | Evidence / limitation |
|---|---|---|
| PERS-001 User registration | PASS | New journey test checks database presence, bcrypt verification, and duplicate-email rejection. |
| PERS-002 Login and logout | PARTIAL | Login/re-login is tested. Logout is browser token removal; no server-side revocation endpoint or browser logout run. |
| PERS-003 Profile persistence | PASS | Profile update is refetched through a new API request and stored profile is verified. |
| PERS-004 Refresh and re-login | PARTIAL | Re-login after engine reconstruction is tested; actual browser refresh/logout UI was not automated. |
| PERS-005 Diagnostic answer persistence | PASS | Submitted diagnostic answers/attempt are re-read in a new database session. |
| PERS-006 Diagnostic score persistence | PASS | Deterministic zero-score result and stored completion/answer count/skill evidence are verified. |
| PERS-007 Skill update persistence | PASS | Diagnostic and topic assessments verify skill records in fresh sessions. |
| PERS-008 Assessment history | PASS | Diagnostic/topic history and dashboard ordering/performance tests run; full journey retains three topic attempts and the diagnostic. |
| PERS-009 Course generation | PASS | Generated course/module JSON/topics are retrieved from a fresh session. |
| PERS-010 Course refresh | PASS | Module IDs/order are compared before and after engine reconstruction. |
| PERS-011 Course re-login | PASS | Course is fetched after a new login token and database engine reconstruction. |
| PERS-012 No unnecessary regeneration | PASS | Generation service spy observes one generation; repeated GET/current and generation request reuse the course without another generation call. |
| PERS-013 Course ownership | PASS | Existing authorization tests and new journey reject cross-user dashboard access. |
| PERS-014 Ordering/relationships | PASS | Tests verify ordered module IDs, module-topic membership, and course-topic relationship. |
| PERS-015 Module content persistence | PASS | Lesson artifact is persisted in `ai_artifact_cache` and reloaded identically. |
| PERS-016 Lesson refresh | PASS | Same saved lesson is fetched after closing/reconstructing database engine. |
| PERS-017 Lesson regeneration | NOT APPLICABLE | No explicit force-regenerate/versioning API exists. The current `POST .../content/generate` shares the cache-backed retrieval path and reuses valid saved content. |
| PERS-018 Lesson-to-topic integrity | PASS | Stored and returned lesson `topic_id` is checked against the selected course topic; ownership tests cover generated topics. |
| PERS-019 Generated-content cache | PASS | Existing content and assessment cache tests plus journey test verify artifact reuse. Cache includes learner and operation/context keying. |
| PERS-020 Topic completion | PASS | Existing idempotency test and full journey verify completion/progress persistence. |
| PERS-021 Module completion | PARTIAL | Module status is calculated from child topic states; no separate module-completion row/API exists. |
| PERS-022 Current learning position | PASS | The adaptive current topic is fetched before and after database-engine reconstruction. |
| PERS-023 Progress recalculation | PASS | Dashboard tests compare percentage/counts against stored topic completion records. |
| PERS-024 Progress idempotency | PASS | Repeated completion request does not duplicate `TopicProgress`. |
| PERS-025 Assessment attempt persistence | PASS | Attempt, response answers, score, completion, weakness, and recommendation are verified. |
| PERS-026 Assessment resume | PASS | Multi-type test covers saving/resuming pending responses; saved attempt retrieval after completion is covered. |
| PERS-027 Server-side answer security | PASS | Generated assessment responses omit `correct_option`/explanations; results reveal review only after submission. |
| PERS-028 Multi-type persistence | PASS | Existing tests exercise all seven supported types and persisted multi-type responses/results. |
| PERS-029 Adaptive remediation persistence | PASS | Weak assessment creates persisted weakness/recommendation; dashboard reads saved adaptation. |
| PERS-030 Reassessment/weakness resolution | PASS | Full journey submits two perfect retakes, verifies weakness resolution, and retains all three topic attempts. |
| PERS-031 Conversation persistence | PASS | User and assistant messages are reloaded from a fresh session and after engine reconstruction. |
| PERS-032 Conversation continuation | PASS | A new message is sent after engine reconstruction using the restored conversation. |
| PERS-033 Tutor reload/re-login | PARTIAL | Backend conversation is restored after new login/engine; no browser logout/refresh test. |
| PERS-034 Tutor context integrity | PASS | Existing tests verify persisted lesson, current topic, course, assessment and skill context in rebuilt tutor context. |
| PERS-035 Cross-user conversation isolation | PASS | Existing and new tests reject foreign learner/conversation access. |
| PERS-036 Dashboard persisted data | PASS | Dashboard metrics/recommendation/history are verified against saved rows. |
| PERS-037 Dashboard refresh | PARTIAL | Fresh API request after engine reconstruction is verified; browser refresh/new browser session not run. |
| PERS-038 Activity history | PASS | Dashboard activity is derived from persisted progress, assessments, and tutor messages; no standalone activity table exists. |
| PERS-039 Empty dashboard | PASS | Existing dashboard empty-state test checks zero progress and no fabricated activity. |
| PERS-040 Backend restart | PASS | Audit backend process was stopped completely and restarted against the same configured application database; a fresh login and API reads restored the saved learner journey. |
| PERS-041 Session independence | PASS | Journey repeatedly closes sessions and reloads records using fresh sessions and a new engine. |
| PERS-042 Transaction rollback | PASS | Injected failure at final curriculum commit leaves no generated course or course-topic rows. |
| PERS-043 Concurrent duplicate requests | NOT RUN | No concurrency race harness was run. `persist_curriculum()` uses check-then-create without a unique course business key; concurrent identical requests remain a risk. |
| PERS-044 Database constraints | PARTIAL | ORM foreign keys/uniques and ownership behavior are inspected/tested, but every cascade/constraint was not exhaustively fault-tested. |
| PERS-045 Migration safety | PARTIAL | Startup is non-dropping and SQLite compatibility ALTERs were inspected; there is no migration framework and legacy upgrade was not tested against a copied historical database. |
| PERS-046 AI provider failure | PASS | Existing tests cover timeout/rate-limit/malformed output and curated fallback; live provider was not called. |
| PERS-047 Database failure | NOT RUN | No systematic connection/commit fault injection across endpoints. Tutor write-lock handling exists and is covered by a separate tutor test. |
| PERS-048 Frontend optimistic state | NOT RUN | No browser-based save-failure/rollback test was run. |
| PERS-049 Repeated refresh | PARTIAL | Repeated live API reads reused course, path, and cached lessons without increasing scoped course/lesson/assessment counts; repeated real-browser refreshes were not run. |
| PERS-050 Persistence regression | PASS | Full backend suite: 122 passed, 1 opt-in live-provider test skipped. Frontend production build passed. |

## Confirmed issue fixed

**Working-directory-dependent SQLite location.** The old relative URL could select a different `adaptive_learning.db` if the API was started from a different current directory. `backend/app/database.py` now resolves relative SQLite filenames from the backend directory. This is covered by `test_relative_sqlite_database_url_is_stable_across_working_directories`. No schema or database file was rewritten by this change.

## Remaining risks and unverified behavior

1. **Concurrent course generation:** Sequential repeated generation reuses a course and is tested. Concurrent requests can both observe “no existing course” before either commits; a unique business key/serialization policy has not been added because it could change course-version semantics and requires a migration plan.
2. **Migration strategy:** `ensure_legacy_columns()` is hand-maintained. A production migration history/rollback tool and a copied historical-schema upgrade test remain advisable.
3. **Explicit lesson regeneration:** No cache-bypass/versioned regeneration behavior exists. The current generate endpoint returns validated cached content when present.
4. **Browser persistence:** API-level reload/re-login behavior and an actual backend process restart were tested. A browser-driven logout/refresh/new-session test was not run; visual loading/error states and account switching remain unverified.
5. **Live AI / external sandbox:** The live journey used provider-fallback mode, not a successful external LLM call. The opt-in live OpenRouter smoke test was skipped, and code-sandbox persistence/evaluation was not exercised.
6. **Database failure coverage:** A curriculum commit failure rollback was tested; general connection loss/commit failure behavior for all endpoints was not.
7. **Shared database observation:** The live test intentionally wrote through application APIs to `backend/adaptive_learning.db` and preserved all resulting rows. Scoped counts for the test learner matched across restart/reloads, but unrelated concurrent activity in the shared workspace/database cannot be excluded.

## Changed files

- `backend/app/database.py` — stable resolution for relative SQLite database URLs.
- `backend/tests/test_database.py` — working-directory-independent SQLite URL regression test.
- `backend/tests/test_persistence_journey.py` — isolated authenticated end-to-end persistence, re-login/engine reconstruction, course/lesson/cache, progress, assessment/remediation, tutor, ownership, and rollback tests.
- `README.md` — documents relative SQLite path resolution.

No production tables or database records were manually edited. No commit or push was made.
