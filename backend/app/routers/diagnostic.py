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
    QuestionReviewItem,
    SkillAnalysisResponse,
    SkillInterpretationResponse,
    SkillScoreResponse,
)
from ..services.diagnostic_service import generate_diagnostic, score_diagnostic
from ..models import User
from ..security import ensure_learner_access, get_optional_user
from .learners import build_skill_analysis
from ..services.learning_ai_service import interpret_skill_results


router = APIRouter(prefix="/api/learners/{learner_id}/diagnostic", tags=["diagnostic"])


def _concept_result_response(concept: str, result: dict[str, float | int]) -> SkillScoreResponse:
    score = float(result["score"])
    if score < 0.5:
        level = "weak"
    elif score < 0.75:
        level = "developing"
    else:
        level = "strong"
    return SkillScoreResponse(
        concept=concept,
        score=round(score, 3),
        percentage=round(score * 100),
        level=level,
        evidence_count=int(result["total"]),
    )


def _diagnostic_question_review(assessment: Assessment) -> list[QuestionReviewItem]:
    answers_by_id = {answer["question_id"]: answer for answer in assessment.answers_json}
    return [
        QuestionReviewItem(
            question_id=question["id"],
            question=question["question"],
            options=question["options"],
            selected_option=answers_by_id[question["id"]]["selected_option"],
            correct_option=question["correct_option"],
            is_correct=answers_by_id[question["id"]]["is_correct"],
            concept=question["concept"],
            explanation=question["explanation"],
        )
        for question in assessment.questions_json
    ]


@router.post("/generate", response_model=DiagnosticGenerateResponse)
def generate_learner_diagnostic(
    learner_id: int, database: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
) -> DiagnosticGenerateResponse:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    ensure_learner_access(learner, user)

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


@router.get("/{assessment_id}", response_model=DiagnosticSubmitResponse)
def get_diagnostic_result(
    learner_id: int,
    assessment_id: int,
    database: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> DiagnosticSubmitResponse:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    ensure_learner_access(learner, user)
    assessment = database.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.learner_id == learner_id,
            Assessment.assessment_type == "diagnostic",
        )
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Diagnostic assessment not found")
    if not assessment.completed_at:
        raise HTTPException(status_code=409, detail="Diagnostic assessment has not been submitted")
    skills = database.scalars(select(SkillScore).where(SkillScore.learner_id == learner_id)).all()
    analysis = build_skill_analysis(learner_id, skills)
    stored_interpretation = (assessment.feedback_json or {}).get("ai_interpretation")
    return DiagnosticSubmitResponse(
        assessment_id=assessment.id,
        answered_questions=len(assessment.answers_json),
        question_review=_diagnostic_question_review(assessment),
        ai_interpretation=(
            SkillInterpretationResponse.model_validate(stored_interpretation)
            if stored_interpretation
            else None
        ),
        **analysis.model_dump(),
    )


@router.post("/{assessment_id}/submit", response_model=DiagnosticSubmitResponse)
def submit_learner_diagnostic(
    learner_id: int,
    assessment_id: int,
    payload: DiagnosticSubmitRequest,
    database: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> DiagnosticSubmitResponse:
    learner = database.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    ensure_learner_access(learner, user)

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

    concept_scores = sorted(
        (_concept_result_response(concept, result) for concept, result in concept_results.items()),
        key=lambda item: item.score,
    )
    analysis = SkillAnalysisResponse(
        learner_id=learner_id,
        overall_score=round(float(score), 3),
        overall_percentage=round(float(score) * 100),
        strong_areas=[item for item in concept_scores if item.level == "strong"],
        developing_areas=[item for item in concept_scores if item.level == "developing"],
        weak_areas=[item for item in concept_scores if item.level == "weak"],
        skills=concept_scores,
    )
    interpretation, interpretation_source = interpret_skill_results(
        learner,
        round(float(score) * 100),
        [item.concept for item in concept_scores if item.level == "weak"],
        [item.concept for item in concept_scores if item.level == "developing"],
        [item.concept for item in concept_scores if item.level == "strong"],
    )
    ai_interpretation = SkillInterpretationResponse(
        **interpretation.model_dump(),
        source=interpretation_source,
    )
    assessment.feedback_json = {
        **(assessment.feedback_json or {}),
        "ai_interpretation": ai_interpretation.model_dump(),
    }
    database.commit()
    return DiagnosticSubmitResponse(
        assessment_id=assessment_id,
        answered_questions=len(payload.answers),
        question_review=_diagnostic_question_review(assessment),
        ai_interpretation=ai_interpretation,
        **analysis.model_dump(),
    )
