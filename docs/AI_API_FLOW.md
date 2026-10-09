# AI API Flow

This guide traces the learner journey through the frontend, API, services, and persisted state. Paths below use the current authenticated API.

## Learner journey

| Learner action | Frontend/API client | Request and backend flow | Persistent effect |
|---|---|---|---|
| Create account | `AuthProvider.register` → `registerAccount` | `POST /api/auth/register` → `auth.register` | Hashed-password `User` record |
| Save profile and track | `ProfilePage.handleSubmit` → `createLearner` | `POST /api/learners` → `learners.create_learner` | `Learner` and selected `LearningGoal` |
| Generate or load course | `generateMyCurriculum` | `POST /api/curriculum/generate` → `generate_my_curriculum` → `curriculum_service` | `GeneratedCourse`, ordered module JSON, owned `Topic` rows and prerequisite edges |
| Start diagnostic | `DiagnosticPage` → `generateDiagnostic` | `POST /api/learners/{learner_id}/diagnostic` → `generate_learner_diagnostic` → `diagnostic_service` | Pending `Assessment`; public questions exclude answer keys |
| Submit diagnostic | `DiagnosticPage.handleSubmit` | `POST /api/learners/{learner_id}/diagnostic/{assessment_id}/submit` → `submit_learner_diagnostic` | Deterministic score, `SkillScore` evidence, and saved interpretation/feedback |
| Open a topic | `LearningExperiencePage` → `getLearningContent` | `GET /api/learners/{learner_id}/topics/{topic_id}/content` → `get_topic_content` → `content_service` | `TopicProgress` and reusable `AIArtifactCache` lesson |
| Complete lesson | `LearningExperiencePage.handleComplete` | `POST /api/learners/{learner_id}/topics/{topic_id}/complete` | Lesson completion state; this alone does not pass the topic |
| Generate assessment | `LearningExperiencePage.handleGenerateAssessment` → `generateAssessment` | `POST /api/learners/{learner_id}/topics/{topic_id}/assessment/generate` → `generate_topic_assessment` → assessment service | Assessment/questions and validated generation artifact |
| Save/resume draft | `AssessmentPage` | `PUT /api/learners/{learner_id}/assessments/{assessment_id}/responses`; `GET` same assessment to reload | `AssessmentResponseRecord` draft answers; no evaluation on save |
| Submit assessment | `AssessmentPage.handleSubmit` | `POST /api/learners/{learner_id}/assessments/{assessment_id}/submit` → `submit_assessment` → result service | Score, skill updates, weaknesses, recommendation, progress, and path position |
| Use tutor | Tutor UI → `sendTutorMessage` | `POST /api/learners/{learner_id}/tutor/conversations/{conversation_id}/messages` | Learner and assistant turns saved in `TutorMessage` |
| Reload dashboard | Dashboard data request | `GET /api/learners/{learner_id}/summary` | Reads persisted state; no generation is needed for saved metrics |

All learner-specific routes must verify both authentication and ownership. Unauthorized access must not reveal another learner's records.

## AI generation and fallbacks

Curriculum, diagnostic, lesson, assessment, tutor, and selected interpretation/remediation operations call the shared structured provider only when needed. The provider validates structured output before a service uses or persists it. Repeated requests reuse persisted course, pending assessment, or cached artifact when its context key still matches.

Fallback behavior depends on the operation: track-specific curriculum fallback, curated question/lesson material, or deterministic tutor/interpretation/remediation. Fallback results are labeled by their source. Invalid AI output is not treated as successful generated content.

The assessment score, objective-item evaluation, skill-state update, prerequisite enforcement, and progress transition remain backend-controlled. Subjective assessment evaluation may use a structured AI grader; code tasks require the separately configured external sandbox.

## Adaptive sequence

`path_engine.generate_path_plan` uses persisted skills, assessment history, progress, goal, experience, and prerequisites. It may use valid OpenRouter diagnostic focus concepts to prioritize otherwise-eligible topics, but it validates topic membership and preserves prerequisite ordering. It does not make an additional provider call.

A passing assessment completes the topic and advances progress. Weak or developing evidence retains the topic for remediation or practice. Recommendations are distinct from the persisted course outline; an assessment does not silently replace the course.

## Privacy and retry behavior

Pending assessment responses omit answer keys and hidden grading metadata. Provider logs omit credentials and request/response bodies. Provider retries are bounded by the shared provider policy; failed frontend mutations are not automatically replayed.
