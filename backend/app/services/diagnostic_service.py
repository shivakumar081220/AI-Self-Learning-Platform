import logging
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Assessment, GeneratedCourse, Learner, SkillScore, Topic, TopicPrerequisite
from ..schemas import DiagnosticQuestionSet
from ..topic_titles import display_topic_title
from ..track_catalog import TRACK_BY_ID
from .ai_cache import get_or_generate_artifact
from .ai_provider import AIProviderError, request_structured_json


CURATED_DIAGNOSTIC_QUESTIONS = [
    {
        "id": "foundations-purpose",
        "question": "Which statement best describes a generative AI model?",
        "options": [
            "It creates new content by learning patterns from data",
            "It only stores exact copies of its training examples",
            "It can only classify inputs into fixed labels",
            "It replaces the need for any application logic",
        ],
        "correct_option": 0,
        "concept": "llm_fundamentals",
        "explanation": "Generative models learn patterns that let them produce new outputs such as text, images, or code.",
    },
    {
        "id": "prompt-context",
        "question": "Which prompt is most likely to produce a consistent structured response?",
        "options": [
            "Tell me something useful",
            "Return a JSON object with exactly the fields title and summary",
            "Be creative and do whatever you think is best",
            "Answer quickly without considering the context",
        ],
        "correct_option": 1,
        "concept": "prompt_design",
        "explanation": "Clear constraints and an explicit output contract reduce ambiguity and improve consistency.",
    },
    {
        "id": "tokenization-role",
        "question": "What is the role of tokenization in a language-model workflow?",
        "options": [
            "It converts text into units the model can process",
            "It guarantees that every answer is factually correct",
            "It stores a complete copy of the model weights",
            "It chooses which database rows to retrieve",
        ],
        "correct_option": 0,
        "concept": "tokenization",
        "explanation": "Tokenization maps text into model-readable units such as subwords or symbols.",
    },
    {
        "id": "embedding-use",
        "question": "What are embeddings most commonly used for in a RAG system?",
        "options": [
            "Measuring semantic similarity between content representations",
            "Increasing the model temperature automatically",
            "Replacing the language model's tokenizer",
            "Guaranteeing that retrieved content is current",
        ],
        "correct_option": 0,
        "concept": "embeddings",
        "explanation": "Embeddings represent meaning as vectors so related content can be compared and retrieved.",
    },
    {
        "id": "attention-focus",
        "question": "What does self-attention help a transformer model do?",
        "options": [
            "Relate each token to other relevant tokens in the sequence",
            "Remove every ambiguous word from the input",
            "Train without any examples or data",
            "Force every token to have the same representation",
        ],
        "correct_option": 0,
        "concept": "self_attention",
        "explanation": "Self-attention computes relationships between tokens so context can influence representations.",
    },
    {
        "id": "rag-grounding",
        "question": "What is the primary purpose of retrieval in retrieval-augmented generation?",
        "options": [
            "Provide relevant external context to ground the answer",
            "Make the model generate without seeing any prompt",
            "Guarantee a shorter answer regardless of the question",
            "Replace evaluation with a single similarity score",
        ],
        "correct_option": 0,
        "concept": "grounding",
        "explanation": "Retrieval supplies relevant context that the model can use to produce more grounded responses.",
    },
    {
        "id": "evaluation-quality",
        "question": "Which practice is most useful for evaluating an LLM application?",
        "options": [
            "Test representative examples against defined quality criteria",
            "Assume a fluent answer is always correct",
            "Evaluate only the most successful example",
            "Change the prompt after every single output",
        ],
        "correct_option": 0,
        "concept": "evaluation",
        "explanation": "Representative test cases and explicit criteria make quality changes measurable.",
    },
    {
        "id": "agent-tools",
        "question": "What distinguishes an AI agent from a one-shot text generation call?",
        "options": [
            "It can choose and use tools across multiple steps toward a goal",
            "It always produces a longer response",
            "It never needs constraints or validation",
            "It can only answer questions about its training data",
        ],
        "correct_option": 0,
        "concept": "tool_use",
        "explanation": "Agents coordinate model reasoning with tools and observations to complete multi-step tasks.",
    },
]
logger = logging.getLogger(__name__)


