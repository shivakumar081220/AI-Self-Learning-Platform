from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Assessment, Learner, LearningPath, Recommendation, SkillScore, Topic, TopicProgress, Weakness
from ..schemas import (
    AssessmentAnswer,
    AssessmentQuestionSet,
    AssessmentResultResponse,
    ConceptResult,
    QuestionReviewItem,
    RecommendationResponse,
)
from .learning_ai_service import generate_remediation_aid
from .path_engine import generate_path_plan


WEAK_THRESHOLD = 0.50
STRONG_THRESHOLD = 0.80


def classify_score(score: float) -> str:
    if score < WEAK_THRESHOLD:
        return "weak"
    if score < STRONG_THRESHOLD:
        return "developing"
    return "strong"


def score_assessment(
    questions: list[dict[str, Any]], answers: list[AssessmentAnswer]
) -> tuple[int, dict[str, dict[str, Any]], list[dict[str, Any]]]:
    question_by_id = {question["question_id"]: question for question in questions}
    answer_ids = [answer.question_id for answer in answers]
    if len(answer_ids) != len(set(answer_ids)):
        raise ValueError("Each assessment question can be answered only once")
    if set(answer_ids) != set(question_by_id):
        raise ValueError("Submit exactly one answer for every assessment question")

    correct_count = 0
    concept_results: dict[str, dict[str, Any]] = {}
    stored_answers: list[dict[str, Any]] = []
    for answer in answers:
        question = question_by_id.get(answer.question_id)
        if question is None:
            raise ValueError(f"Unknown assessment question: {answer.question_id}")
        if answer.selected_option >= len(question["options"]):
            raise ValueError(f"Invalid option for question: {answer.question_id}")
        is_correct = answer.selected_option == question["correct_option"]
        correct_count += int(is_correct)
        result = concept_results.setdefault(
            question["concept"], {"correct": 0, "total": 0, "question_ids": []}
        )
        result["correct"] += int(is_correct)
        result["total"] += 1
        result["question_ids"].append(answer.question_id)
        stored_answers.append(
            {
                "question_id": answer.question_id,
                "selected_option": answer.selected_option,
                "is_correct": is_correct,
            }
        )
    return correct_count, concept_results, stored_answers


def _update_skill(
    database: Session,
    learner_id: int,
    concept: str,
    latest_score: float,
) -> SkillScore:
    skill = database.scalar(
        select(SkillScore).where(
            SkillScore.learner_id == learner_id,
            SkillScore.concept == concept,
        )
    )
    evidence_count = skill.evidence_count or 0 if skill else 0
    previous_score = skill.score or 0.0 if skill else 0.0
    if skill and evidence_count > 0:
        skill.score = round(0.6 * previous_score + 0.4 * latest_score, 4)
        skill.evidence_count = evidence_count + 1
        skill.confidence = min(1.0, skill.evidence_count / 3)
    else:
        skill = skill or SkillScore(learner_id=learner_id, concept=concept)
        skill.score = latest_score
        skill.evidence_count = max(1, evidence_count)
        skill.confidence = min(1.0, skill.evidence_count / 3)
        database.add(skill)
    skill.source = "topic_assessment"
    skill.updated_at = datetime.utcnow()
    return skill


def _update_weakness(
    database: Session,
    learner_id: int,
    topic_id: str,
    concept: str,
    latest_score: float,
    question_ids: list[str],
    updated_score: float,
) -> None:
    weakness = database.scalar(
        select(Weakness).where(
            Weakness.learner_id == learner_id,
            Weakness.topic_id == topic_id,
            Weakness.concept == concept,
            Weakness.status == "open",
        )
    )
    if latest_score < WEAK_THRESHOLD or updated_score < WEAK_THRESHOLD:
        if not weakness:
            weakness = Weakness(
                learner_id=learner_id,
                topic_id=topic_id,
                concept=concept,
            )
            database.add(weakness)
        weakness.severity = "high" if latest_score < WEAK_THRESHOLD else "medium"
        weakness.evidence = [{"source": "topic_assessment", "question_ids": question_ids, "score": latest_score}]
        weakness.status = "open"
        weakness.detected_at = datetime.utcnow()
    elif weakness:
        weakness.status = "resolved"
        weakness.evidence = [{"source": "topic_assessment", "score": latest_score, "resolution": "improved"}]


def _adapt_path(
    database: Session,
    learner: Learner,
    topic_id: str,
    action_type: str,
) -> tuple[str | None, str | None]:
    path = database.scalar(
        select(LearningPath)
        .where(LearningPath.learner_id == learner.id)
        .order_by(LearningPath.created_at.desc())
    )
    if not path:
        return None, None
    plan = generate_path_plan(database, learner)
    topics = plan["topics"]
    current_id = None
    if action_type in {"remediate", "practice", "reassess"}:
        current_id = topic_id
    if current_id not in {item["topic_id"] for item in topics}:
        current_id = next(
            (item["topic_id"] for item in topics if item["status"] != "completed"),
            None,
        )
    path.path_json = topics
    path.overall_rationale = plan["overall_rationale"]
    path.current_index = next(
        (index for index, item in enumerate(topics) if item["topic_id"] == current_id),
        len(topics),
    )
    return current_id, next(
        (item["title"] for item in topics if item["topic_id"] == current_id),
        None,
    )


