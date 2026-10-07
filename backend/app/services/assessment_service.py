from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Topic
from ..schemas import AssessmentQuestionSet
from .ai_provider import request_structured_json


QUESTION_BANK: dict[str, list[dict[str, Any]]] = {
    "ai-foundations": [
        {"question_id": "foundations-generative", "question": "What makes a model generative?", "options": ["It creates new outputs from learned patterns", "It only stores exact training records", "It only assigns fixed labels", "It replaces application validation"], "concept": "generative_models", "difficulty": "beginner", "correct_option": 0, "explanation": "Generative models learn patterns that let them produce new content."},
        {"question_id": "foundations-language", "question": "What is a language model primarily estimating?", "options": ["Likely token sequences given context", "A user's authorization level", "The database schema", "A guaranteed factual answer"], "concept": "llm_fundamentals", "difficulty": "beginner", "correct_option": 0, "explanation": "Language models estimate likely continuations from context."},
        {"question_id": "foundations-controls", "question": "Which responsibility should remain in application code?", "options": ["Permission and state updates", "Choosing fluent wording only", "Suggesting an analogy", "Drafting a summary"], "concept": "ai_fundamentals", "difficulty": "beginner", "correct_option": 0, "explanation": "Deterministic application logic should control permissions and state."},
    ],
    "prompt-engineering": [
        {"question_id": "prompt-constraints", "question": "Which prompt detail most improves output consistency?", "options": ["A clear output contract", "A vague request for creativity", "Removing all context", "Asking unrelated tasks together"], "concept": "prompt_design", "difficulty": "beginner", "correct_option": 0, "explanation": "Explicit constraints reduce ambiguity."},
        {"question_id": "prompt-examples", "question": "What is a useful role for a few-shot example?", "options": ["Show the expected behavior or format", "Guarantee factual correctness", "Replace validation", "Hide the task objective"], "concept": "few_shot_learning", "difficulty": "intermediate", "correct_option": 0, "explanation": "Examples clarify boundaries and response patterns."},
        {"question_id": "prompt-schema", "question": "What should happen after a model returns structured data?", "options": ["Validate it against a schema", "Execute it without checks", "Assume every field is present", "Use it as a score"], "concept": "structured_outputs", "difficulty": "intermediate", "correct_option": 0, "explanation": "Schema validation catches malformed or unsafe output."},
    ],
    "tokenization-embeddings": [
        {"question_id": "tokens-units", "question": "What does tokenization do?", "options": ["Maps text into model-readable units", "Retrieves database rows", "Guarantees correctness", "Adds tool permissions"], "concept": "tokenization", "difficulty": "beginner", "correct_option": 0, "explanation": "Tokenization creates the units processed by the model."},
        {"question_id": "embedding-space", "question": "What do embeddings represent?", "options": ["Meaning as vectors for comparison", "A complete model backup", "A fixed answer key", "Only token counts"], "concept": "embeddings", "difficulty": "beginner", "correct_option": 0, "explanation": "Embeddings place related meanings near one another in vector space."},
        {"question_id": "embedding-retrieval", "question": "How can embeddings support RAG?", "options": ["Compare a query vector with document vectors", "Replace every source document", "Guarantee current information", "Score the learner directly"], "concept": "vector_representation", "difficulty": "intermediate", "correct_option": 0, "explanation": "Vector similarity helps retrieve relevant candidate context."},
    ],
    "attention-transformers": [
        {"question_id": "attention-context", "question": "What does self-attention help a token do?", "options": ["Use relevant context from other tokens", "Forget sequence order", "Guarantee a factual answer", "Choose database permissions"], "concept": "self_attention", "difficulty": "intermediate", "correct_option": 0, "explanation": "Self-attention relates token representations using context."},
        {"question_id": "attention-position", "question": "Why do transformers need positional information?", "options": ["Attention alone does not encode order", "It stores the answer key", "It retrieves documents", "It validates JSON"], "concept": "positional_encoding", "difficulty": "intermediate", "correct_option": 0, "explanation": "Position distinguishes sequences with different order."},
        {"question_id": "attention-blocks", "question": "What is commonly repeated in a transformer?", "options": ["Attention and feed-forward blocks", "Only a database lookup", "A fixed answer string", "A permission check from the model"], "concept": "transformers", "difficulty": "intermediate", "correct_option": 0, "explanation": "Transformer layers combine attention and feed-forward processing."},
    ],
    "llm-application-patterns": [
        {"question_id": "patterns-validation", "question": "What should application code do with model output?", "options": ["Validate it before using it", "Trust it as executable code", "Use it as a final score", "Skip error handling"], "concept": "structured_outputs", "difficulty": "intermediate", "correct_option": 0, "explanation": "Validation is a boundary between model output and application state."},
        {"question_id": "patterns-tools", "question": "Who should enforce tool permissions?", "options": ["The application", "The model alone", "The prompt alone", "The user interface text"], "concept": "tool_calls", "difficulty": "intermediate", "correct_option": 0, "explanation": "The application controls access and validates arguments."},
        {"question_id": "patterns-evaluation", "question": "Why use representative evaluation examples?", "options": ["To detect quality regressions", "To avoid all deterministic logic", "To expose API keys", "To replace user goals"], "concept": "evaluation", "difficulty": "intermediate", "correct_option": 0, "explanation": "Evaluation makes quality changes measurable."},
    ],
    "retrieval-augmented-generation": [
        {"question_id": "rag-retrieval", "question": "What is the role of retrieval in RAG?", "options": ["Supply relevant external context", "Guarantee factual answers", "Remove the prompt", "Replace all evaluation"], "concept": "retrieval", "difficulty": "intermediate", "correct_option": 0, "explanation": "Retrieval finds context for the generation step."},
        {"question_id": "rag-grounding", "question": "What makes a response more traceable?", "options": ["Citations to supplied sources", "A higher temperature", "A longer answer", "Removing document IDs"], "concept": "grounding", "difficulty": "intermediate", "correct_option": 0, "explanation": "Citations let users inspect the evidence behind an answer."},
        {"question_id": "rag-chunking", "question": "Why does chunking matter?", "options": ["It controls the context units available for retrieval", "It guarantees no hallucinations", "It changes learner scores", "It grants tool access"], "concept": "chunking", "difficulty": "intermediate", "correct_option": 0, "explanation": "Chunk size affects retrieval relevance and context fit."},
    ],
    "evaluation-safety": [
        {"question_id": "eval-criteria", "question": "What makes an evaluation useful?", "options": ["Explicit criteria and representative examples", "Only fluent outputs", "One successful demo", "No expected behavior"], "concept": "quality_metrics", "difficulty": "intermediate", "correct_option": 0, "explanation": "Criteria and examples make quality testable."},
        {"question_id": "eval-hallucination", "question": "What is a hallucination?", "options": ["A confident but unsupported model claim", "A valid citation", "A deterministic score", "A prerequisite edge"], "concept": "hallucination", "difficulty": "intermediate", "correct_option": 0, "explanation": "Hallucinations are unsupported or fabricated claims."},
        {"question_id": "eval-fallback", "question": "What should a system do after invalid model output?", "options": ["Use a controlled fallback", "Render the raw response", "Update mastery to one", "Ignore the user"], "concept": "safety", "difficulty": "intermediate", "correct_option": 0, "explanation": "Controlled fallback preserves a usable and safe experience."},
    ],
    "ai-agents": [
        {"question_id": "agents-loop", "question": "What is part of an agent loop?", "options": ["Acting with a tool and observing the result", "Skipping validation", "Changing database state freely", "Only returning a greeting"], "concept": "agents", "difficulty": "advanced", "correct_option": 0, "explanation": "Agents coordinate actions and observations across steps."},
        {"question_id": "agents-tools", "question": "What should tool arguments receive?", "options": ["Application validation", "Unrestricted execution", "No permission checks", "Only model approval"], "concept": "tool_use", "difficulty": "advanced", "correct_option": 0, "explanation": "The application validates tool inputs and permissions."},
        {"question_id": "agents-planning", "question": "When is a deterministic workflow preferable?", "options": ["When the steps and rules are known", "When no validation is possible", "When state must be hidden", "When every task is ambiguous"], "concept": "planning", "difficulty": "advanced", "correct_option": 0, "explanation": "Known workflows are easier to test deterministically."},
    ],
    "production-llm-systems": [
        {"question_id": "production-observe", "question": "What should production monitoring include?", "options": ["Latency, failures, cost, and outcomes", "Only the longest answer", "The raw API key", "No user results"], "concept": "observability", "difficulty": "advanced", "correct_option": 0, "explanation": "Operational signals reveal system health and quality."},
        {"question_id": "production-latency", "question": "Why use bounded retries?", "options": ["To recover without creating indefinite delay", "To guarantee the model responds", "To bypass validation", "To hide failures"], "concept": "latency", "difficulty": "advanced", "correct_option": 0, "explanation": "Bounded retries balance recovery and responsiveness."},
        {"question_id": "production-reliability", "question": "What improves reliability during provider downtime?", "options": ["A curated fallback path", "Logging secrets", "Removing validation", "Retrying forever"], "concept": "reliability", "difficulty": "advanced", "correct_option": 0, "explanation": "Fallback behavior keeps the product usable during outages."},
    ],
}


