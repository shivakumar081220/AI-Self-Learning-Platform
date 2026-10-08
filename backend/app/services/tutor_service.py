import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from ..config import settings
from ..models import Learner, Topic
from ..schemas import CodingExample
from ..topic_titles import display_topic_title
from ..track_catalog import TRACK_BY_ID
from .ai_provider import AIProviderError, log_ai_fallback, request_structured_json


logger = logging.getLogger(__name__)


class TutorAnswer(BaseModel):
    answer: str = Field(min_length=20, max_length=800)
    simple_explanation: str = Field(min_length=20, max_length=700)
    example: str = Field(min_length=10, max_length=700)
    coding_example: CodingExample | None = None
    key_points: list[str] = Field(min_length=2, max_length=4)
    related_topic: str | None = Field(default=None, max_length=160)
    suggested_next_action: str = Field(min_length=10, max_length=300)
    follow_up: str = Field(min_length=5, max_length=300)


def module_matches_question(question: str, course_topics: list[str]) -> bool:
    question_lower = question.lower()
    if "current module" in question_lower or "current topic" in question_lower:
        return True
    for title in course_topics:
        normalized_title = title.lower().strip()
        base_title = normalized_title.split("·", 1)[0].strip()
        if normalized_title in question_lower or (len(base_title) >= 4 and base_title in question_lower):
            return True
    return False


def _coding_example(track_id: str, topic: Topic | None) -> CodingExample:
    title = (
        display_topic_title(topic.title)
        if topic
        else TRACK_BY_ID.get(track_id, TRACK_BY_ID["generative_ai"]).name
    )
    examples = {
        "python_for_ai": (
            "Normalize a numeric feature",
            "values = [2.0, 4.0, 6.0]\nmean = sum(values) / len(values)\ncentered = [value - mean for value in values]\nprint(centered)",
            "Centering a feature makes each value relative to the observed mean.",
            "[-2.0, 0.0, 2.0]",
            "Data preparation changes what a model can learn from numeric inputs.",
            "Compute statistics from training data only to avoid leakage.",
        ),
        "machine_learning": (
            "Separate a small dataset",
            "rows = list(range(10))\nsplit = int(len(rows) * 0.8)\ntrain, test = rows[:split], rows[split:]\nprint(len(train), len(test))",
            "A holdout split estimates how a model performs on unseen examples.",
            "8 2",
            "Evaluation on held-out data helps detect overfitting.",
            "Do not evaluate a model on the same rows used to fit it.",
        ),
        "deep_learning": (
            "Apply a simple activation",
            "values = [-1.0, 0.5, 2.0]\nrelu = [max(0.0, value) for value in values]\nprint(relu)",
            "ReLU keeps positive activations and sets negative values to zero.",
            "[0.0, 0.5, 2.0]",
            "Activations add nonlinear behavior to neural network layers.",
            "A stack of only linear transformations remains linear overall.",
        ),
        "nlp": (
            "Tokenize a short sentence",
            'text = "Language models use context"\ntokens = text.lower().split()\nprint(tokens)',
            "Tokenization turns text into units a language workflow can process.",
            "['language', 'models', 'use', 'context']",
            "Text preprocessing makes model inputs explicit and inspectable.",
            "Whitespace tokenization is a teaching example, not a production tokenizer.",
        ),
        "generative_ai": (
            "Build a backend-owned model request",
            'from openai import OpenAI\n\nclient = OpenAI(api_key="your_api_key_here", base_url="https://openrouter.ai/api/v1")\nprint("Validate provider output in the backend")',
            "A backend-owned provider call keeps credentials out of the browser.",
            "Validate provider output in the backend",
            "Provider calls should be bounded and their output validated before use.",
            "Never place a real API key in frontend code or source control.",
        ),
        "llms": (
            "Estimate a simple context budget",
            'prompt = "Summarize the report"\nrough_tokens = len(prompt.split())\nprint(rough_tokens)',
            "A rough word count illustrates that prompts consume a finite context budget.",
            "4",
            "Context limits affect which instructions and evidence fit in one request.",
            "Word count is only an approximation; model tokenizers split text differently.",
        ),
        "rag": (
            "Chunk a document before retrieval",
            'document = "RAG retrieves evidence. It then generates a grounded answer."\nchunks = [part.strip() for part in document.split(".") if part.strip()]\nprint(chunks)',
            "Chunking creates smaller units that retrieval can rank for a question.",
            "['RAG retrieves evidence', 'It then generates a grounded answer']",
            "Retrieval should pass relevant evidence rather than a large document.",
            "Chunks that are too small can lose important context.",
        ),
        "ai_agents": (
            "Validate a tool before calling it",
            'tools = {"search": lambda query: f"Results for: {query}"}\nrequested = "search"\nif requested in tools:\n    print(tools[requested]("vector databases"))',
            "An application should allowlist tools and validate arguments before execution.",
            "Results for: vector databases",
            "Tool boundaries keep model-proposed actions under application control.",
            "Never execute arbitrary tool names or arguments from model output.",
        ),
    }
    example_title, code, explanation, output, why, mistake = examples.get(
        track_id, examples["generative_ai"]
    )
    return CodingExample(
        title=f"{example_title} for {title}",
        code=code,
        explanation=explanation,
        expected_output=output,
        why_it_matters=why,
        common_mistake=mistake,
    )


