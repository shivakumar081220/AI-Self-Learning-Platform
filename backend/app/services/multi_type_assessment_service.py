import logging
import json
import re
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (
    Assessment,
    AssessmentQuestionRecord,
    AssessmentResponseRecord,
    GeneratedCourse,
    Learner,
    Recommendation,
    Topic,
    TopicProgress,
)
from ..schemas import (
    AssessmentAnswer,
    AssessmentResultResponse,
    AssessmentQuestionType,
    AssessmentTypesQuestion,
    AssessmentTypesQuestionSet,
    ConceptMasteryEvaluation,
    ConceptResult,
    OpenResponseEvaluation,
    OpenResponseEvaluationSet,
    RecommendationResponse,
)
from ..topic_titles import display_topic_title
from .ai_cache import get_or_generate_artifact
from .ai_provider import AIProviderError, log_ai_fallback, request_structured_json
from .assessment_result_service import (
    WEAK_THRESHOLD,
    _adapt_path,
    _recommendation,
    _update_skill,
    _update_weakness,
    classify_score,
)
from .learning_ai_service import generate_remediation_aid, interpret_skill_results


logger = logging.getLogger(__name__)
ASSESSMENT_VERSION = "multi-type-v1"
SUBJECTIVE_TYPES = {"conceptual", "scenario", "comparison"}
PUBLIC_METADATA_KEYS = {"answer_format", "comparison_target", "requirements"}
_ASSESSMENT_VALIDATION_REASONS = {
    "Generated assessment has an unexpected question count": "unexpected_question_count",
    "Generated assessment does not match the selected types": "selected_type_mismatch",
    "Generated assessment contains an unknown topic concept": "unknown_topic_concept",
    "Generated assessment repeats a previous question": "repeated_question",
    "Generated question metadata contains hidden assessment data": "hidden_assessment_data",
    "Generated question references an unknown expected concept": "unknown_expected_concept",
    "Code-output questions must use Python": "invalid_code_output_question",
    "Code tasks must use Python": "invalid_code_task_language",
    "Code tasks may include at most 20 tests": "too_many_code_tests",
    "Code test cases must define args, kwargs and expected": "invalid_code_test_case",
}


def _question_fingerprint(question: str) -> str:
    return re.sub(r"[^a-z0-9]", "", question.casefold())


class SandboxTaskResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=2, max_length=80)
    passed: int = Field(ge=0, le=20)
    total: int = Field(ge=1, le=20)
    feedback: str = Field(min_length=1, max_length=1000)
    actual_output: str | None = Field(default=None, max_length=2000)


class SandboxBatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[SandboxTaskResult] = Field(min_length=1, max_length=30)


