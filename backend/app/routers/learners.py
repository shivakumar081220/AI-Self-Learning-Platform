from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..goal_catalog import GOAL_BY_KEY, GOAL_OPTIONS
from ..models import Assessment, Learner, LearningGoal, LearningPath, Recommendation, SkillScore, Topic, TopicProgress
from ..schemas import (
    GoalOption,
    LearnerCreate,
    LearnerResponse,
    SkillAnalysisResponse,
    SkillScoreResponse,
    LatestAssessmentSummary,
    LearnerSummaryResponse,
    RecommendationResponse,
)


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


@router.get("/goals", response_model=list[GoalOption])
def list_goals() -> list[GoalOption]:
    return GOAL_OPTIONS


@router.post("/learners", response_model=LearnerResponse, status_code=status.HTTP_201_CREATED)
def create_learner(payload: LearnerCreate, database: Session = Depends(get_db)) -> Learner:
    if payload.goal_key and payload.goal_key not in GOAL_BY_KEY:
        raise HTTPException(status_code=422, detail="Unknown Generative AI learning goal")

    selected_goal = payload.custom_goal or GOAL_BY_KEY[payload.goal_key].label
    learner = Learner(
        name=payload.name,
        experience_level=payload.experience_level,
        goal_text=selected_goal,
        track="generative_ai",
    )
    learner.goals.append(
        LearningGoal(
            title=selected_goal,
            track="generative_ai",
            is_active=True,
        )
    )
    database.add(learner)
    database.commit()
    database.refresh(learner)
    return learner


@router.get("/learners/{learner_id}", response_model=LearnerResponse)
def get_learner(learner_id: int, database: Session = Depends(get_db)) -> Learner:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    return learner


@router.get("/learners/{learner_id}/skills", response_model=SkillAnalysisResponse)
def get_skill_analysis(
    learner_id: int, database: Session = Depends(get_db)
) -> SkillAnalysisResponse:
    if not database.get(Learner, learner_id):
        raise HTTPException(status_code=404, detail="Learner not found")
    skills = database.scalars(
        select(SkillScore).where(SkillScore.learner_id == learner_id)
    ).all()
    return build_skill_analysis(learner_id, skills)


@router.get("/learners/{learner_id}/summary", response_model=LearnerSummaryResponse)
def get_learner_summary(
    learner_id: int, database: Session = Depends(get_db)
) -> LearnerSummaryResponse:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
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
        .where(Assessment.learner_id == learner_id, Assessment.completed_at.is_not(None), Assessment.topic_id.is_not(None))
        .order_by(Assessment.completed_at.desc())
    )
    latest_summary = None
    if latest_assessment and latest_assessment.topic_id:
        topic = database.get(Topic, latest_assessment.topic_id)
        if topic and latest_assessment.score is not None:
            latest_summary = LatestAssessmentSummary(
                topic_id=topic.id,
                topic_title=topic.title,
                percentage=round(latest_assessment.score * 100, 1),
            )
    recommendation_record = database.scalar(
        select(Recommendation)
        .where(Recommendation.learner_id == learner_id)
        .order_by(Recommendation.created_at.desc())
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
