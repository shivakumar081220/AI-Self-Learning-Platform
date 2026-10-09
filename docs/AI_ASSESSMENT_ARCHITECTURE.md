# Assessment Architecture

## Generation

After a topic lesson is completed, `LearningExperiencePage` calls `generateAssessment` in `frontend/src/api/client.js` when the learner selects one or more assessment types.

```text
POST /api/learners/{learner_id}/topics/{topic_id}/assessment/generate
    -> routers/assessment.py::generate_topic_assessment
    -> multi_type_assessment_service.generate_assessment
    -> request_structured_json (when provider generation is enabled)
```

The request includes selected types and total question count. Generation context is derived from the authenticated learner, persisted course/topic, objectives, skill evidence, and completed work. The service validates type coverage, question shape, IDs, topic concepts, and hidden grading data before saving questions. Curated questions are used if valid provider output is unavailable.

Legacy callers that omit type-selection data retain the MCQ route. Matching pending assessments can be resumed rather than regenerated.

## Persistence and privacy

`Assessment` stores attempt state and legacy JSON fields. Multi-type question content and protected evaluation data use `AssessmentQuestionRecord`; learner answers and evaluation results use `AssessmentResponseRecord`. Draft response saves do not evaluate or score the assessment.

Public pending-question responses exclude correct answers, explanations, rubrics, expected concepts/output, function names, and sandbox test cases. These fields are only used by backend evaluation after submission.

## Submission and evaluation

`POST /api/learners/{learner_id}/assessments/{assessment_id}/submit` validates one response per question and evaluates by type:

- **MCQ:** deterministic answer-key comparison.
- **Conceptual, Scenario, Comparison:** grouped structured AI evaluation, with deterministic fallback when unavailable or invalid.
- **Code Output:** sandbox execution of the fixed question snippet; compare the learner's output with captured stdout.
- **Coding:** sandbox tests against the learner's submitted code.
- **Debugging:** sandbox tests plus structured evaluation of the learner's explanation.

Evaluation results are validated against question IDs, point limits, and expected concept IDs before being used to update learner state.

### External sandbox

Code-bearing tasks are sent in a batched request to `CODE_SANDBOX_URL`. Learner code is never executed in the FastAPI process. Without a configured sandbox, these submissions fail explicitly with HTTP 503 and remain uncompleted. The sandbox deployment must enforce process isolation, CPU/memory limits, network restrictions, and execution timeouts; the API timeout is not a substitute for those controls.

## Adaptive updates

After evaluation, the result service persists points and percentages, updates concept `SkillScore` records, creates or resolves `Weakness` records, saves a `Recommendation`, and updates topic progress and current position.

A passing result completes the topic and allows progression. Weak or developing evidence keeps the learner focused on revision or practice. Assessment interpretation and remediation text can explain deterministic evidence but cannot alter scores, ownership, prerequisite order, or completion state. The course curriculum is not silently replaced after an assessment.

## Cache and retry

Generated artifacts are keyed by relevant course, topic, assessment selection/version, and learner context. Pending attempts are reused where applicable. The shared provider makes at most one retry; invalid output is rejected and falls back to the supported curated/deterministic behavior.
