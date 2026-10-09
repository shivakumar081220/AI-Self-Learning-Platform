# Assessment Types

Learners select one or more types for a topic assessment. Recommended combinations in the UI are deterministic guidance and can be changed by the learner.

| Type | What it checks | Evaluation |
|---|---|---|
| MCQ | Concept and application knowledge | Deterministic answer-key comparison |
| Conceptual | Explanation in the learner's own words | Structured AI evaluation; deterministic fallback |
| Scenario-based | Practical design or problem-solving | Structured AI evaluation; deterministic fallback |
| Code Output | Understanding code behavior | External sandbox runs fixed snippet; compare learner output with actual stdout |
| Coding | Implementing a topic-relevant solution | External sandbox tests |
| Debugging | Finding/fixing a defect and explaining it | External sandbox tests plus explanation evaluation |
| Comparison | Distinguishing related methods or concepts | Structured AI evaluation; deterministic fallback |

## Selection and question count

At least one type is required. The requested question count applies to the whole assessment. If it is smaller than the number of selected types, the backend ensures at least one question per selected type. The generated response must contain the selected types and no unselected types.

## Hidden grading data

The backend stores type-specific answer keys and grading metadata. Pending-question API responses omit correct options, explanations, rubrics, expected concepts or outputs, function names, and test cases. The result API returns review information only after submission.

For a retake, recent completed prompts are used to discourage exact repetition. Generated output is checked before persistence; cached content and pending attempts are reused only when the relevant assessment context matches.

## Scoring and adaptation

Objective scoring and score aggregation are performed by backend code. Subjective responses may be evaluated by a structured model request, but the backend checks question IDs, score bounds, and concept references. Code assessment requires an external sandbox; learner code is not run by FastAPI.

Scores and concept evidence are persisted. The result service updates skills and weaknesses, records recommendations, and changes progress based on assessed evidence. Weak results trigger remediation; developing results prompt practice; passing results enable progression. The curriculum itself is not replaced after every assessment.

## Persistence and resume

Multi-type questions are stored in `AssessmentQuestionRecord`; saved answers and evaluations are stored in `AssessmentResponseRecord`. Partial saves can be resumed without evaluation. Completed results are read from storage and are not regenerated or re-evaluated on reopen.
