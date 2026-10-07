import json
from typing import Any

from openai import OpenAI
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Topic
from ..schemas import DiagnosticQuestionSet


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


def _fallback_questions(database: Session, experience_level: str) -> DiagnosticQuestionSet:
    available_concepts = {
        concept
        for topic in database.scalars(select(Topic)).all()
        for concept in topic.concept_tags
    }
    questions = [
        question
        for question in CURATED_DIAGNOSTIC_QUESTIONS
        if question["concept"] in available_concepts
    ]
    if experience_level == "advanced":
        questions = questions[1:] + questions[:1]
    return DiagnosticQuestionSet.model_validate({"questions": questions})


def _openai_questions(learner: Any, database: Session) -> DiagnosticQuestionSet:
    topic_context = [
        {"id": topic.id, "concepts": topic.concept_tags, "description": topic.description}
        for topic in database.scalars(select(Topic)).all()
    ]
    prompt = {
        "learner": {
            "experience_level": learner.experience_level,
            "goal": learner.goal_text,
        },
        "topic_catalog": topic_context,
        "requirements": {
            "question_count": 8,
            "question_type": "MCQ",
            "minimum_concepts": 4,
            "internal_metadata": ["concept", "correct_option", "explanation"],
        },
    }
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You create rigorous diagnostic MCQs for a Generative AI learner. "
                    "Return only valid JSON with a questions array. Use only concepts present "
                    "in the supplied topic catalog. Keep correct_option zero-based."
                ),
            },
            {"role": "user", "content": json.dumps(prompt)},
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("OpenAI returned an empty diagnostic")
    return DiagnosticQuestionSet.model_validate_json(content)


def generate_diagnostic(learner: Any, database: Session) -> tuple[DiagnosticQuestionSet, str]:
    if settings.openai_api_key:
        try:
            return _openai_questions(learner, database), "openai"
        except (Exception, ValidationError):
            pass
    return _fallback_questions(database, learner.experience_level), "curated_fallback"


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