def _fallback_question(
    topic: Topic, question_type: AssessmentQuestionType, index: int
) -> AssessmentTypesQuestion:
    title = display_topic_title(topic.title)
    concept = str((topic.concept_tags or ["ai_fundamentals"])[index % len(topic.concept_tags or ["ai_fundamentals"])])
    concept_text = concept.replace("_", " ")
    framing = index % 4
    common = {
        "question_id": f"{question_type}-{index + 1}-{topic.id[:40]}",
        "question_type": question_type,
        "concept": concept,
        "difficulty": topic.difficulty,
        "points": 1,
    }
    if question_type == "mcq":
        question = [
            f"Which approach best applies {concept_text} when working with {title}?",
            f"A learner is applying {title} in a new task. Which choice uses {concept_text} appropriately?",
            f"Which decision shows sound use of {concept_text} in a practical {title} workflow?",
            f"When checking a {title} result, which action best demonstrates {concept_text}?",
        ][framing]
        return AssessmentTypesQuestion(
            **common,
            question=question,
            options=[
                f"Use {concept_text} for its intended purpose and validate the result",
                "Assume a fluent output is correct without checking evidence",
                "Let the model directly change learner or application state",
                "Remove relevant context so the system can infer missing facts",
            ],
            correct_option=0,
            explanation=f"{topic.description} Validate outputs against the task requirements.",
        )
    if question_type == "conceptual":
        question = [
            f"In your own words, explain {concept_text} and how it contributes to {title}.",
            f"Teach a teammate the core idea of {concept_text}, using {title} as your example.",
            f"Describe how {concept_text} works and where it fits in {title}.",
            f"Explain {concept_text} step by step, then connect it to {title}.",
        ][framing]
        return AssessmentTypesQuestion(
            **common,
            question=question,
            rubric=["Explain the core mechanism accurately", "Connect it to the supplied topic"],
            expected_concepts=[concept],
        )
    if question_type == "scenario":
        scenario = [
            "A team is applying",
            "A learner is reviewing",
            "A product team is designing",
            "An engineer is validating",
        ][framing]
        return AssessmentTypesQuestion(
            **common,
            question=(
                f"{scenario} {title} in a real user workflow. Describe a design choice that uses "
                f"{concept_text}, explain why it fits, and name one trade-off or validation step."
            ),
            rubric=["Choose a technically suitable approach", "Explain reasoning", "Address a trade-off or validation"],
            expected_concepts=[concept],
        )
    if question_type == "code_output":
        threshold = [0.5, 0.6, 0.7, 0.8][framing]
        scores = [0.2, 0.8, 0.65] if framing % 2 else [0.2, 0.8]
        expected_output = str([score for score in scores if score >= threshold])
        return AssessmentTypesQuestion(
            **common,
            question=f"Predict the exact output of this {concept_text} check used in {title}.",
            code=f"scores = {scores!r}\nthreshold = {threshold}\nselected = [score for score in scores if score >= threshold]\nprint(selected)",
            language="python",
            expected_output=expected_output,
            metadata={"answer_format": "Enter the printed output."},
        )
    if question_type == "coding":
        function_name = [
            "limit_topic_items",
            "take_first_items",
            "select_prefix_items",
            "keep_initial_items",
        ][framing]
        return AssessmentTypesQuestion(
            **common,
            question=f"Implement {function_name} for {title}: return at most limit items from the beginning of items, preserving order.",
            starter_code=f"def {function_name}(items, limit):\n    # Return the first `limit` items.\n    pass",
            language="python",
            function_name=function_name,
            rubric=["Return no more than limit elements", "Preserve input order"],
            expected_concepts=[concept],
            test_cases=[
                {"args": [["a", "b", "c"], 2], "kwargs": {}, "expected": ["a", "b"]},
                {"args": [["a"], 3], "kwargs": {}, "expected": ["a"]},
                {"args": [["a", "b"], 0], "kwargs": {}, "expected": []},
            ],
            metadata={"requirements": ["Preserve order", "Handle zero and oversized limits"]},
        )
    if question_type == "debugging":
        function_name = [
            "limit_topic_items",
            "take_first_items",
            "select_prefix_items",
            "keep_initial_items",
        ][framing]
        broken_code = f"def {function_name}(items, limit):\n    return items[limit:]\n"
        return AssessmentTypesQuestion(
            **common,
            question=f"Debug this {title} utility: identify the bug, explain its cause, and provide corrected Python code for {function_name}.",
            code=broken_code,
            starter_code=broken_code,
            language="python",
            function_name=function_name,
            rubric=["Identify that the slice starts at limit instead of zero", "Return the first limit items"],
            expected_concepts=[concept],
            test_cases=[
                {"args": [["a", "b", "c"], 2], "kwargs": {}, "expected": ["a", "b"]},
                {"args": [["a"], 3], "kwargs": {}, "expected": ["a"]},
            ],
            metadata={"requirements": ["State the bug and cause", "Submit corrected code"]},
        )
    return AssessmentTypesQuestion(
        **common,
        question=(
            f"Compare {concept_text} with an alternative approach used in {title}. Explain differences, use cases, and trade-offs."
            if framing % 2 == 0
            else f"Choose an alternative to {concept_text} for {title}; compare their use cases and practical trade-offs."
        ),
        rubric=["Describe technically accurate differences", "Identify suitable use cases", "Explain trade-offs"],
        expected_concepts=[concept],
        metadata={"comparison_target": title},
    )


def _fallback_set(
    topic: Topic,
    selected_types: list[AssessmentQuestionType],
    question_count: int,
    previous_questions: list[dict[str, Any]] | None = None,
) -> AssessmentTypesQuestionSet:
    selected = list(selected_types)
    count = max(question_count, len(selected))
    previous_questions = previous_questions or []
    seen = {
        _question_fingerprint(item.get("question", ""))
        for item in previous_questions
    }
    questions = []
    for index in range(count):
        question_type = selected[index % len(selected)]
        variant_index = len(previous_questions) + index
        question = _fallback_question(topic, question_type, variant_index)
        attempts = 0
        while _question_fingerprint(question.question) in seen and attempts < 16:
            variant_index += 1
            attempts += 1
            question = _fallback_question(topic, question_type, variant_index)
        if _question_fingerprint(question.question) in seen:
            question.question = (
                f"Consider a new practical case {len(previous_questions) + index + 1}: "
                f"{question.question}"
            )
        seen.add(_question_fingerprint(question.question))
        questions.append(question)
    return AssessmentTypesQuestionSet(questions=questions)


