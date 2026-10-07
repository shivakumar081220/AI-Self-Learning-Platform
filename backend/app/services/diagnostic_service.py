from typing import Any

from pydantic import ValidationError
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Assessment, GeneratedCourse, SkillScore, Topic, TopicPrerequisite
from ..schemas import DiagnosticQuestionSet
from ..track_catalog import TRACK_BY_ID
from .ai_provider import request_structured_json


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


def _fallback_questions(
    database: Session,
    experience_level: str,
    learner_id: int | None = None,
    track_id: str = "generative_ai",
) -> DiagnosticQuestionSet:
    available_concepts = {
        concept
        for topic in database.scalars(
            select(Topic).where(
                or_(
                    Topic.owner_user_id.is_(None),
                    and_(
                        Topic.owner_user_id == learner_id,
                        Topic.track_id == track_id,
                        Topic.is_active.is_(True),
                    ),
                )
            )
        ).all()
        for concept in topic.concept_tags
    }
    if track_id == "generative_ai":
        questions = [
            question
            for question in CURATED_DIAGNOSTIC_QUESTIONS
            if question["concept"] in available_concepts
        ]
    else:
        track = TRACK_BY_ID.get(track_id, TRACK_BY_ID["generative_ai"])
        concepts = list(available_concepts)[:4]
        if len(concepts) < 3:
            concepts = [track_id, f"{track_id}_foundations", f"{track_id}_practice"]
        questions = []
        for index, concept in enumerate(concepts[:4]):
            readable_concept = concept.replace("_", " ")
            questions.extend(
                [
                    {
                        "id": f"{track_id}-{index}-concept",
                        "question": f"What is a useful focus when learning {readable_concept} in the {track.name} track?",
                        "options": [
                            f"Understand and apply {readable_concept} in a small project",
                            "Skip the concept and rely on guesswork",
                            "Treat every result as correct without evaluation",
                            "Avoid practicing until the final lesson",
                        ],
                        "correct_option": 0,
                        "concept": concept,
                        "explanation": f"The {track.name} track connects {readable_concept} to practical, evaluated work.",
                    },
                    {
                        "id": f"{track_id}-{index}-practice",
                        "question": f"Which practice best supports progress with {readable_concept}?",
                        "options": [
                            f"Test a focused example and inspect the result",
                            "Remove all validation from the workflow",
                            "Use an unrelated topic instead",
                            "Assume advanced mastery immediately",
                        ],
                        "correct_option": 0,
                        "concept": f"{concept}_practice",
                        "explanation": "Small evaluated practice makes gaps visible and guides the next learning decision.",
                    },
                ]
            )
        for index, question in enumerate(questions):
            if index % 2:
                question["options"][0], question["options"][1] = question["options"][1], question["options"][0]
                question["correct_option"] = 1
    if experience_level == "advanced":
        questions = questions[1:] + questions[:1]
    return DiagnosticQuestionSet.model_validate({"questions": questions})


def _openrouter_questions(learner: Any, database: Session) -> DiagnosticQuestionSet:
    catalog = database.scalars(
        select(Topic).where(
            or_(
                Topic.owner_user_id.is_(None),
                and_(
                    Topic.owner_user_id == learner.user_id,
                    Topic.track_id == learner.track,
                    Topic.is_active.is_(True),
                ),
            )
        )
    ).all()
    available_concepts = {concept for topic in catalog for concept in topic.concept_tags}
    prerequisites = database.scalars(select(TopicPrerequisite)).all()
    prerequisites_by_topic: dict[str, list[str]] = {}
    for edge in prerequisites:
        prerequisites_by_topic.setdefault(edge.topic_id, []).append(edge.prerequisite_id)
    course = database.scalar(
        select(GeneratedCourse).where(GeneratedCourse.learner_id == learner.id)
    )
    course_topics = [
        {
            "title": topic.title,
            "concepts": topic.concept_tags,
            "prerequisites": prerequisites_by_topic.get(topic.id, []),
        }
        for topic in catalog
        if course and course.track_id == learner.track and topic.course_id == course.id
    ]
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
            "minimum_concepts": 4,
            "internal_metadata": ["concept", "correct_option", "explanation"],
        },
    }
    question_set = request_structured_json(
        system_prompt=(
            "Create rigorous diagnostic MCQs for the learner's selected AI track. Return a questions array. "
            "Use only concepts from available_concepts, align questions to the learner's goal and level, "
            "and keep correct_option zero-based. The answer key is server-side metadata."
        ),
        user_payload={"schema": DiagnosticQuestionSet.model_json_schema(), "context": context},
        response_model=DiagnosticQuestionSet,
        temperature=0.2,
        max_tokens=2800,
    )
    if any(question.concept not in available_concepts for question in question_set.questions):
        raise ValueError("Diagnostic contains a concept outside the topic catalog")
    return question_set


def generate_diagnostic(learner: Any, database: Session) -> tuple[DiagnosticQuestionSet, str]:
    if settings.openrouter_api_key:
        try:
            return _openrouter_questions(learner, database), "openrouter"
        except (Exception, ValidationError):
            pass
    return _fallback_questions(
        database,
        learner.experience_level,
        learner.user_id,
        learner.track,
    ), "curated_fallback"


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
