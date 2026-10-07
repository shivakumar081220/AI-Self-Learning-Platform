from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..goal_catalog import GOAL_BY_KEY, GOAL_OPTIONS
from ..models import Assessment, GeneratedCourse, Learner, LearningGoal, LearningPath, Recommendation, SkillScore, Topic, TopicProgress
from ..schemas import (
    AITrackOption,
    GoalOption,
    LearnerCreate,
    LearnerResponse,
    SkillAnalysisResponse,
    SkillScoreResponse,
    LatestAssessmentSummary,
    LearnerSummaryResponse,
    RecommendationResponse,
    TutorRequest,
    TutorResponse,
)
from ..models import User
from ..security import ensure_learner_access, get_optional_user, require_user
from ..services.tutor_service import answer_tutor_question, module_matches_question
from ..track_catalog import AI_TRACKS, LEGACY_GOAL_TRACK, TRACK_BY_ID, infer_track_id


router = APIRouter(prefix="/api", tags=["learners"])


def _skill_level(score: float) -> str:
    if score < 0.5:
        return "weak"
    if score < 0.75:
        return "developing"
    return "strong"


def _skill_response(skill: SkillScore) -> SkillScoreResponse:
    return SkillScoreResponse(
        concept=skill.concept,
        score=round(skill.score, 3),
        percentage=round(skill.score * 100),
        level=_skill_level(skill.score),
        evidence_count=skill.evidence_count,
    )


def build_skill_analysis(learner_id: int, skills: list[SkillScore]) -> SkillAnalysisResponse:
    results = sorted((_skill_response(skill) for skill in skills), key=lambda item: item.score)
    total_evidence = sum(skill.evidence_count for skill in skills)
    overall_score = (
        sum(skill.score * skill.evidence_count for skill in skills) / total_evidence
        if total_evidence
        else 0.0
    )

    return SkillAnalysisResponse(
        learner_id=learner_id,
        overall_score=round(overall_score, 3),
        overall_percentage=round(overall_score * 100),
        strong_areas=[item for item in results if item.level == "strong"],
        developing_areas=[item for item in results if item.level == "developing"],
        weak_areas=[item for item in results if item.level == "weak"],
        skills=results,
    )


def _selected_goal(payload: LearnerCreate) -> str:
    if payload.custom_goal:
        return payload.custom_goal
    if payload.goal_key in GOAL_BY_KEY:
        return GOAL_BY_KEY[payload.goal_key].label
    raise HTTPException(status_code=422, detail="Select a learning goal or provide a custom goal")


def _selected_track(payload: LearnerCreate, learner: Learner | None = None) -> str:
    if payload.track_id:
        if payload.track_id not in TRACK_BY_ID:
            raise HTTPException(status_code=422, detail="Unknown AI learning track")
        return payload.track_id
    if payload.goal_key in LEGACY_GOAL_TRACK:
        return LEGACY_GOAL_TRACK[payload.goal_key]
    if learner and learner.track in TRACK_BY_ID:
        return learner.track
    return infer_track_id(payload.custom_goal or "", payload.goal_key)


def _replace_active_goal(learner: Learner, goal_text: str, track_id: str) -> None:
    for goal in learner.goals:
        goal.is_active = False
    learner.goals.append(LearningGoal(title=goal_text, track=track_id, is_active=True))


@router.get("/goals", response_model=list[GoalOption])
def list_goals() -> list[GoalOption]:
    return GOAL_OPTIONS


@router.get("/tracks", response_model=list[AITrackOption])
def list_ai_tracks() -> list[AITrackOption]:
    return AI_TRACKS


@router.get("/learners/me", response_model=LearnerResponse)
def get_my_learner(user: User = Depends(require_user), database: Session = Depends(get_db)) -> Learner:
    learner = database.scalar(select(Learner).where(Learner.user_id == user.id))
    if not learner:
        raise HTTPException(status_code=404, detail="Complete onboarding to create your learner profile.")
    return learner


@router.put("/learners/me", response_model=LearnerResponse)
def update_my_learner(
    payload: LearnerCreate,
    user: User = Depends(require_user),
    database: Session = Depends(get_db),
) -> Learner:
    learner = database.scalar(select(Learner).where(Learner.user_id == user.id))
    if not learner:
        raise HTTPException(status_code=404, detail="Learner profile not found")
    goal_text = _selected_goal(payload)
    learner.track = _selected_track(payload, learner)
    learner.name = payload.name
    learner.experience_level = payload.experience_level
    learner.goal_text = goal_text
    learner.preferred_learning_style = payload.preferred_learning_style
    learner.target_outcome = payload.target_outcome
    _replace_active_goal(learner, goal_text, learner.track)
    database.commit()
    database.refresh(learner)
    return learner