def _question_fingerprint(question: str) -> str:
    return " ".join(question.lower().split())


def _fallback_questions(
    topic: Topic, previous_questions: list[dict[str, Any]] | None = None
) -> AssessmentQuestionSet:
    previous_questions = previous_questions or []
    previous_ids = {item.get("question_id") for item in previous_questions}
    seen_questions = {
        _question_fingerprint(item.get("question", ""))
        for item in previous_questions
    }
    questions = [
        question
        for question in QUESTION_BANK.get(topic.id, [])
        if question["question_id"] not in previous_ids
        and _question_fingerprint(question["question"]) not in seen_questions
    ][:3]
    if len(questions) < 3:
        concepts = topic.concept_tags or [topic.title.lower().replace(" ", "_")]
        templates = [
            "What is the main idea in {title}?",
            "Which statement best describes {title}?",
            "Which principle should guide work with {title}?",
            "How does {concept} support {title}?",
            "Which example best demonstrates {concept} in {title}?",
            "What should you verify when applying {concept} to {title}?",
            "Which outcome shows {concept} is being used appropriately in {title}?",
            "What is a useful first step when working with {concept} in {title}?",
            "Which limitation should you remember about {concept} in {title}?",
            "How can you check your understanding of {concept} in {title}?",
            "What role does {concept} play in {title}?",
            "Which practice helps apply {concept} to {title}?",
        ]
        retry_number = len(previous_questions) // 3 + 1
        template_offset = (retry_number - 1) * 3
        candidate_number = 0
        while len(questions) < 3:
            concept = concepts[(retry_number + candidate_number) % len(concepts)]
            concept_text = concept.replace("_", " ")
            template_index = (template_offset + candidate_number) % len(templates)
            question_text = templates[template_index].format(
                title=topic.title,
                concept=concept_text,
            )
            fingerprint = _question_fingerprint(question_text)
            if fingerprint in seen_questions:
                candidate_number += 1
                if candidate_number > len(templates) * 2:
                    question_text = f"{question_text} Try {retry_number + candidate_number}."
                    fingerprint = _question_fingerprint(question_text)
            if fingerprint in seen_questions:
                candidate_number += 1
                continue
            seen_questions.add(fingerprint)
            questions.append(
                {
                    "question_id": f"{topic.id}-retry-{retry_number}-{candidate_number + 1}",
                    "question": question_text,
                    "options": [topic.description, "It requires no data", "It replaces validation", "It is unrelated to AI"],
                    "concept": concepts[(retry_number + candidate_number) % len(concepts)],
                    "difficulty": topic.difficulty,
                    "correct_option": 0,
                    "explanation": topic.description,
                }
            )
            candidate_number += 1
    return AssessmentQuestionSet.model_validate({"questions": questions})


