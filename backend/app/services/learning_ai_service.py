import logging

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import settings
from ..models import Learner, Topic
from ..schemas import SkillAnalysisResponse
from ..topic_titles import display_topic_title
from .ai_provider import AIProviderError, log_ai_fallback, request_structured_json


logger = logging.getLogger(__name__)


class LearningInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=20, max_length=600)
    focus_concepts: list[str] = Field(max_length=5)
    knowledge_level: str = Field(default="developing", min_length=3, max_length=80)
    knowledge_assessment: str = Field(default="", max_length=600)


class RemediationAid(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weak_concepts: list[str] = Field(min_length=1, max_length=5)
    explanation: str = Field(min_length=20, max_length=800)
    alternative_explanation: str = Field(min_length=20, max_length=800)
    example: str = Field(min_length=10, max_length=800)
    practice_suggestion: str = Field(min_length=10, max_length=600)
    next_action: str = Field(min_length=10, max_length=300)


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
        log_ai_fallback("learning_interpretation", "provider_not_configured")
        return fallback, "deterministic_fallback"
    available_concepts = set(weak_concepts + developing_concepts + strong_concepts)
    try:
        interpretation = request_structured_json(
            operation="learning_interpretation",
            system_prompt=(
                "Act as an AI learning assessor for the selected AI track. Analyze the supplied assessment evidence "
                "and explain the learner's current knowledge level and knowledge assessment. Never recalculate or "
                "alter the deterministic score. Use only exact supplied concept identifiers in focus_concepts. "
                "Adapt language to the learner's experience and goal. The response must contain only the schema's "
                "fields with their declared JSON types; do not add fields."
            ),
            user_payload={
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
            max_tokens=1200,
        )
        if not set(interpretation.focus_concepts).issubset(available_concepts):
            logger.warning(
                "OpenRouter structured response failed semantic validation; "
                "operation=learning_interpretation model=%s validation_error=unknown_focus_concept "
                "missing_fields=[] unexpected_fields=[]",
                settings.openrouter_model,
            )
            raise ValueError("Interpretation referenced a concept outside learner results")
        return interpretation, "openrouter"
    except (AIProviderError, ValidationError, ValueError) as error:
        logger.warning(
            "AI operation used deterministic fallback; operation=learning_interpretation reason=%s",
            type(error).__name__,
        )
        log_ai_fallback("learning_interpretation", type(error).__name__)
        return fallback, "deterministic_fallback"


def _remediation_fallback(topic: Topic, weak_concepts: list[str]) -> RemediationAid:
    concepts = (weak_concepts or list(topic.concept_tags))[:5]
    focus = ", ".join(item.replace("_", " ") for item in concepts[:3])
    topic_title = display_topic_title(topic.title)
    return RemediationAid(
        weak_concepts=concepts,
        explanation=(
            f"For {topic_title}, revisit {focus} by stating the core idea before applying it. "
            "Keep the next attempt focused on one concept at a time; the score and progression decision remain application-controlled."
        ),
        alternative_explanation=(
            f"Think of {focus} as a set of ideas to test one at a time. "
            "A small worked example can make the relationship between them easier to see."
        ),
        example=(
            f"Choose one part of {focus}, write a tiny example, and explain the result in your own words."
        ),
        practice_suggestion=f"Write a small example using {focus}, explain why it works, then retry the topic assessment.",
        next_action="Complete the targeted practice, then retry the topic assessment.",
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
        log_ai_fallback("learning_remediation", "provider_not_configured")
        return fallback, "deterministic_fallback"
    try:
        available_concepts = set(weak_concepts or list(topic.concept_tags))
        aid = request_structured_json(
            operation="learning_remediation",
            system_prompt=(
                "Create concise, level-appropriate remediation for the supplied learner and topic. Return all schema "
                "fields: weak_concepts, explanation, alternative_explanation, example, practice_suggestion, and "
                "next_action. weak_concepts must contain only exact identifiers supplied in weak_concepts or topic "
                "concepts. Do not change scores, mastery, progression decisions, path actions, or topic IDs. "
                "Return only the exact JSON schema fields and declared types; do not add fields."
            ),
            user_payload={
                "learner": {
                    "experience_level": learner.experience_level,
                    "goal": learner.goal_text,
                    "target_outcome": learner.target_outcome,
                },
                "topic": {
                    "id": topic.id,
                    "title": display_topic_title(topic.title),
                    "description": topic.description,
                },
                "deterministic_percentage": percentage,
                "weak_concepts": weak_concepts,
                "deterministic_remediation": deterministic_remediation,
            },
            response_model=RemediationAid,
            temperature=0.3,
            max_tokens=1200,
        )
        if not set(aid.weak_concepts).issubset(available_concepts):
            logger.warning(
                "OpenRouter structured response failed semantic validation; "
                "operation=learning_remediation model=%s validation_error=unknown_weak_concept "
                "missing_fields=[] unexpected_fields=[]",
                settings.openrouter_model,
            )
            raise ValueError("Remediation referenced a concept outside supplied context")
        return aid, "openrouter"
    except (AIProviderError, ValidationError, ValueError) as error:
        logger.warning(
            "AI operation used deterministic fallback; operation=learning_remediation reason=%s",
            type(error).__name__,
        )
        log_ai_fallback("learning_remediation", type(error).__name__)
        return fallback, "deterministic_fallback"