def _validate_generated_set(
    question_set: AssessmentTypesQuestionSet,
    selected_types: list[AssessmentQuestionType],
    question_count: int,
    topic: Topic,
    previous_questions: list[dict[str, Any]] | None = None,
) -> AssessmentTypesQuestionSet:
    expected = max(question_count, len(selected_types))
    if len(question_set.questions) != expected:
        raise ValueError("Generated assessment has an unexpected question count")
    found_types = {question.question_type for question in question_set.questions}
    if found_types != set(selected_types):
        raise ValueError("Generated assessment does not match the selected types")
    allowed_concepts = set(topic.concept_tags)
    if any(question.concept not in allowed_concepts for question in question_set.questions):
        raise ValueError("Generated assessment contains an unknown topic concept")
    previous_fingerprints = {
        _question_fingerprint(item.get("question", ""))
        for item in previous_questions or []
    }
    current_fingerprints = [
        _question_fingerprint(question.question)
        for question in question_set.questions
    ]
    if (
        len(current_fingerprints) != len(set(current_fingerprints))
        or any(fingerprint in previous_fingerprints for fingerprint in current_fingerprints)
    ):
        raise ValueError("Generated assessment repeats a previous question")
    for question in question_set.questions:
        if _contains_hidden_assessment_data(question.metadata):
            raise ValueError("Generated question metadata contains hidden assessment data")
        if not set(question.expected_concepts).issubset(allowed_concepts):
            raise ValueError("Generated question references an unknown expected concept")
        if question.question_type == "code_output":
            if question.language != "python" or not (question.expected_output or "").strip():
                raise ValueError("Code-output questions must use Python")
        if question.question_type in {"coding", "debugging"}:
            if question.language != "python":
                raise ValueError("Code tasks must use Python")
            if len(question.test_cases) > 20:
                raise ValueError("Code tasks may include at most 20 tests")
            for case in question.test_cases:
                if set(case) != {"args", "kwargs", "expected"}:
                    raise ValueError("Code test cases must define args, kwargs and expected")
    return question_set


