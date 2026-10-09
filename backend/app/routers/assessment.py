from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Any

from ..database import get_db
from ..models import Assessment, AssessmentResponseRecord, Learner, LearningPath, Recommendation, Topic, TopicProgress
from ..schemas import (
    AssessmentGenerateResponse,
    AssessmentQuestionPublic,
    AssessmentQuestionSet,
    AssessmentResultResponse,
    AssessmentSubmitRequest,
    AssessmentTypesQuestionSet,
    GenerateAssessmentRequest,
    ConceptResult,
    QuestionReviewItem,
    RecommendationResponse,
)
from ..services.assessment_result_service import apply_assessment_result, classify_score
from ..services.assessment_service import generate_assessment_questions
from ..services.multi_type_assessment_service import (
    ASSESSMENT_VERSION,
    apply_multi_type_result,
    generate_assessment,
    persisted_multi_type_result,
    public_question,
    save_question_records,
)
from ..models import User
from ..security import ensure_learner_access, get_optional_user
from ..topic_titles import display_topic_title


router = APIRouter(prefix="/api/learners/{learner_id}", tags=["assessment"])


def _get_assessment_context(
    learner_id: int, topic_id: str, database: Session, require_completed: bool = True, user: User | None = None
) -> tuple[Learner, Topic, LearningPath, TopicProgress]:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    ensure_learner_access(learner, user)
    topic = database.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found in curated catalog")
    path = database.scalar(
        select(LearningPath)
        .where(
            LearningPath.learner_id == learner_id,
            LearningPath.course_id == topic.course_id,
        )
        .order_by(LearningPath.created_at.desc())
    )
    if not path or topic_id not in {item.get("topic_id") for item in path.path_json}:
        raise HTTPException(status_code=404, detail="Topic is not part of the learner's path")
    progress = database.scalar(
        select(TopicProgress).where(
            TopicProgress.learner_id == learner_id,
            TopicProgress.topic_id == topic_id,
        )
    )
    if require_completed and (not progress or progress.status != "completed"):
        raise HTTPException(
            status_code=400,
            detail="Complete the learning activity before starting its assessment",
        )
    return learner, topic, path, progress


def _public_response(
    assessment: Assessment, topic: Topic, source: str
) -> AssessmentGenerateResponse:
    if assessment.assessment_version == ASSESSMENT_VERSION:
        question_set = AssessmentTypesQuestionSet.model_validate(
            {"questions": assessment.questions_json}
        )
        saved_answers = {
            item.question_id: item.response.learner_answer_json
            for item in assessment.questions
            if item.response is not None
        }
        return AssessmentGenerateResponse(
            assessment_id=assessment.id,
            learner_id=assessment.learner_id,
            course_id=topic.course_id,
            topic_id=topic.id,
            topic_title=display_topic_title(topic.title),
            status="submitted" if assessment.completed_at else "pending",
            questions=[
                AssessmentQuestionPublic.model_validate(public_question(question))
                for question in question_set.questions
            ],
            source=source,
            selected_types=assessment.selected_types or [],
            question_count=len(question_set.questions),
            saved_answers=saved_answers,
        )
    question_set = AssessmentQuestionSet.model_validate({"questions": assessment.questions_json})
    return AssessmentGenerateResponse(
        assessment_id=assessment.id,
        learner_id=assessment.learner_id,
        course_id=topic.course_id,
        topic_id=topic.id,
        topic_title=display_topic_title(topic.title),
        status="submitted" if assessment.completed_at else "pending",
        questions=[
            AssessmentQuestionPublic(
                question_id=question.question_id,
                question=question.question,
                options=question.options,
                concept=question.concept,
                difficulty=question.difficulty,
            )
            for question in question_set.questions
        ],
        source=source,
        selected_types=["mcq"],
        question_count=len(question_set.questions),
    )


def _build_question_review(assessment: Assessment) -> list[QuestionReviewItem]:
    answer_by_id = {answer["question_id"]: answer for answer in assessment.answers_json}
    review_items: list[QuestionReviewItem] = []
    for question in assessment.questions_json:
        answer = answer_by_id.get(question["question_id"])
        selected_option = answer.get("selected_option") if answer else None
        review_items.append(
            QuestionReviewItem(
                question_id=question["question_id"],
                question=question["question"],
                options=question["options"],
                selected_option=selected_option,
                correct_option=question["correct_option"],
                is_correct=bool(answer and answer.get("is_correct")),
                concept=question["concept"],
                explanation=question.get("explanation", ""),
            )
        )
    return review_items