def _fallback_answer(
    learner: Learner,
    topic: Topic | None,
    question: str,
    weak_concepts: list[str],
    course_title: str | None,
    course_topics: list[str],
    completed_topics: list[str] | None = None,
    recent_assessments: list[dict[str, Any]] | None = None,
) -> TutorAnswer:
    track_id = topic.course.track_id if topic and topic.course else learner.track
    track_name = TRACK_BY_ID.get(track_id, TRACK_BY_ID["generative_ai"]).name
    current_title = display_topic_title(topic.title) if topic else "your current topic"
    asks_for_module = any(term in question.lower() for term in ("course", "module", "lesson"))
    if asks_for_module and course_title and not module_matches_question(question, course_topics):
        return TutorAnswer(
            answer=f"I don't see a matching module for that request in {course_title}, so I won't invent one. I can connect it to {current_title} instead.",
            simple_explanation=f"That subject is not currently covered in your {track_name} learning path.",
            example=f"Use one idea from {current_title} to examine a small example related to your goal: {learner.goal_text}.",
            coding_example=_coding_example(track_id, topic),
            key_points=[f"Your selected track is {track_name}.", "No matching module was found in the active course."],
            related_topic=display_topic_title(topic.title) if topic else None,
            suggested_next_action=f"Continue with {current_title} or switch tracks from your profile.",
            follow_up="Would you like to connect the question to the current topic?",
        )

    concept = str((topic.concept_tags or [track_name])[0]).replace("_", " ") if topic else track_name
    weak_context = ", ".join(item.replace("_", " ") for item in weak_concepts[:2])
    focus_text = f" Give extra attention to {weak_context}." if weak_context else ""
    answer = f"For {current_title}, {concept} is an important idea. {topic.description if topic else learner.goal_text}{focus_text}"
    example = f"For '{question.strip()}', apply {concept} to a small example related to {learner.goal_text}, then check the result."
    points = [f"The active track is {track_name}.", f"The current topic is {current_title}."]
    simple = f"In simple terms, {concept} helps you make progress toward {learner.goal_text}."
    related_topic = next(
        (
            title
            for title in course_topics
            if topic is None or title != display_topic_title(topic.title)
        ),
        None,
    )

    lowered = " ".join(str(item).lower() for item in (topic.concept_tags if topic else []))
    if track_id == "ai_agents" or "agent" in lowered or "tool" in question.lower():
        answer = "An agent should use a tool when it needs information or an action that text generation alone cannot provide. The application validates the tool and its arguments before execution."
        simple = "The model may suggest a tool, but application code decides whether that tool is allowed."
        example = "A support agent searches approved policy documents, then cites a retrieved passage in its answer."
        points = ["Tools add specific capabilities.", "Application code validates tool names and arguments."]
    elif track_id in {"rag", "nlp", "llms"} or any(term in lowered for term in ("embedding", "retriev", "grounding", "token")):
        answer = "Retrieval and language representations help select relevant evidence before a model writes an answer."
        simple = "Find useful source text first; then ask the model to explain it without making up missing facts."
        example = "A document assistant retrieves the policy paragraph most relevant to a question before generating a cited answer."
        points = ["Representations help compare meaning.", "Retrieved context is evidence, not a guarantee of correctness."]
    next_action = f"Continue to {related_topic}." if related_topic else f"Try the targeted practice for {current_title}."
    return TutorAnswer(
        answer=answer,
        simple_explanation=simple,
        example=example,
        coding_example=_coding_example(track_id, topic),
        key_points=points,
        related_topic=related_topic,
        suggested_next_action=next_action,
        follow_up="Which part of the example would you like to explore?",
    )