@router.post("/learners", response_model=LearnerResponse, status_code=status.HTTP_201_CREATED)
def create_learner(
    payload: LearnerCreate,
    database: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Learner:
    selected_goal = _selected_goal(payload)
    selected_track = _selected_track(payload)
    if user:
        existing = database.scalar(select(Learner).where(Learner.user_id == user.id))
        if existing:
            ensure_learner_access(existing, user)
            existing.track = _selected_track(payload, existing)
            existing.name = payload.name
            existing.experience_level = payload.experience_level
            existing.goal_text = selected_goal
            existing.preferred_learning_style = payload.preferred_learning_style
            existing.target_outcome = payload.target_outcome
            _replace_active_goal(existing, selected_goal, existing.track)
            database.commit()
            database.refresh(existing)
            return existing
    learner = Learner(
        user_id=user.id if user else None,
        name=payload.name,
        experience_level=payload.experience_level,
        goal_text=selected_goal,
        track=selected_track,
        preferred_learning_style=payload.preferred_learning_style,
        target_outcome=payload.target_outcome,
    )
    learner.goals.append(
        LearningGoal(
            title=selected_goal,
            track=selected_track,
            is_active=True,
        )
    )
    database.add(learner)
    database.commit()
    database.refresh(learner)
    return learner


@router.get("/learners/{learner_id}", response_model=LearnerResponse)
def get_learner(learner_id: int, database: Session = Depends(get_db), user: User | None = Depends(get_optional_user)) -> Learner:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    ensure_learner_access(learner, user)
    return learner


@router.get("/learners/{learner_id}/skills", response_model=SkillAnalysisResponse)
def get_skill_analysis(
    learner_id: int, database: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
) -> SkillAnalysisResponse:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    ensure_learner_access(learner, user)
    skills = database.scalars(
        select(SkillScore).where(SkillScore.learner_id == learner_id)
    ).all()
    return build_skill_analysis(learner_id, skills)


@router.post("/learners/{learner_id}/tutor", response_model=TutorResponse)
def ask_learner_tutor(
    learner_id: int,
    payload: TutorRequest,
    database: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> TutorResponse:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    ensure_learner_access(learner, user)

    path = database.scalar(
        select(LearningPath)
        .where(LearningPath.learner_id == learner_id)
        .order_by(LearningPath.created_at.desc())
    )
    if payload.topic_id:
        path_topic_ids = {item.get("topic_id") for item in path.path_json} if path else set()
        if payload.topic_id not in path_topic_ids:
            raise HTTPException(status_code=404, detail="Tutor topic is not part of the learner's path")
        topic = database.get(Topic, payload.topic_id)
        if not topic or (topic.owner_user_id is not None and topic.owner_user_id != learner.user_id):
            raise HTTPException(status_code=404, detail="Tutor topic is not part of the learner's path")
    else:
        current_topic_id = (
            path.path_json[path.current_index].get("topic_id")
            if path and path.current_index < len(path.path_json)
            else None
        )
        topic = database.get(Topic, current_topic_id) if current_topic_id else None
    course = database.scalar(
        select(GeneratedCourse).where(GeneratedCourse.learner_id == learner_id)
    )
    course_topics = [item.get("title", "") for item in path.path_json] if path else []
    completed_topics = [
        topic.title
        for progress in database.scalars(
            select(TopicProgress).where(
                TopicProgress.learner_id == learner_id,
                TopicProgress.status == "completed",
            )
        ).all()
        if (topic := database.get(Topic, progress.topic_id)) is not None
    ]
    recent_assessments = [
        {"topic_id": item.topic_id, "score": item.score}
        for item in database.scalars(
            select(Assessment)
            .where(Assessment.learner_id == learner_id, Assessment.completed_at.is_not(None))
            .order_by(Assessment.completed_at.desc())
            .limit(5)
        ).all()
    ]
    question_lower = payload.question.lower()
    asks_for_module = any(term in question_lower for term in ("course", "module", "lesson"))
    matching_module = module_matches_question(payload.question, course_topics)
    module_available = not asks_for_module or matching_module

    weak_concepts = [
        skill.concept
        for skill in sorted(
            database.scalars(select(SkillScore).where(SkillScore.learner_id == learner_id)).all(),
            key=lambda item: item.score,
        )
        if skill.score < 0.75
    ][:3]
    tutor_answer, source = answer_tutor_question(
        learner,
        topic,
        payload.question,
        weak_concepts,
        course.title if course else None,
        course_topics,
        completed_topics,
        recent_assessments,
    )
    return TutorResponse(
        learner_id=learner_id,
        topic_id=topic.id if topic else payload.topic_id,
        topic_title=topic.title if topic else "Current learning topic",
        answer=tutor_answer.answer,
        simple_explanation=tutor_answer.simple_explanation,
        example=tutor_answer.example,
        coding_example=tutor_answer.coding_example,
        key_points=tutor_answer.key_points,
        weak_concepts=weak_concepts,
        related_topic=tutor_answer.related_topic,
        suggested_next_action=tutor_answer.suggested_next_action,
        follow_up=tutor_answer.follow_up,
        course_title=course.title if course else None,
        course_connection=(
            f"No matching module was found in {course.title if course else 'your current learning path'}; no module was invented."
            if not module_available
            else f"{topic.title} is part of {course.title} and supports your goal: {learner.goal_text}."
            if topic and course
            else f"This explanation is scoped to {topic.title}."
            if topic
            else "No course module is currently selected."
        ),
        module_title=topic.title if topic and module_available else None,
        source=source,
    )


@router.get("/learners/{learner_id}/summary", response_model=LearnerSummaryResponse)
def get_learner_summary(
    learner_id: int, database: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
) -> LearnerSummaryResponse:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    ensure_learner_access(learner, user)
    analysis = build_skill_analysis(
        learner_id,
        database.scalars(select(SkillScore).where(SkillScore.learner_id == learner_id)).all(),
    )
    path = database.scalar(
        select(LearningPath)
        .where(LearningPath.learner_id == learner_id)
        .order_by(LearningPath.created_at.desc())
    )
    progress = database.scalars(
        select(TopicProgress).where(TopicProgress.learner_id == learner_id)
    ).all()
    current_item = path.path_json[path.current_index] if path and path.current_index < len(path.path_json) else None
    completed_count = sum(
        1 for item in progress if item.status == "completed" or item.mastery_score >= 0.8
    )
    total_topics = len(path.path_json) if path else 0
    latest_assessment = database.scalar(
        select(Assessment)
        .where(Assessment.learner_id == learner_id, Assessment.completed_at.is_not(None))
        .order_by(Assessment.completed_at.desc())
    )
    latest_summary = None
    if latest_assessment and latest_assessment.score is not None:
        topic = database.get(Topic, latest_assessment.topic_id) if latest_assessment.topic_id else None
        if topic or latest_assessment.assessment_type == "diagnostic":
            latest_summary = LatestAssessmentSummary(
                topic_id=topic.id if topic else None,
                topic_title=topic.title if topic else "Diagnostic assessment",
                percentage=round(latest_assessment.score * 100, 1),
            )
    path_topic_ids = [item.get("topic_id") for item in path.path_json if item.get("topic_id")] if path else []
    recommendation_record = (
        database.scalar(
            select(Recommendation)
            .where(
                Recommendation.learner_id == learner_id,
                Recommendation.topic_id.in_(path_topic_ids),
            )
            .order_by(Recommendation.created_at.desc())
        )
        if path_topic_ids
        else None
    )
    recommendation = None
    if recommendation_record:
        target = database.get(Topic, recommendation_record.topic_id) if recommendation_record.topic_id else None
        recommendation = RecommendationResponse(
            action_type=recommendation_record.action_type,
            target_topic_id=recommendation_record.topic_id,
            target_topic_title=target.title if target else None,
            summary=recommendation_record.reason,
            next_action=(
                "Review weak concepts and reassess before continuing."
                if recommendation_record.action_type == "remediate"
                else "Review focused examples before continuing."
                if recommendation_record.action_type == "practice"
                else "Continue to the next recommended topic."
            ),
            remediation=None,
        )
    return LearnerSummaryResponse(
        learner_id=learner.id,
        name=learner.name,
        goal=learner.goal_text,
        current_topic_id=current_item.get("topic_id") if current_item else None,
        current_topic_title=current_item.get("title") if current_item else None,
        completed_topics=completed_count,
        total_topics=total_topics,
        progress_percentage=round((completed_count / total_topics) * 100) if total_topics else 0,
        overall_skill_percentage=analysis.overall_percentage,
        strong_concepts=analysis.strong_areas,
        developing_concepts=analysis.developing_areas,
        weak_concepts=analysis.weak_areas,
        latest_assessment=latest_summary,
        recommendation=recommendation,
    )