def _contains_hidden_assessment_data(value: Any) -> bool:
    hidden_keys = {
        "answer",
        "answer_key",
        "correct_answer",
        "correct_option",
        "expected_concepts",
        "expected_output",
        "explanation",
        "rubric",
        "solution",
        "test_cases",
        "test_answers",
    }
    if isinstance(value, dict):
        return any(
            str(key).lower() in hidden_keys or _contains_hidden_assessment_data(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_hidden_assessment_data(item) for item in value)
    return False


def _openrouter_questions(
    topic: Topic,
    learner: Learner,
    course: GeneratedCourse | None,
    selected_types: list[AssessmentQuestionType],
    question_count: int,
    weak_concepts: list[str],
    completed_topics: list[str],
    previous_questions: list[dict[str, Any]],
) -> AssessmentTypesQuestionSet:
    parsed = request_structured_json(
        operation="topic_assessment_questions",
        system_prompt=(
            "Create one complete multi-type assessment for the supplied course topic. Include questions for every "
            "selected type and no unselected types. Use exactly the requested total number of questions, or one "
            "question per selected type if the requested count is smaller. MCQs have four plausible distractors "
            "and one correct_option. Open response items include rubric and expected_concepts. Code output items "
            "include short Python code and exact expected_output. Coding/debugging items define a function_name and "
            "JSON-compatible tests using args, kwargs and expected. Debugging code must contain a real defect. "
            "Never put answer keys, hidden concepts or test expectations in metadata or visible question text. "
            "Avoid repeating any question in previous_questions_to_avoid. Return only fields defined by the response schema."
        ),
        user_payload={
            "learner": {
                "experience_level": learner.experience_level,
                "goal": learner.goal_text,
                "target_outcome": learner.target_outcome,
            },
            "course": {
                "title": course.title if course else None,
                "track_id": course.track_id if course else topic.track_id,
                "objectives": course.learning_objectives_json if course else [],
            },
            "topic": {
                "id": topic.id,
                "title": display_topic_title(topic.title),
                "description": topic.description,
                "objectives": topic.learning_objectives_json or [],
                "concepts": topic.concept_tags,
                "difficulty": topic.difficulty,
            },
            "weak_concepts": weak_concepts,
            "completed_topics": completed_topics,
            "selected_types": selected_types,
            "requested_question_count": max(question_count, len(selected_types)),
            "previous_questions_to_avoid": [
                item.get("question", "") for item in previous_questions
            ],
        },
        response_model=AssessmentTypesQuestionSet,
        temperature=0.2,
        max_tokens=3200,
    )
    return _validate_generated_set(
        parsed, selected_types, question_count, topic, previous_questions
    )


def generate_assessment(
    database: Session,
    topic: Topic,
    learner: Learner,
    selected_types: list[AssessmentQuestionType],
    question_count: int,
) -> tuple[AssessmentTypesQuestionSet, str]:
    course = database.get(GeneratedCourse, topic.course_id) if topic.course_id else None
    allowed_concepts = set(topic.concept_tags)
    weak_concepts = [
        item.concept
        for item in learner.skill_scores
        if item.score < 0.75 and item.concept in allowed_concepts
    ]
    completed_topics = [
        item.topic.title
        for item in database.scalars(
            select(TopicProgress).where(
                TopicProgress.learner_id == learner.id,
                TopicProgress.status == "completed",
            )
        ).all()
        if item.topic is not None
        and item.topic.course_id == topic.course_id
    ]
    previous_assessments = database.scalars(
        select(Assessment)
        .where(
            Assessment.learner_id == learner.id,
            Assessment.topic_id == topic.id,
            Assessment.assessment_type == "topic",
            Assessment.completed_at.is_not(None),
        )
        .order_by(Assessment.completed_at.desc(), Assessment.id.desc())
        .limit(10)
    ).all()
    previous_questions = [
        question
        for assessment in previous_assessments
        for question in assessment.questions_json
        if isinstance(question, dict) and question.get("question")
    ][:50]
    previous_fingerprints = [
        _question_fingerprint(item["question"]) for item in previous_questions
    ]
    effective_count = max(question_count, len(selected_types))

    def generate() -> tuple[AssessmentTypesQuestionSet, str]:
        if settings.openrouter_api_key:
            try:
                return (
                    _openrouter_questions(
                        topic,
                        learner,
                        course,
                        selected_types,
                        effective_count,
                        weak_concepts,
                        completed_topics,
                        previous_questions,
                    ),
                    "openrouter",
                )
            except (AIProviderError, ValidationError, ValueError) as error:
                reason = _ASSESSMENT_VALIDATION_REASONS.get(
                    str(error), type(error).__name__
                )
                logger.warning(
                    "AI assessment generation used deterministic fallback; reason=%s",
                    reason,
                )
        return _fallback_set(
            topic, selected_types, effective_count, previous_questions
        ), "curated_fallback"

    return get_or_generate_artifact(
        database,
        learner_id=learner.id,
        operation="multi_type_topic_assessment",
        key_context={
            "version": ASSESSMENT_VERSION,
            "topic_id": topic.id,
            "course_id": topic.course_id,
            "course_title": course.title if course else None,
            "course_track": course.track_id if course else topic.track_id,
            "course_objectives": course.learning_objectives_json if course else [],
            "topic_description": topic.description,
            "topic_objectives": topic.learning_objectives_json or [],
            "topic_concepts": topic.concept_tags,
            "selected_types": sorted(selected_types),
            "question_count": effective_count,
            "difficulty": topic.difficulty,
            "learner_level": learner.experience_level,
            "goal": learner.goal_text,
            "target_outcome": learner.target_outcome,
            "weak_concepts": sorted(weak_concepts),
            "completed_topics": sorted(completed_topics),
            "previous_question_fingerprints": previous_fingerprints,
        },
        response_model=AssessmentTypesQuestionSet,
        generate=generate,
        fallback=lambda: _fallback_set(
            topic, selected_types, effective_count, previous_questions
        ),
    )


def public_question(question: AssessmentTypesQuestion) -> dict[str, Any]:
    return {
        "question_id": question.question_id,
        "question": question.question,
        "question_type": question.question_type,
        "concept": question.concept,
        "difficulty": question.difficulty,
        "points": question.points,
        "options": question.options or [],
        "code": question.code,
        "starter_code": question.starter_code,
        "language": question.language,
        "metadata": {
            key: value
            for key, value in question.metadata.items()
            if key in PUBLIC_METADATA_KEYS
        },
    }


def save_question_records(
    database: Session, assessment: Assessment, question_set: AssessmentTypesQuestionSet
) -> None:
    assessment.questions_json = [question.model_dump(mode="json") for question in question_set.questions]
    assessment.selected_types = list(dict.fromkeys(assessment.selected_types or [
        question.question_type for question in question_set.questions
    ]))
    assessment.status = "pending"
    assessment.total_points = sum(question.points for question in question_set.questions)
    for question in question_set.questions:
        record = AssessmentQuestionRecord(
            assessment=assessment,
            question_id=question.question_id,
            question_type=question.question_type,
            question=question.question,
            concept=question.concept,
            difficulty=question.difficulty,
            points=question.points,
            options_json=question.options,
            code=question.code,
            starter_code=question.starter_code,
            metadata_json=question.metadata,
            evaluation_data_json={
                "correct_option": question.correct_option,
                "explanation": question.explanation,
                "rubric": question.rubric,
                "expected_concepts": question.expected_concepts,
                "expected_output": question.expected_output,
                "function_name": question.function_name,
                "test_cases": question.test_cases,
            },
        )
        database.add(record)


def evaluate_open_responses(
    questions: list[AssessmentTypesQuestion], answers: dict[str, Any], learner: Learner, topic: Topic
) -> tuple[dict[str, OpenResponseEvaluation], str]:
    subjective = [
        question
        for question in questions
        if question.question_type in SUBJECTIVE_TYPES | {"debugging"}
    ]
    if not subjective:
        return {}, "not_applicable"

    def fallback_evaluation(question: AssessmentTypesQuestion) -> OpenResponseEvaluation:
        answer = _answer_text(answers.get(question.question_id)).lower()
        matched = [concept for concept in question.expected_concepts if concept.lower() in answer]
        fraction = len(matched) / max(1, len(question.expected_concepts))
        score = round(question.points * fraction, 2)
        missing = [concept for concept in question.expected_concepts if concept not in matched]
        return OpenResponseEvaluation(
            question_id=question.question_id,
            score=score,
            strengths=["Uses relevant topic terminology"] if matched else [],
            missing_concepts=missing,
            feedback=(
                "Your response includes relevant concepts; add reasoning and specific evidence."
                if matched
                else "Your response should address the key concepts and explain the reasoning."
            ),
            concept_mastery=[
                ConceptMasteryEvaluation(concept=concept, mastery=1.0 if concept in matched else 0.0)
                for concept in question.expected_concepts
            ],
        )

    if not settings.openrouter_api_key:
        log_ai_fallback("assessment_response_evaluation", "provider_not_configured")
        return {item.question_id: fallback_evaluation(item) for item in subjective}, "deterministic_fallback"
    try:
        parsed = request_structured_json(
            operation="assessment_response_evaluation",
            system_prompt=(
                "Evaluate every supplied open response against only its own rubric and hidden expected concepts. "
                "Do not alter assessment state or invent evidence. Score each response from 0 to that question's "
                "points. Return exactly one evaluation per supplied question, preserving question_id. "
                "Return only the declared schema."
            ),
            user_payload={
                "learner": {"level": learner.experience_level, "goal": learner.goal_text},
                "topic": {"title": display_topic_title(topic.title), "concepts": topic.concept_tags},
                "responses": [
                    {
                        "question_id": question.question_id,
                        "question_type": question.question_type,
                        "question": question.question,
                        "answer": (
                            _answer_text(answers.get(question.question_id))
                            if question.question_type == "debugging"
                            else answers.get(question.question_id)
                        ),
                        "points": question.points,
                        "rubric": question.rubric,
                        "expected_concepts": question.expected_concepts,
                    }
                    for question in subjective
                ],
            },
            response_model=OpenResponseEvaluationSet,
            temperature=0.1,
            max_tokens=2200,
        )
        expected_ids = {question.question_id for question in subjective}
        evaluations = {item.question_id: item for item in parsed.evaluations}
        if set(evaluations) != expected_ids:
            raise ValueError("AI evaluation question IDs do not match submitted responses")
        question_by_id = {item.question_id: item for item in subjective}
        for question_id, evaluation in evaluations.items():
            question = question_by_id[question_id]
            if evaluation.score > question.points:
                raise ValueError("AI evaluation exceeded question points")
            allowed_concepts = set(question.expected_concepts)
            if (
                not set(evaluation.missing_concepts).issubset(allowed_concepts)
                or {item.concept for item in evaluation.concept_mastery} != allowed_concepts
            ):
                raise ValueError("AI evaluation referenced an unknown concept")
        return evaluations, "openrouter"
    except (AIProviderError, ValidationError, ValueError) as error:
        logger.warning(
            "AI response evaluation used deterministic fallback; reason=%s",
            type(error).__name__,
        )
        log_ai_fallback("assessment_response_evaluation", type(error).__name__)
        return {item.question_id: fallback_evaluation(item) for item in subjective}, "deterministic_fallback"


def evaluate_code_in_sandbox(
    submissions: list[dict[str, Any]],
) -> tuple[dict[str, SandboxTaskResult], str]:
    if not settings.code_sandbox_url:
        raise RuntimeError("Code evaluation is unavailable because CODE_SANDBOX_URL is not configured")
    request_body = json.dumps(
        {
            "tasks": submissions,
        }
    ).encode("utf-8")
    request = Request(
        settings.code_sandbox_url,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.code_sandbox_timeout_seconds) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"Code sandbox returned HTTP {response.status}")
            payload = json.loads(response.read(256_001))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError("Code sandbox request failed") from error
    if not isinstance(payload, dict):
        raise RuntimeError("Code sandbox returned an invalid response")
    result = SandboxBatchResult.model_validate(payload)
    results = {item.question_id: item for item in result.results}
    expected_ids = {str(item["question_id"]) for item in submissions}
    if set(results) != expected_ids:
        raise RuntimeError("Code sandbox returned unexpected task results")
    for item in submissions:
        task_result = results[str(item["question_id"])]
        if item.get("execution_mode") == "stdout":
            if task_result.actual_output is None or task_result.total != 1:
                raise RuntimeError("Code sandbox returned an incomplete output result")
        elif task_result.total != len(item["test_cases"]) or task_result.passed > task_result.total:
            raise RuntimeError("Code sandbox returned inconsistent test totals")
    return results, "sandbox"


