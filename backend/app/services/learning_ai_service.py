from pydantic import BaseModel, Field, ValidationError

from ..config import settings
from ..models import Learner, Topic
from ..schemas import SkillAnalysisResponse
from .ai_provider import request_structured_json


class LearningInterpretation(BaseModel):
    summary: str = Field(min_length=20, max_length=600)
    focus_concepts: list[str] = Field(max_length=5)
    knowledge_level: str = Field(default="developing", min_length=3, max_length=80)
    knowledge_assessment: str = Field(default="", max_length=600)


class RemediationAid(BaseModel):
    explanation: str = Field(min_length=20, max_length=800)
    practice_suggestion: str = Field(min_length=10, max_length=600)


def _interpretation_fallback(
    overall_percentage: int,
    weak_concepts: list[str],
    developing_concepts: list[str],
    strong_concepts: list[str],
) -> LearningInterpretation:
    if weak_concepts:
        focus = ", ".join(weak_concepts[:3])
        summary = (
            f"Your deterministic score is {overall_percentage}%. You have useful foundations, and should strengthen "
            f"{focus} before moving into the most advanced applications."
        )
    elif developing_concepts:
        focus = ", ".join(developing_concepts[:3])
        summary = (
            f"Your deterministic score is {overall_percentage}%. Your understanding is developing; practice "
            f"{focus} with concrete examples before adding more complexity."
        )
    else:
        summary = (
            f"Your deterministic score is {overall_percentage}%. Your recorded concepts are strong; continue "
            "to the next topic and keep validating your understanding with applied practice."
        )
    return LearningInterpretation(
        summary=summary,
        focus_concepts=(weak_concepts or developing_concepts or strong_concepts)[:5],
        knowledge_level=("needs foundations" if overall_percentage < 50 else "developing" if overall_percentage < 75 else "ready to apply"),
        knowledge_assessment=(
            f"The recorded evidence suggests focusing first on {focus}."
            if weak_concepts
            else "The recorded evidence shows a developing foundation that will benefit from applied practice."
            if developing_concepts
            else "The recorded evidence supports moving into applied work while continuing to validate understanding."
        ),
    )


def interpret_skill_results(
    learner: Learner,
    overall_percentage: int,
    weak_concepts: list[str],
    developing_concepts: list[str],
    strong_concepts: list[str],
) -> tuple[LearningInterpretation, str]:
    fallback = _interpretation_fallback(
        overall_percentage, weak_concepts, developing_concepts, strong_concepts
    )
    if not settings.openrouter_api_key:
        return fallback, "deterministic_fallback"
    available_concepts = set(weak_concepts + developing_concepts + strong_concepts)
    try:
        interpretation = request_structured_json(
            system_prompt=(
                "Act as an AI learning assessor for the selected AI track. Analyze the supplied assessment evidence and explain the learner's current knowledge level and knowledge assessment. "
                "Never recalculate or alter the deterministic score. Use only the supplied concepts in focus_concepts. Adapt language to the learner's experience and goal. "
                "Return concise JSON matching the schema."
            ),
            user_payload={
                "schema": LearningInterpretation.model_json_schema(),
                "learner": {
                    "experience_level": learner.experience_level,
                    "goal": learner.goal_text,
                    "target_outcome": learner.target_outcome,
                    "track": learner.track,
                },
                "deterministic_score_percentage": overall_percentage,
                "assessment_evidence": {
                    "weak_concepts": weak_concepts,
                    "developing_concepts": developing_concepts,
                    "strong_concepts": strong_concepts,
                },
                "weak_concepts": weak_concepts,
                "developing_concepts": developing_concepts,
                "strong_concepts": strong_concepts,
            },
            response_model=LearningInterpretation,
            temperature=0.2,
            max_tokens=400,
        )
        if not set(interpretation.focus_concepts).issubset(available_concepts):
            raise ValueError("Interpretation referenced a concept outside learner results")
        return interpretation, "openrouter"
    except (Exception, ValidationError):
        return fallback, "deterministic_fallback"


def _remediation_fallback(topic: Topic, weak_concepts: list[str]) -> RemediationAid:
    focus = ", ".join(item.replace("_", " ") for item in weak_concepts[:3])
    focus = focus or ", ".join(str(item).replace("_", " ") for item in topic.concept_tags[:2])
    return RemediationAid(
        explanation=(
            f"For {topic.title}, revisit {focus} by stating the core idea before applying it. "
            "Keep the next attempt focused on one concept at a time; the score and progression decision remain application-controlled."
        ),
        practice_suggestion=f"Write a small example using {focus}, explain why it works, then retry the topic assessment.",
    )


def generate_remediation_aid(
    learner: Learner,
    topic: Topic,
    weak_concepts: list[str],
    percentage: float,
    deterministic_remediation: str | None,
) -> tuple[RemediationAid, str]:
    fallback = _remediation_fallback(topic, weak_concepts)
    if not settings.openrouter_api_key:
        return fallback, "deterministic_fallback"
    try:
        aid = request_structured_json(
            system_prompt=(
                "Create concise, level-appropriate remediation for a Generative AI learner. Use only supplied topic and weak-concept context. "
                "Do not change scores, mastery, path actions, or topic IDs. Return a short explanation and one targeted practice suggestion."
            ),
            user_payload={
                "schema": RemediationAid.model_json_schema(),
                "learner": {
                    "experience_level": learner.experience_level,
                    "goal": learner.goal_text,
                    "target_outcome": learner.target_outcome,
                },
                "topic": {"id": topic.id, "title": topic.title, "description": topic.description},
                "deterministic_percentage": percentage,
                "weak_concepts": weak_concepts,
                "deterministic_remediation": deterministic_remediation,
            },
            response_model=RemediationAid,
            temperature=0.3,
            max_tokens=500,
        )
        return aid, "openrouter"
    except (Exception, ValidationError):
        return fallback, "deterministic_fallback"