def _current_course(database: Session, learner_id: int) -> GeneratedCourse | None:
    learner = database.get(Learner, learner_id)
    if not learner:
        return None
    return database.scalar(
        select(GeneratedCourse).where(
            GeneratedCourse.learner_id == learner.id,
            GeneratedCourse.track_id == learner.track,
            GeneratedCourse.goal == learner.goal_text,
            GeneratedCourse.level == learner.experience_level,
            GeneratedCourse.target_outcome == learner.target_outcome,
        )
    )


def _diagnostic_topic_catalog(
    database: Session,
    learner_id: int | None,
    track_id: str,
    owner_user_id: int | None = None,
) -> list[Topic]:
    course = _current_course(database, learner_id) if learner_id is not None else None
    if course:
        return database.scalars(
            select(Topic).where(Topic.course_id == course.id, Topic.is_active.is_(True))
        ).all()
    global_topics = database.scalars(
        select(Topic).where(Topic.owner_user_id.is_(None))
    ).all()
    relevant_global_topics = [
        topic for topic in global_topics if topic.goal_relevance.get(track_id, 0) > 0
    ]
    if not relevant_global_topics:
        relevant_global_topics = global_topics
    owned_topics = database.scalars(
        select(Topic).where(
            Topic.owner_user_id == owner_user_id,
            Topic.track_id == track_id,
            Topic.is_active.is_(True),
        )
    ).all()
    return [*relevant_global_topics, *owned_topics]


def _fallback_questions(
    database: Session,
    experience_level: str,
    owner_user_id: int | None = None,
    track_id: str = "generative_ai",
    learner_id: int | None = None,
) -> DiagnosticQuestionSet:
    catalog = _diagnostic_topic_catalog(database, learner_id, track_id, owner_user_id)
    available_concepts = {concept for topic in catalog for concept in topic.concept_tags}
    course = _current_course(database, learner_id) if learner_id is not None else None
    if course:
        concepts_by_topic = {
            concept: topic for topic in catalog for concept in topic.concept_tags
        }
        concepts = sorted(available_concepts)
        if len(concepts) < 3:
            raise ValueError("Generated course does not define enough diagnostic concepts")
        questions = []
        for index in range(8):
            concept = concepts[index % len(concepts)]
            topic = concepts_by_topic[concept]
            questions.append(
                {
                    "id": f"course-{topic.id}-diagnostic-{index + 1}",
                    "question": (
                        f"Which approach best demonstrates understanding of {concept.replace('_', ' ')} "
                        f"in {display_topic_title(topic.title)}?"
                    ),
                    "options": [
                        f"Apply {concept.replace('_', ' ')} to a focused example and evaluate the result",
                        "Assume every model output is correct without checking it",
                        "Skip the concept and rely on unrelated material",
                        "Remove application constraints and testing",
                    ],
                    "correct_option": 0,
                    "concept": concept,
                    "difficulty": experience_level,
                    "explanation": topic.description[:500],
                }
            )
    elif track_id == "generative_ai":
        questions = [
            {**question, "difficulty": experience_level}
            for question in CURATED_DIAGNOSTIC_QUESTIONS
            if question["concept"] in available_concepts
        ]
    else:
        track = TRACK_BY_ID.get(track_id, TRACK_BY_ID["generative_ai"])
        concepts = sorted(available_concepts)[:8]
        if len(concepts) < 3:
            raise ValueError("Track does not define enough diagnostic concepts")
        questions = []
        for index in range(8):
            concept = concepts[index % len(concepts)]
            readable_concept = concept.replace("_", " ")
            questions.append(
                {
                    "id": f"{track_id}-diagnostic-{index + 1}",
                    "question": (
                        f"Which approach best supports learning {readable_concept} "
                        f"in the {track.name} track?"
                        if index % 2 == 0
                        else f"How should you check your understanding of {readable_concept}?"
                    ),
                    "options": [
                        f"Apply {readable_concept} to a focused example and evaluate the result",
                        "Skip the concept and rely on guesswork",
                        "Treat every result as correct without evaluation",
                        "Avoid practice until the end of the course",
                    ],
                    "correct_option": 0,
                    "concept": concept,
                    "difficulty": experience_level,
                    "explanation": (
                        f"The {track.name} track connects {readable_concept} to practical, evaluated work."
                    ),
                }
            )
        for index, question in enumerate(questions):
            if index % 2:
                question["options"][0], question["options"][1] = (
                    question["options"][1],
                    question["options"][0],
                )
                question["correct_option"] = 1
    if experience_level == "advanced":
        questions = questions[1:] + questions[:1]
    return DiagnosticQuestionSet.model_validate({"questions": questions})