def _answer_text(answer: Any) -> str:
    if isinstance(answer, str):
        return answer.strip()
    if isinstance(answer, dict):
        return " ".join(
            str(answer.get(key, "")).strip()
            for key in ("bug", "explanation")
            if answer.get(key)
        )
    return ""


def _normalize_output(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.strip().splitlines())


def apply_multi_type_result(
    database: Session,
    assessment: Assessment,
    learner: Learner,
    topic: Topic,
    question_set: AssessmentTypesQuestionSet,
    answers: list[AssessmentAnswer],
) -> AssessmentResultResponse:
    question_by_id = {item.question_id: item for item in question_set.questions}
    answer_by_id = {item.question_id: item for item in answers}
    if len(answer_by_id) != len(answers) or set(answer_by_id) != set(question_by_id):
        raise ValueError("Submit exactly one answer for every assessment question")

    answer_values: dict[str, Any] = {}
    sandbox_submissions: list[dict[str, Any]] = []
    for question_id, question in question_by_id.items():
        answer = answer_by_id[question_id]
        if question.question_type == "mcq":
            if answer.selected_option is None or answer.learner_answer is not None:
                raise ValueError("MCQ questions require a selected option")
            if question.options is None or answer.selected_option >= len(question.options):
                raise ValueError(f"Invalid option for question: {question_id}")
            answer_values[question_id] = answer.selected_option
        elif answer.selected_option is not None or answer.learner_answer is None:
            raise ValueError(f"Question {question_id} requires a text or structured answer")
        elif question.question_type in {"coding", "debugging"}:
            if not isinstance(answer.learner_answer, dict):
                raise ValueError(f"Question {question_id} requires a code answer object")
            code = answer.learner_answer.get("code")
            if not isinstance(code, str) or not code.strip() or len(code) > 12000:
                raise ValueError(f"Question {question_id} requires non-empty Python code")
            if question.question_type == "debugging":
                if not answer.learner_answer.get("bug") or not answer.learner_answer.get("explanation"):
                    raise ValueError("Debugging answers require the bug and its explanation")
            answer_values[question_id] = answer.learner_answer
            sandbox_submissions.append(
                {
                    "question_id": question_id,
                    "language": question.language,
                    "source_code": code,
                    "function_name": question.function_name,
                    "test_cases": question.test_cases,
                    "execution_mode": "tests",
                }
            )
        elif question.question_type == "code_output":
            if not isinstance(answer.learner_answer, str) or not answer.learner_answer.strip():
                raise ValueError(f"Question {question_id} requires a predicted output")
            answer_values[question_id] = answer.learner_answer.strip()
            sandbox_submissions.append(
                {
                    "question_id": question_id,
                    "language": question.language,
                    "source_code": question.code,
                    "execution_mode": "stdout",
                    "test_cases": [],
                }
            )
        else:
            if not isinstance(answer.learner_answer, str) or not answer.learner_answer.strip():
                raise ValueError(f"Question {question_id} requires a non-empty text answer")
            if len(answer.learner_answer) > 12000:
                raise ValueError(f"Question {question_id} answer is too long")
            answer_values[question_id] = answer.learner_answer.strip()

    sandbox_results: dict[str, SandboxTaskResult] = {}
    if sandbox_submissions:
        sandbox_results, sandbox_source = evaluate_code_in_sandbox(sandbox_submissions)
    else:
        sandbox_source = "not_applicable"

    evaluations, evaluation_source = evaluate_open_responses(
        question_set.questions, answer_values, learner, topic
    )
    question_results: list[dict[str, Any]] = []
    concept_totals: dict[str, dict[str, float]] = {}
    type_totals: dict[str, dict[str, float]] = {}
    response_by_id = {
        record.question.question_id: record
        for record in database.scalars(
            select(AssessmentResponseRecord)
            .join(AssessmentQuestionRecord)
            .where(AssessmentQuestionRecord.assessment_id == assessment.id)
        ).all()
    }

    for question in question_set.questions:
        answer = answer_by_id[question.question_id]
        earned = 0.0
        feedback = ""
        source = "deterministic"
        evaluation = evaluations.get(question.question_id)
        if question.question_type == "mcq":
            correct = answer.selected_option == question.correct_option
            earned = float(question.points if correct else 0)
            feedback = question.explanation or (
                "Correct." if correct else "Review the topic concept and try a focused example."
            )
        elif question.question_type == "code_output":
            sandbox_result = sandbox_results[question.question_id]
            if sandbox_result.actual_output is None:
                raise RuntimeError("Code-output execution result is missing")
            correct = _normalize_output(str(answer.learner_answer)) == _normalize_output(
                sandbox_result.actual_output
            )
            earned = float(question.points if correct else 0)
            feedback = "Output matches." if correct else "The predicted output does not match."
            source = sandbox_source
        elif question.question_type in {"coding", "debugging"}:
            sandbox_result = sandbox_results[question.question_id]
            tests_score = sandbox_result.passed / sandbox_result.total
            earned = question.points * tests_score
            feedback = sandbox_result.feedback
            source = sandbox_source
            if question.question_type == "debugging":
                if evaluation is None:
                    raise RuntimeError("Debugging explanation evaluation is missing")
                earned = question.points * (
                    0.8 * tests_score + 0.2 * evaluation.score / question.points
                )
                feedback = f"{feedback} {evaluation.feedback}"
                source = f"{sandbox_source}+{evaluation_source}"
        else:
            if evaluation is None:
                raise RuntimeError("Open response evaluation is missing")
            earned = evaluation.score
            feedback = evaluation.feedback
            source = evaluation_source
        earned = round(max(0.0, min(float(question.points), earned)), 2)
        mastery_by_concept = {question.concept: earned / question.points}
        if question.question_type == "coding":
            mastery_by_concept.update(
                {concept: tests_score for concept in question.expected_concepts}
            )
        elif question.question_type in SUBJECTIVE_TYPES and evaluation:
            mastery_by_concept.update(
                {item.concept: item.mastery for item in evaluation.concept_mastery}
            )
        elif question.question_type == "debugging" and evaluation:
            mastery_by_concept.update(
                {
                    item.concept: 0.8 * tests_score + 0.2 * item.mastery
                    for item in evaluation.concept_mastery
                }
            )
        for concept, mastery in mastery_by_concept.items():
            concepts = concept_totals.setdefault(
                concept, {"earned": 0.0, "possible": 0.0, "count": 0}
            )
            concepts["earned"] += mastery
            concepts["possible"] += 1
            concepts["count"] += 1
        type_bucket = type_totals.setdefault(
            question.question_type, {"earned_points": 0.0, "total_points": 0.0}
        )
        type_bucket["earned_points"] += earned
        type_bucket["total_points"] += question.points
        serialized_answer = answer_values[question.question_id]
        if isinstance(serialized_answer, dict):
            response_answer: Any = dict(serialized_answer)
        else:
            response_answer = serialized_answer
        saved_response = response_by_id.get(question.question_id)
        if saved_response is None:
            question_record = database.scalar(
                select(AssessmentQuestionRecord).where(
                    AssessmentQuestionRecord.assessment_id == assessment.id,
                    AssessmentQuestionRecord.question_id == question.question_id,
                )
            )
            if question_record is None:
                raise RuntimeError("Assessment question persistence is missing")
            saved_response = AssessmentResponseRecord(
                question=question_record,
                learner_answer_json=response_answer,
                score=earned,
                feedback_json={"feedback": feedback},
                evaluation_source=source,
                evaluated_at=datetime.utcnow(),
            )
            database.add(saved_response)
        else:
            saved_response.learner_answer_json = response_answer
            saved_response.score = earned
            saved_response.feedback_json = {"feedback": feedback}
            saved_response.evaluation_source = source
            saved_response.evaluated_at = datetime.utcnow()
        question_results.append(
            {
                "question_id": question.question_id,
                "question_type": question.question_type,
                "concept": question.concept,
                "points": question.points,
                "earned_points": earned,
                "percentage": round(earned / question.points * 100, 1),
                "feedback": feedback,
                "evaluation_source": source,
                "strengths": evaluation.strengths if evaluation else [],
                "missing_concepts": evaluation.missing_concepts if evaluation else [],
            }
        )

    total_points = sum(int(item["total_points"]) for item in type_totals.values())
    earned_points = round(sum(item["earned_points"] for item in type_totals.values()), 2)
    percentage = round(earned_points / total_points * 100, 1) if total_points else 0.0
    for bucket in type_totals.values():
        bucket["percentage"] = round(bucket["earned_points"] / bucket["total_points"] * 100, 1)
    concept_results: list[ConceptResult] = []
    weak_concepts: list[str] = []
    strong_concepts: list[str] = []
    for concept, bucket in concept_totals.items():
        latest_score = bucket["earned"] / bucket["possible"]
        updated_skill = _update_skill(database, learner.id, concept, latest_score)
        concept_score = updated_skill.score
        level = classify_score(latest_score)
        concept_results.append(
            ConceptResult(
                concept=concept,
                correct_count=round(bucket["earned"]),
                total_questions=int(bucket["count"]),
                score=round(latest_score, 3),
                percentage=round(latest_score * 100),
                level=level,
            )
        )
        if level == "weak":
            weak_concepts.append(concept)
        elif level == "strong":
            strong_concepts.append(concept)
        _update_weakness(
            database,
            learner.id,
            topic.id,
            concept,
            latest_score,
            [
                question_id
                for question_id, item in question_by_id.items()
                if item.concept == concept or concept in item.expected_concepts
            ],
            concept_score,
        )

    weak_types = [name for name, bucket in type_totals.items() if bucket["percentage"] < 50]
    practice_types = [name for name, bucket in type_totals.items() if bucket["percentage"] < 80]
    if weak_types or weak_concepts:
        action_type = "remediate"
        next_status = "remediation"
    elif practice_types:
        action_type = "practice"
        next_status = "in_progress"
    else:
        action_type = "continue"
        next_status = "completed"
    progress = database.scalar(
        select(TopicProgress).where(
            TopicProgress.learner_id == learner.id,
            TopicProgress.topic_id == topic.id,
        )
    )
    if progress is None:
        progress = TopicProgress(learner_id=learner.id, topic_id=topic.id)
        database.add(progress)
    progress.status = next_status
    progress.mastery_score = earned_points / total_points if total_points else 0.0
    progress.attempt_count += 1
    progress.last_activity_at = datetime.utcnow()
    database.flush()
    target_topic_id, target_topic_title = _adapt_path(
        database, learner, topic.id, topic.course_id, action_type
    )
    recommendation = _recommendation(
        action_type, topic, weak_concepts, target_topic_id, target_topic_title
    )
    if action_type in {"remediate", "practice"}:
        remediation, remediation_source = generate_remediation_aid(
            learner,
            topic,
            weak_concepts
            or [
                concept
                for question in question_by_id.values()
                for concept in question.expected_concepts
            ][:3],
            percentage, recommendation.remediation,
        )
        recommendation.remediation = remediation.explanation
        recommendation.practice_suggestion = remediation.practice_suggestion
        recommendation.remediation_source = remediation_source
        recommendation.alternative_explanation = remediation.alternative_explanation
        recommendation.example = remediation.example
        recommendation.remediation_next_action = remediation.next_action
        assessment.feedback_json = {
            **(assessment.feedback_json or {}),
            "remediation": {**remediation.model_dump(), "source": remediation_source},
        }

    developing_concepts = [
        result.concept
        for result in concept_results
        if result.concept not in weak_concepts and result.concept not in strong_concepts
    ]
    interpretation, interpretation_source = interpret_skill_results(
        learner, round(percentage), weak_concepts, developing_concepts, strong_concepts
    )
    assessment.feedback_json = {
        **(assessment.feedback_json or {}),
        "interpretation": {**interpretation.model_dump(), "source": interpretation_source},
        "type_results": type_totals,
        "concept_results": [item.model_dump() for item in concept_results],
        "weak_concepts": weak_concepts,
        "strong_concepts": strong_concepts,
        "recommendation": recommendation.model_dump(),
        "question_results": question_results,
    }
    assessment.answers_json = [
        {
            "question_id": item["question_id"],
            "learner_answer": answer_values[item["question_id"]],
            "score": item["earned_points"],
            "feedback": item["feedback"],
            "evaluation_source": item["evaluation_source"],
        }
        for item in question_results
    ]
    assessment.total_points = total_points
    assessment.earned_points = earned_points
    assessment.percentage = percentage
    assessment.score = earned_points / total_points if total_points else 0.0
    assessment.status = "completed"
    assessment.completed_at = datetime.utcnow()
    database.add(
        Recommendation(
            learner_id=learner.id,
            action_type=action_type,
            topic_id=target_topic_id,
            reason=recommendation.summary,
        )
    )
    database.commit()
    return AssessmentResultResponse(
        assessment_id=assessment.id,
        learner_id=learner.id,
        course_id=topic.course_id,
        topic_id=topic.id,
        topic_title=display_topic_title(topic.title),
        score=round(earned_points),
        percentage=percentage,
        correct_count=round(earned_points),
        total_questions=len(question_set.questions),
        concept_results=concept_results,
        weak_concepts=weak_concepts,
        strong_concepts=strong_concepts,
        recommendation=recommendation,
        total_points=total_points,
        earned_points=earned_points,
        type_results=type_totals,
        selected_types=assessment.selected_types or [],
        ai_interpretation={**interpretation.model_dump(), "source": interpretation_source},
        question_results=question_results,
    )