def _recommendation(
    action_type: str,
    topic: Topic,
    weak_concepts: list[str],
    target_topic_id: str | None,
    target_topic_title: str | None,
) -> RecommendationResponse:
    concept_text = ", ".join(item.replace("_", " ") for item in weak_concepts)
    if action_type == "remediate":
        return RecommendationResponse(
            action_type="remediate",
            target_topic_id=target_topic_id,
            target_topic_title=target_topic_title,
            summary=f"Your result identified a weakness in {concept_text}. The path is holding this topic for remediation.",
            next_action="Review the weak concept using a simpler explanation and targeted practice, then reassess.",
            remediation=f"Review {concept_text} with a concrete analogy and one worked example before retrying the assessment.",
        )
    if action_type == "practice":
        return RecommendationResponse(
            action_type="practice",
            target_topic_id=target_topic_id,
            target_topic_title=target_topic_title,
            summary="Your result shows developing understanding, so the topic remains active for focused practice.",
            next_action="Review the examples and complete targeted practice before continuing.",
            remediation="Work through another example and explain the concept in your own words.",
        )
    return RecommendationResponse(
        action_type="continue",
        target_topic_id=target_topic_id,
        target_topic_title=target_topic_title,
        summary=f"You demonstrated strong understanding of {topic.title}.",
        next_action="Continue to the next recommended topic in your adaptive path.",
        remediation=None,
    )


def _build_question_review(
    question_set: AssessmentQuestionSet,
    answers: list[AssessmentAnswer],
) -> list[QuestionReviewItem]:
    answer_by_id = {answer.question_id: answer for answer in answers}
    review_items: list[QuestionReviewItem] = []
    for question in question_set.questions:
        answer = answer_by_id.get(question.question_id)
        review_items.append(
            QuestionReviewItem(
                question_id=question.question_id,
                question=question.question,
                options=question.options,
                selected_option=answer.selected_option if answer else None,
                correct_option=question.correct_option,
                is_correct=bool(answer and answer.selected_option == question.correct_option),
                concept=question.concept,
                explanation=question.explanation,
            )
        )
    return review_items


def apply_assessment_result(
    database: Session,
    assessment: Assessment,
    learner: Learner,
    topic: Topic,
    question_set: AssessmentQuestionSet,
    answers: list[AssessmentAnswer],
) -> AssessmentResultResponse:
    correct_count, raw_concepts, stored_answers = score_assessment(
        [question.model_dump() for question in question_set.questions], answers
    )
    total_questions = len(question_set.questions)
    percentage = round((correct_count / total_questions) * 100, 1)
    assessment.answers_json = stored_answers
    assessment.score = correct_count / total_questions
    assessment.completed_at = datetime.utcnow()

    concept_results: list[ConceptResult] = []
    weak_concepts: list[str] = []
    strong_concepts: list[str] = []
    for concept, result in raw_concepts.items():
        latest_score = result["correct"] / result["total"]
        skill = _update_skill(database, learner.id, concept, latest_score)
        level = classify_score(latest_score)
        concept_results.append(
            ConceptResult(
                concept=concept,
                correct_count=result["correct"],
                total_questions=result["total"],
                score=round(latest_score, 3),
                percentage=round(latest_score * 100),
                level=level,
            )
        )
        if level == "weak":
            weak_concepts.append(concept)
        elif level == "strong":
            strong_concepts.append(concept)
        _update_weakness(database, learner.id, topic.id, concept, latest_score, result["question_ids"], skill.score)

    topic_progress = database.scalar(
        select(TopicProgress).where(
            TopicProgress.learner_id == learner.id,
            TopicProgress.topic_id == topic.id,
        )
    )
    topic_progress = topic_progress or TopicProgress(learner_id=learner.id, topic_id=topic.id)
    topic_progress.mastery_score = assessment.score
    topic_progress.attempt_count += 1
    topic_progress.last_activity_at = datetime.utcnow()
    if percentage < 60:
        action_type = "remediate"
        topic_progress.status = "remediation"
    elif percentage < 80:
        action_type = "practice"
        topic_progress.status = "in_progress"
    else:
        action_type = "continue"
        topic_progress.status = "completed"
    database.add(topic_progress)

    target_topic_id, target_topic_title = _adapt_path(database, learner, topic.id, action_type)
    recommendation = _recommendation(
        action_type, topic, weak_concepts, target_topic_id, target_topic_title
    )
    if action_type in {"remediate", "practice"}:
        remediation_aid, remediation_source = generate_remediation_aid(
            learner,
            topic,
            weak_concepts,
            percentage,
            recommendation.remediation,
        )
        recommendation.remediation = remediation_aid.explanation
        recommendation.practice_suggestion = remediation_aid.practice_suggestion
        recommendation.remediation_source = remediation_source
        assessment.feedback_json = {
            **(assessment.feedback_json or {}),
            "remediation": {
                **remediation_aid.model_dump(),
                "source": remediation_source,
            },
        }
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
        topic_id=topic.id,
        topic_title=topic.title,
        score=correct_count,
        percentage=percentage,
        correct_count=correct_count,
        total_questions=total_questions,
        concept_results=concept_results,
        weak_concepts=weak_concepts,
        strong_concepts=strong_concepts,
        recommendation=recommendation,
        question_review=_build_question_review(question_set, answers),
    )