def _openrouter_questions(learner: Any, database: Session) -> DiagnosticQuestionSet:
    catalog = _diagnostic_topic_catalog(
        database, learner.id, learner.track, learner.user_id
    )
    available_concepts = {concept for topic in catalog for concept in topic.concept_tags}
    prerequisites = database.scalars(
        select(TopicPrerequisite).where(
            TopicPrerequisite.topic_id.in_([topic.id for topic in catalog])
        )
    ).all()
    prerequisites_by_topic: dict[str, list[str]] = {}
    for edge in prerequisites:
        prerequisites_by_topic.setdefault(edge.topic_id, []).append(edge.prerequisite_id)
    course = _current_course(database, learner.id)
    course_topics = [
        {
            "title": display_topic_title(topic.title),
            "concepts": topic.concept_tags,
            "prerequisites": prerequisites_by_topic.get(topic.id, []),
        }
        for topic in catalog
        if course and course.track_id == learner.track and topic.course_id == course.id
    ]
    if course:
        available_concepts = {
            concept for topic in catalog for concept in topic.concept_tags
        }
    weak_concepts = [
        item.concept
        for item in database.scalars(
            select(SkillScore).where(
                SkillScore.learner_id == learner.id,
                SkillScore.score < 0.75,
            )
        ).all()
    ]
    latest_diagnostic = database.scalar(
        select(Assessment)
        .where(
            Assessment.learner_id == learner.id,
            Assessment.assessment_type == "diagnostic",
            Assessment.completed_at.is_not(None),
        )
        .order_by(Assessment.completed_at.desc())
    )
    context = {
        "learner": {
            "experience_level": learner.experience_level,
            "goal": learner.goal_text,
            "target_outcome": learner.target_outcome,
            "track": learner.track,
            "weak_concepts": weak_concepts,
            "previous_diagnostic_score": latest_diagnostic.score if latest_diagnostic else None,
        },
        "course_topics": course_topics,
        "available_concepts": sorted(available_concepts),
        "requirements": {
            "question_count": 8,
            "question_type": "MCQ",
            "minimum_concepts": 3,
            "internal_metadata": ["concept", "correct_option", "explanation"],
        },
    }
    question_set = request_structured_json(
        operation="diagnostic_questions",
        system_prompt=(
            "Create exactly eight rigorous diagnostic multiple-choice questions for the learner's selected AI "
            "track. Use only exact concept identifiers from available_concepts, cover at least three distinct "
            "concepts from the selected course topics, and use unique question IDs. Each question must have id "
            "(string), question (string), options (array of 3 to 5 strings), difficulty (beginner, intermediate, "
            "or advanced), correct_option (zero-based integer within options), concept (exact supplied identifier "
            "string), and explanation (string). These fields are required. "
            "correct_option and explanation are internal server-side grading metadata and must never be included "
            "in the learner-facing question response. Do not return any extra properties."
        ),
        user_payload={"context": context},
        response_model=DiagnosticQuestionSet,
        temperature=0.2,
        max_tokens=3200,
    )
    if any(question.concept not in available_concepts for question in question_set.questions):
        logger.warning(
            "OpenRouter structured response failed semantic validation; operation=diagnostic_questions "
            "model=%s http_status=200 response_type=DiagnosticQuestionSet "
            "validation_error=unknown_concept missing_fields=[] unexpected_fields=[]",
            settings.openrouter_model,
        )
        raise ValueError("Diagnostic contains a concept outside the topic catalog")
    return question_set