def _persisted_result(assessment: Assessment, topic: Topic, database: Session) -> AssessmentResultResponse:
    question_by_id = {question["question_id"]: question for question in assessment.questions_json}
    concept_state: dict[str, dict[str, int]] = {}
    for answer in assessment.answers_json:
        question = question_by_id[answer["question_id"]]
        result = concept_state.setdefault(question["concept"], {"correct": 0, "total": 0})
        result["correct"] += int(answer["is_correct"])
        result["total"] += 1
    concept_results = []
    weak = []
    strong = []
    for concept, result in concept_state.items():
        score = result["correct"] / result["total"]
        level = classify_score(score)
        concept_results.append(
            ConceptResult(
                concept=concept,
                correct_count=result["correct"],
                total_questions=result["total"],
                score=round(score, 3),
                percentage=round(score * 100),
                level=level,
            )
        )
        if level == "weak":
            weak.append(concept)
        elif level == "strong":
            strong.append(concept)
    path = database.scalar(
        select(LearningPath)
        .where(
            LearningPath.learner_id == assessment.learner_id,
            LearningPath.course_id == topic.course_id,
        )
        .order_by(LearningPath.created_at.desc())
    )
    path_topic_ids = [item.get("topic_id") for item in path.path_json if item.get("topic_id")] if path else []
    recommendation = (
        database.scalar(
            select(Recommendation)
            .where(
                Recommendation.learner_id == assessment.learner_id,
                Recommendation.topic_id.in_(path_topic_ids),
            )
            .order_by(Recommendation.created_at.desc())
        )
        if path_topic_ids
        else None
    )
    target_topic = database.get(Topic, recommendation.topic_id) if recommendation and recommendation.topic_id else None
    stored_remediation = (assessment.feedback_json or {}).get("remediation")
    action_type = recommendation.action_type if recommendation else "continue"
    summary = recommendation.reason if recommendation else "Assessment result saved."
    next_action = (
        "Review the weak concepts and reassess before continuing."
        if action_type == "remediate"
        else "Review focused examples before continuing."
        if action_type == "practice"
        else "Continue to the next recommended topic."
    )
    return AssessmentResultResponse(
        assessment_id=assessment.id,
        learner_id=assessment.learner_id,
        course_id=topic.course_id,
        topic_id=topic.id,
        topic_title=display_topic_title(topic.title),
        score=round((assessment.score or 0) * len(assessment.questions_json)),
        percentage=round((assessment.score or 0) * 100, 1),
        correct_count=round((assessment.score or 0) * len(assessment.questions_json)),
        total_questions=len(assessment.questions_json),
        concept_results=concept_results,
        weak_concepts=weak,
        strong_concepts=strong,
        recommendation=RecommendationResponse(
            action_type=action_type,
            target_topic_id=recommendation.topic_id if recommendation else None,
            target_topic_title=(
                display_topic_title(target_topic.title) if target_topic else None
            ),
            summary=summary,
            next_action=next_action,
            remediation=(
                stored_remediation["explanation"]
                if stored_remediation
                else "Review the weak concept using a simpler analogy and targeted practice."
                if action_type in {"remediate", "practice"}
                else None
            ),
            practice_suggestion=stored_remediation.get("practice_suggestion") if stored_remediation else None,
            remediation_source=stored_remediation.get("source") if stored_remediation else None,
            alternative_explanation=(
                stored_remediation.get("alternative_explanation") if stored_remediation else None
            ),
            example=stored_remediation.get("example") if stored_remediation else None,
            remediation_next_action=(
                stored_remediation.get("next_action") if stored_remediation else None
            ),
        ),
        question_review=_build_question_review(assessment),
    )


