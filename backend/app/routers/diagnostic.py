from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Assessment, Learner, SkillScore
from ..schemas import (
    DiagnosticGenerateResponse,
    DiagnosticQuestionPublic,
    DiagnosticSubmitRequest,
    DiagnosticSubmitResponse,
)
from ..services.diagnostic_service import generate_diagnostic, score_diagnostic
from .learners import build_skill_analysis


router = APIRouter(prefix="/api/learners/{learner_id}/diagnostic", tags=["diagnostic"])


@router.post("/generate", response_model=DiagnosticGenerateResponse)
def generate_learner_diagnostic(
    learner_id: int, database: Session = Depends(get_db)
) -> DiagnosticGenerateResponse:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")

    question_set, generated_by = generate_diagnostic(learner, database)
    assessment = Assessment(
        learner_id=learner_id,
        assessment_type="diagnostic",
        questions_json=[question.model_dump() for question in question_set.questions],
    )
    database.add(assessment)
    database.commit()
    database.refresh(assessment)
    return DiagnosticGenerateResponse(
        assessment_id=assessment.id,
        questions=[
            DiagnosticQuestionPublic(
                id=question.id,
                question=question.question,
                options=question.options,
            )
            for question in question_set.questions
        ],
        generated_by=generated_by,
    )


@router.post("/{assessment_id}/submit", response_model=DiagnosticSubmitResponse)
def submit_learner_diagnostic(
    learner_id: int,
    assessment_id: int,
    payload: DiagnosticSubmitRequest,
    database: Session = Depends(get_db),
) -> DiagnosticSubmitResponse:
    if not database.get(Learner, learner_id):
        raise HTTPException(status_code=404, detail="Learner not found")

    assessment = database.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.learner_id == learner_id,
            Assessment.assessment_type == "diagnostic",
        )
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Diagnostic assessment not found")
    if assessment.completed_at:
        raise HTTPException(status_code=409, detail="Diagnostic assessment is already submitted")

    try:
        score, concept_results, answer_results = score_diagnostic(
            assessment.questions_json, payload.answers
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    assessment.answers_json = answer_results
    assessment.score = score
    assessment.completed_at = datetime.utcnow()

    for concept, result in concept_results.items():
        skill = database.scalar(
            select(SkillScore).where(
                SkillScore.learner_id == learner_id,
                SkillScore.concept == concept,
            )
        )
        if skill:
            combined_evidence = skill.evidence_count + result["total"]
            skill.score = (
                skill.score * skill.evidence_count + result["score"] * result["total"]
            ) / combined_evidence
            skill.evidence_count = combined_evidence
            skill.confidence = min(1.0, combined_evidence / 3)
            skill.source = "diagnostic"
        else:
            database.add(
                SkillScore(
                    learner_id=learner_id,
                    concept=concept,
                    score=result["score"],
                    evidence_count=result["total"],
                    confidence=min(1.0, result["total"] / 3),
                    source="diagnostic",
                )
            )

    database.commit()
    skills = database.scalars(
        select(SkillScore).where(SkillScore.learner_id == learner_id)
    ).all()
    analysis = build_skill_analysis(learner_id, skills)
    return DiagnosticSubmitResponse(
        assessment_id=assessment_id,
        answered_questions=len(payload.answers),
        **analysis.model_dump(),
    )