def _generate_diagnostic_uncached(
    learner: Any, database: Session
) -> tuple[DiagnosticQuestionSet, str]:
    if settings.openrouter_api_key:
        try:
            return _openrouter_questions(learner, database), "openrouter"
        except (AIProviderError, ValidationError, ValueError) as error:
            logger.warning(
                "AI operation used curated fallback; operation=diagnostic_questions reason=%s",
                type(error).__name__,
            )
    return _fallback_questions(
        database,
        learner.experience_level,
        learner.user_id,
        learner.track,
        learner.id,
    ), "curated_fallback"


def generate_diagnostic(learner: Any, database: Session) -> tuple[DiagnosticQuestionSet, str]:
    course = _current_course(database, learner.id)
    skill_state = [
        {"concept": item.concept, "score": item.score, "evidence_count": item.evidence_count}
        for item in database.scalars(
            select(SkillScore).where(SkillScore.learner_id == learner.id)
        ).all()
    ]
    latest_diagnostic = database.scalar(
        select(Assessment)
        .where(
            Assessment.learner_id == learner.id,
            Assessment.assessment_type == "diagnostic",
            Assessment.completed_at.is_not(None),
        )
        .order_by(Assessment.completed_at.desc())
    )
    return get_or_generate_artifact(
        database,
        learner_id=learner.id,
        operation="diagnostic_questions",
        key_context={
            "course_id": course.id if course else None,
            "track": learner.track,
            "goal": learner.goal_text,
            "experience_level": learner.experience_level,
            "target_outcome": learner.target_outcome,
            "skill_state": sorted(skill_state, key=lambda item: item["concept"]),
            "previous_diagnostic_score": latest_diagnostic.score if latest_diagnostic else None,
        },
        response_model=DiagnosticQuestionSet,
        generate=lambda: _generate_diagnostic_uncached(learner, database),
        fallback=lambda: _fallback_questions(
            database, learner.experience_level, learner.user_id, learner.track, learner.id
        ),
    )


def score_diagnostic(
    questions: list[dict[str, Any]], answers: list[Any]
) -> tuple[float, dict[str, dict[str, float | int]], list[dict[str, Any]]]:
    question_by_id = {question["id"]: question for question in questions}
    answer_ids = [answer.question_id for answer in answers]
    if len(answer_ids) != len(set(answer_ids)):
        raise ValueError("Each diagnostic question can be answered only once")
    if set(answer_ids) != set(question_by_id):
        raise ValueError("Submit exactly one answer for every diagnostic question")

    correct_count = 0
    concept_results: dict[str, dict[str, float | int]] = {}
    answer_results = []
    for answer in answers:
        question = question_by_id.get(answer.question_id)
        if question is None:
            raise ValueError(f"Unknown diagnostic question: {answer.question_id}")
        if answer.selected_option >= len(question["options"]):
            raise ValueError(f"Invalid option for question: {answer.question_id}")

        is_correct = answer.selected_option == question["correct_option"]
        correct_count += int(is_correct)
        concept = question["concept"]
        result = concept_results.setdefault(concept, {"correct": 0, "total": 0, "score": 0.0})
        result["correct"] += int(is_correct)
        result["total"] += 1
        result["score"] = result["correct"] / result["total"]
        answer_results.append(
            {
                "question_id": answer.question_id,
                "selected_option": answer.selected_option,
                "is_correct": is_correct,
            }
        )

    return correct_count / len(questions), concept_results, answer_results