def _openrouter_answer(
    learner: Learner,
    topic: Topic | None,
    question: str,
    weak_concepts: list[str],
    course_title: str | None,
    course_topics: list[str],
    completed_topics: list[str],
    recent_assessments: list[dict[str, Any]],
) -> TutorAnswer:
    track_id = topic.course.track_id if topic and topic.course else learner.track
    track = TRACK_BY_ID.get(track_id, TRACK_BY_ID["generative_ai"])
    context = {
        "learner": {
            "track_id": track_id,
            "track_name": track.name,
            "experience_level": learner.experience_level,
            "goal": learner.goal_text,
            "target_outcome": learner.target_outcome,
            "weak_concepts": weak_concepts,
            "completed_topics": completed_topics,
            "recent_assessments": recent_assessments,
        },
        "topic": (
            {
                "title": display_topic_title(topic.title),
                "description": topic.description,
                "concepts": topic.concept_tags,
            }
            if topic
            else None
        ),
        "course": {"title": course_title, "allowed_module_titles": course_topics},
        "learner_question": question,
    }
    user_payload = {"context": context}
    answer = request_structured_json(
        operation="tutor_response",
        system_prompt=(
            "You are a patient AI tutor. Use the learner's selected track, goal, level, current topic, weak concepts, completed topics, and recent assessment results. "
            "Explain simply and concisely, include one example, key points, and a safe track-relevant coding example. "
            "If the question is unrelated to the goal, say so and redirect. Never invent courses or module titles or IDs. "
            "Set related_topic only to an exact title from allowed_module_titles, otherwise null. "
            "Return only the exact schema fields with their declared JSON types and no additional fields."
        ),
        user_payload=user_payload,
        response_model=TutorAnswer,
        temperature=0.4,
        max_tokens=1400,
    )
    if answer.related_topic and answer.related_topic not in course_topics:
        raise ValueError("Tutor referenced a module outside the learner's active path")
    return answer


def answer_tutor_question(
    learner: Learner,
    topic: Topic | None,
    question: str,
    weak_concepts: list[str],
    course_title: str | None = None,
    course_topics: list[str] | None = None,
    completed_topics: list[str] | None = None,
    recent_assessments: list[dict[str, Any]] | None = None,
) -> tuple[TutorAnswer, str]:
    course_topics = course_topics or []
    course_topics = [display_topic_title(title) for title in course_topics]
    completed_topics = completed_topics or []
    recent_assessments = recent_assessments or []
    if settings.openrouter_api_key:
        try:
            return (
                _openrouter_answer(
                    learner, topic, question, weak_concepts, course_title,
                    course_topics, completed_topics, recent_assessments,
                ),
                "openrouter",
            )
        except (AIProviderError, ValidationError, ValueError) as error:
            logger.warning(
                "AI operation used deterministic fallback; operation=tutor_response reason=%s",
                type(error).__name__,
            )
            log_ai_fallback("tutor_response", type(error).__name__)
    else:
        log_ai_fallback("tutor_response", "provider_not_configured")
    return (
        _fallback_answer(
            learner, topic, question, weak_concepts, course_title,
            course_topics, completed_topics, recent_assessments,
        ),
        "deterministic_fallback",
    )