def persisted_multi_type_result(
    assessment: Assessment, learner: Learner, topic: Topic
) -> AssessmentResultResponse:
    feedback = assessment.feedback_json or {}
    saved_concepts = feedback.get("concept_results", [])
    saved_recommendation = feedback.get("recommendation")
    if not isinstance(saved_recommendation, dict):
        raise RuntimeError("Persisted assessment recommendation is missing")
    recommendation = RecommendationResponse.model_validate(saved_recommendation)
    interpretation = feedback.get("interpretation")
    return AssessmentResultResponse(
        assessment_id=assessment.id,
        learner_id=learner.id,
        course_id=topic.course_id,
        topic_id=topic.id,
        topic_title=display_topic_title(topic.title),
        score=round(assessment.earned_points or 0),
        percentage=assessment.percentage or 0.0,
        correct_count=round(assessment.earned_points or 0),
        total_questions=len(assessment.questions_json),
        concept_results=[ConceptResult.model_validate(item) for item in saved_concepts],
        weak_concepts=feedback.get("weak_concepts", []),
        strong_concepts=feedback.get("strong_concepts", []),
        recommendation=recommendation,
        total_points=assessment.total_points,
        earned_points=assessment.earned_points,
        type_results=feedback.get("type_results", {}),
        selected_types=assessment.selected_types or ["mcq"],
        ai_interpretation=interpretation,
        question_results=feedback.get("question_results", []),
    )