def _openrouter_questions(
    topic: Topic,
    learner: Any,
    weak_concepts: list[str],
    previous_questions: list[dict[str, Any]],
) -> AssessmentQuestionSet:
    context = {
        "learner": {
            "experience_level": learner.experience_level,
            "goal": learner.goal_text,
            "target_outcome": learner.target_outcome,
            "weak_concepts": weak_concepts,
        },
        "topic": {
            "id": topic.id,
            "title": topic.title,
            "description": topic.description,
            "concepts": topic.concept_tags,
            "difficulty": topic.difficulty,
        },
        "requirements": {"question_count": 3, "question_type": "MCQ", "difficulty": topic.difficulty},
        "previous_questions_to_avoid": [
            item.get("question", "") for item in previous_questions
        ],
        "schema": AssessmentQuestionSet.model_json_schema(),
    }
    parsed = request_structured_json(
        system_prompt=(
            "Create rigorous MCQs only for the supplied Generative AI topic. Use only the supplied concept tags, "
            "adapt difficulty to the learner, avoid repeating any previous question or scenario, and keep correct_option zero-based."
        ),
        user_payload=context,
        response_model=AssessmentQuestionSet,
        temperature=0.2,
        max_tokens=1800,
    )
    allowed_concepts = set(topic.concept_tags)
    if any(question.concept not in allowed_concepts for question in parsed.questions):
        raise ValueError("Assessment contains a concept outside the topic catalog")
    previous_fingerprints = {
        _question_fingerprint(item.get("question", ""))
        for item in previous_questions
    }
    if any(
        _question_fingerprint(question.question) in previous_fingerprints
        for question in parsed.questions
    ):
        raise ValueError("Assessment repeats a previous question")
    return parsed


def generate_assessment_questions(
    topic: Topic,
    learner: Any,
    weak_concepts: list[str] | None = None,
    previous_questions: list[dict[str, Any]] | None = None,
) -> tuple[AssessmentQuestionSet, str]:
    previous_questions = previous_questions or []
    if settings.openrouter_api_key:
        try:
            return (
                _openrouter_questions(topic, learner, weak_concepts or [], previous_questions),
                "openrouter",
            )
        except (Exception, ValidationError):
            pass
    return _fallback_questions(topic, previous_questions), "curated_fallback"