@router.post("/topics/{topic_id}/assessment/generate", response_model=AssessmentGenerateResponse)
def generate_topic_assessment(
    learner_id: int,
    topic_id: str,
    payload: GenerateAssessmentRequest | None = None,
    database: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> AssessmentGenerateResponse:
    learner, topic, _, progress = _get_assessment_context(
        learner_id, topic_id, database, require_completed=False, user=user
    )
    previous_assessments = database.scalars(
        select(Assessment)
        .where(
            Assessment.learner_id == learner_id,
            Assessment.topic_id == topic_id,
            Assessment.assessment_type == "topic",
            Assessment.completed_at.is_not(None),
        )
        .order_by(Assessment.created_at.asc())
    ).all()
    if (
        not progress
        or (not progress.lesson_completed and progress.status != "completed")
    ) and not previous_assessments:
        raise HTTPException(
            status_code=400,
            detail="Complete the learning activity before starting its assessment",
        )
    selected_types = payload.selected_types if payload else ["mcq"]
    question_count = payload.question_count if payload else 3
    effective_question_count = max(question_count, len(selected_types))
    pending_assessments = database.scalars(
        select(Assessment)
        .where(
            Assessment.learner_id == learner_id,
            Assessment.topic_id == topic_id,
            Assessment.assessment_type == "topic",
            Assessment.status == "pending",
        )
        .order_by(Assessment.created_at.desc())
    ).all()
    pending_assessment = next(
        (
            item
            for item in pending_assessments
            if item.assessment_version == ASSESSMENT_VERSION
            and set(item.selected_types or []) == set(selected_types)
            and len(item.questions_json) == effective_question_count
            and (item.feedback_json or {}).get("generation_difficulty") == topic.difficulty
        ),
        None,
    )
    if pending_assessment:
        source = (pending_assessment.feedback_json or {}).get(
            "generation_source", "curated_fallback"
        )
        return _public_response(pending_assessment, topic, source)

    if payload is None:
        pending_legacy_assessment = next(
            (
                item
                for item in pending_assessments
                if item.assessment_version == "legacy-mcq-v1"
            ),
            None,
        )
        if pending_legacy_assessment:
            source = (pending_legacy_assessment.feedback_json or {}).get(
                "generation_source", "curated_fallback"
            )
            return _public_response(pending_legacy_assessment, topic, source)
        previous_questions = [
            question
            for item in previous_assessments
            for question in item.questions_json
        ]
        question_set, source = generate_assessment_questions(
            database, topic, learner, previous_questions=previous_questions
        )
        assessment = Assessment(
            learner_id=learner_id,
            topic_id=topic_id,
            assessment_type="topic",
            questions_json=[
                question.model_dump(mode="json")
                for question in question_set.questions
            ],
            selected_types=["mcq"],
            status="pending",
            total_points=len(question_set.questions),
            assessment_version="legacy-mcq-v1",
            feedback_json={"generation_source": source},
        )
        database.add(assessment)
        database.commit()
        database.refresh(assessment)
        return _public_response(assessment, topic, source)

    question_set, source = generate_assessment(
        database, topic, learner, selected_types, question_count
    )
    assessment = Assessment(
        learner_id=learner_id,
        topic_id=topic_id,
        assessment_type="topic",
        selected_types=selected_types,
        assessment_version=ASSESSMENT_VERSION,
        feedback_json={
            "generation_source": source,
            "generation_difficulty": topic.difficulty,
        },
    )
    database.add(assessment)
    database.flush()
    save_question_records(database, assessment, question_set)
    database.commit()
    database.refresh(assessment)
    return _public_response(assessment, topic, source)


@router.get(
    "/topics/{topic_id}/assessment/pending",
    response_model=AssessmentGenerateResponse | None,
)
def get_pending_topic_assessment(
    learner_id: int,
    topic_id: str,
    database: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> AssessmentGenerateResponse | None:
    learner, topic, _, _ = _get_assessment_context(
        learner_id, topic_id, database, require_completed=False, user=user
    )
    assessments = database.scalars(
        select(Assessment)
        .where(
            Assessment.learner_id == learner.id,
            Assessment.topic_id == topic.id,
            Assessment.assessment_type == "topic",
            Assessment.assessment_version == ASSESSMENT_VERSION,
            Assessment.status == "pending",
        )
        .order_by(Assessment.created_at.desc())
    ).all()
    assessment = next(
        (
            item
            for item in assessments
            if (item.feedback_json or {}).get("generation_difficulty") == topic.difficulty
        ),
        None,
    )
    if not assessment:
        return None
    source = (assessment.feedback_json or {}).get("generation_source", "curated_fallback")
    return _public_response(assessment, topic, source)


@router.put(
    "/assessments/{assessment_id}/responses",
    response_model=AssessmentGenerateResponse,
)
def save_assessment_responses(
    learner_id: int,
    assessment_id: int,
    payload: AssessmentSubmitRequest,
    database: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> AssessmentGenerateResponse:
    assessment = database.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.learner_id == learner_id,
            Assessment.assessment_type == "topic",
            Assessment.assessment_version == ASSESSMENT_VERSION,
            Assessment.status == "pending",
        )
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Pending assessment not found")
    learner = database.get(Learner, learner_id)
    ensure_learner_access(learner, user)
    topic = database.get(Topic, assessment.topic_id) if assessment.topic_id else None
    if not topic:
        raise HTTPException(status_code=404, detail="Assessment topic not found")
    question_set = AssessmentTypesQuestionSet.model_validate(
        {"questions": assessment.questions_json}
    )
    question_by_id = {item.question_id: item for item in question_set.questions}
    question_records = {
        item.question_id: item
        for item in assessment.questions
    }
    submitted_ids = [item.question_id for item in payload.answers]
    if len(submitted_ids) != len(set(submitted_ids)):
        raise HTTPException(status_code=422, detail="Each question can be saved only once")
    for answer in payload.answers:
        question = question_by_id.get(answer.question_id)
        record = question_records.get(answer.question_id)
        if not question or not record:
            raise HTTPException(status_code=422, detail="Unknown assessment question")
        if question.question_type == "mcq":
            if (
                answer.selected_option is None
                or question.options is None
                or answer.selected_option >= len(question.options)
            ):
                raise HTTPException(status_code=422, detail="Invalid MCQ answer")
            answer_data: Any = {"selected_option": answer.selected_option}
        else:
            if answer.selected_option is not None or answer.learner_answer is None:
                raise HTTPException(status_code=422, detail="Invalid answer format")
            answer_data = answer.learner_answer
        response = record.response
        if response is None:
            response = AssessmentResponseRecord(
                question=record,
                learner_answer_json=answer_data,
                score=0.0,
                feedback_json={},
                evaluation_source="pending",
                evaluated_at=None,
            )
            database.add(response)
        else:
            response.learner_answer_json = answer_data
            response.evaluation_source = "pending"
            response.score = 0.0
            response.feedback_json = {}
            response.evaluated_at = None
    database.commit()
    database.refresh(assessment)
    source = (assessment.feedback_json or {}).get("generation_source", "curated_fallback")
    return _public_response(assessment, topic, source)


@router.get(
    "/assessments/{assessment_id}",
    response_model=AssessmentGenerateResponse | AssessmentResultResponse,
)
def get_assessment(
    learner_id: int, assessment_id: int, database: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
) -> AssessmentGenerateResponse | AssessmentResultResponse:
    assessment = database.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.learner_id == learner_id,
            Assessment.assessment_type == "topic",
        )
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    learner = database.get(Learner, learner_id)
    ensure_learner_access(learner, user)
    topic = database.get(Topic, assessment.topic_id) if assessment.topic_id else None
    if not topic:
        raise HTTPException(status_code=500, detail="Assessment topic is unavailable")
    if assessment.completed_at:
        if assessment.assessment_version == ASSESSMENT_VERSION:
            return persisted_multi_type_result(assessment, learner, topic)
        return _persisted_result(assessment, topic, database)
    source = (assessment.feedback_json or {}).get("generation_source", "curated_fallback")
    return _public_response(assessment, topic, source)


@router.post("/assessments/{assessment_id}/submit", response_model=AssessmentResultResponse)
def submit_assessment(
    learner_id: int,
    assessment_id: int,
    payload: AssessmentSubmitRequest,
    database: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> AssessmentResultResponse:
    assessment = database.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.learner_id == learner_id,
            Assessment.assessment_type == "topic",
        )
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if assessment.completed_at:
        raise HTTPException(status_code=409, detail="Assessment is already submitted")
    learner, topic, _, _ = _get_assessment_context(learner_id, assessment.topic_id, database, False, user)
    try:
        if assessment.assessment_version == ASSESSMENT_VERSION:
            question_set = AssessmentTypesQuestionSet.model_validate(
                {"questions": assessment.questions_json}
            )
            return apply_multi_type_result(
                database, assessment, learner, topic, question_set, payload.answers
            )
        question_set = AssessmentQuestionSet.model_validate({"questions": assessment.questions_json})
        return apply_assessment_result(database, assessment, learner, topic, question_set, payload.answers)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
