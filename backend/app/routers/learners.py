from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..goal_catalog import GOAL_BY_KEY, GOAL_OPTIONS
from ..models import Learner, LearningGoal, SkillScore
from ..schemas import (
    GoalOption,
    LearnerCreate,
    LearnerResponse,
    SkillAnalysisResponse,
    SkillScoreResponse,
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
