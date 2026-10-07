import json
from typing import Any

from openai import OpenAI
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Assessment, Learner, SkillScore, Topic, TopicProgress, Weakness
from ..schemas import LearningContent


CURATED_CONTENT: dict[str, dict[str, Any]] = {
    "ai-foundations": {
        "overview": "Generative AI systems learn patterns from examples and use those patterns to create new text, code, or other media.",
        "learning_objectives": [
            "Distinguish generative tasks from classification tasks",
            "Describe the role of a language model in an application",
            "Recognize where application logic must constrain a model",
        ],
        "explanation": "A generative model estimates likely continuations or constructions from learned patterns. In a language application, the model is one component: prompts provide intent, application code supplies rules and context, and evaluation checks whether the response is useful. The model can produce a fluent answer without guaranteeing that the answer is true, so reliable systems combine generation with validation and trusted context.",
        "key_concepts": ["generative models", "language models", "application constraints"],
        "examples": [
            "A summarizer generates a shorter version of an article rather than assigning the article a fixed label.",
            "A coding assistant proposes a function from a natural-language request.",
        ],
        "practical_example": "A support assistant can combine a user question, approved help-center context, and a response schema before asking a language model to draft an answer.",
        "common_mistakes": [
            "Treating fluent text as proof of correctness",
            "Letting the model decide authorization or database state",
        ],
        "quick_recap": [
            "Generative models create outputs from learned patterns.",
            "A production AI feature still needs deterministic application logic.",
            "Evaluation and grounding improve reliability.",
        ],
        "analogy": "Think of the model as a fast drafting partner: it can propose language, while your application remains the editor and rule keeper.",
        "important_notes": ["Model output should be treated as data to validate, not as an instruction to execute."],
    },
    "prompt-engineering": {
        "overview": "Prompt engineering turns an ambiguous request into a clear, testable instruction with context, constraints, and an output contract.",
        "learning_objectives": [
            "Write prompts with role, task, context, and constraints",
            "Use examples and schemas to reduce ambiguity",
            "Separate model generation from deterministic validation",
        ],
        "explanation": "A useful prompt specifies what the model should do, what information it may use, and what shape the response must have. Short, explicit instructions are often more reliable than a long collection of vague preferences. For application code, pair the prompt with schema validation and keep decisions such as permissions, scoring, and database updates outside the model.",
        "key_concepts": ["context", "constraints", "few-shot examples", "output contracts"],
        "examples": [
            "Instead of asking for a useful answer, request a JSON object with title, evidence, and confidence fields.",
            "Give one good and one bad classification example when the boundary is subtle.",
        ],
        "practical_example": "For a study assistant, provide the learner level, current topic, weak concepts, and a strict response schema, then validate the response before rendering it.",
        "common_mistakes": [
            "Combining unrelated tasks in one prompt",
            "Assuming an output format without validating it",
            "Asking the model to make state-changing decisions",
        ],
        "quick_recap": [
            "Specific context beats vague instructions.",
            "Schemas make output contracts testable.",
            "Keep deterministic decisions in application code.",
        ],
        "analogy": "A prompt is a brief for a collaborator: the clearer the deliverable and constraints, the less time is spent interpreting the request.",
        "code_example": "response = client.responses.parse(model=model, input=prompt, text_format=OutputSchema)",
    },
    "tokenization-embeddings": {
        "overview": "Tokenization converts text into model-readable units, while embeddings represent meaning as vectors for comparison and retrieval.",
        "learning_objectives": [
            "Explain why models process tokens rather than raw text",
            "Describe embeddings as semantic vector representations",
            "Connect embeddings to retrieval in a RAG pipeline",
        ],
        "explanation": "A tokenizer maps text into tokens that a model can process within its context window. An embedding model maps content into a vector space where semantically related items tend to be near each other. A retrieval system can embed a question, compare it with embedded documents, and pass the most relevant text to a generative model. Similarity is useful evidence, not a guarantee that the result is complete or correct.",
        "key_concepts": ["tokens", "context window", "embeddings", "semantic similarity"],
        "examples": [
            "The same word can use different token counts depending on spelling and surrounding text.",
            "A question about refund policy can retrieve a policy paragraph because their embeddings are semantically close.",
        ],
        "practical_example": "Chunk a handbook, embed each chunk, embed the learner question, retrieve the nearest chunks, and provide those chunks as context for an answer.",
        "common_mistakes": [
            "Confusing token similarity with factual correctness",
            "Ignoring chunk boundaries and context limits",
        ],
        "quick_recap": [
            "Tokens are the model's input units.",
            "Embeddings encode useful semantic relationships.",
            "Retrieval uses vectors to find candidate context.",
        ],
        "analogy": "Tokens are like the words and fragments in a library's index; embeddings are coordinates that help you find books about similar ideas.",
    },
    "attention-transformers": {
        "overview": "Attention lets a transformer weigh relationships between tokens, helping each representation use relevant context from the sequence.",
        "learning_objectives": [
            "Describe the purpose of self-attention",
            "Explain why positional information matters",
            "Connect transformer blocks to modern language models",
        ],
        "explanation": "Self-attention compares a token's query with keys from other tokens and uses the resulting weights to combine value information. This lets the representation of a word depend on relevant context elsewhere in the sequence. Because attention alone does not encode order, transformer systems add positional information. Repeated attention and feed-forward blocks allow the model to build increasingly useful representations.",
        "key_concepts": ["self-attention", "queries, keys, values", "positional encoding", "transformer blocks"],
        "examples": [
            "In a sentence with an ambiguous pronoun, attention can connect the pronoun to the relevant noun.",
            "Positional information helps distinguish a sequence from the same tokens in a different order.",
        ],
        "practical_example": "When debugging a transformer explanation, inspect whether it explains both token relationships and the separate mechanism that carries order information.",
        "common_mistakes": [
            "Saying attention simply selects one previous word",
            "Forgetting that attention needs positional information for order",
        ],
        "quick_recap": [
            "Attention mixes information using learned relevance weights.",
            "Transformers process context through repeated blocks.",
            "Position and token relationships solve different problems.",
        ],
        "analogy": "Attention is like highlighting the parts of a paragraph that matter for interpreting one sentence, while positional information preserves the paragraph's order.",
    },
    "llm-application-patterns": {
        "overview": "LLM application patterns combine prompts, structured outputs, tools, validation, and evaluation into a dependable workflow.",
        "learning_objectives": [
            "Separate generation from application state changes",
            "Use structured outputs and validation",
            "Recognize where evaluation belongs in an LLM workflow",
        ],
        "explanation": "A useful LLM feature is a pipeline rather than a single prompt. The application gathers context, asks the model for a bounded response, validates that response, and then applies deterministic business rules. Tool calls add another boundary: the model may suggest a tool and arguments, but the application validates permissions and inputs before execution. Evaluation examples reveal regressions that a single successful response can hide.",
        "key_concepts": ["structured outputs", "tool calls", "validation", "evaluation loops"],
        "examples": [
            "Parse a model response into a Pydantic schema before showing it to a learner.",
            "Require a user confirmation before an agent performs a consequential action.",
        ],
        "practical_example": "A learning platform can request content JSON, validate topic_id against its catalog, and use deterministic code to update progress.",
        "common_mistakes": [
            "Treating a model response as executable instructions",
            "Using a model to calculate scores that code can calculate exactly",
        ],
        "quick_recap": [
            "LLM features need validation boundaries.",
            "Structured output makes responses easier to test.",
            "Application code owns state and permissions.",
        ],
        "analogy": "The model is a specialist inside a workflow, not the workflow manager: each handoff needs a checked contract.",
    },
    "retrieval-augmented-generation": {
        "overview": "RAG retrieves relevant source material and gives it to a language model so the response can be grounded in known context.",
        "learning_objectives": [
            "Describe the retrieval and generation stages",
            "Understand chunking and embedding choices",
            "Explain why citations and evaluation matter",
        ],
        "explanation": "A RAG system typically chunks source documents, creates embeddings, retrieves candidates for a question, and places those candidates into a generation prompt. Good retrieval is necessary but not sufficient: the model can still misread context or answer beyond the evidence. Source identifiers, citations, retrieval evaluation, and answer evaluation help a team see whether the system is grounded.",
        "key_concepts": ["chunking", "retrieval", "grounding", "citations", "RAG evaluation"],
        "examples": [
            "Retrieve the two policy sections most related to a customer's question before drafting a response.",
            "Show the source document title beside an answer so the learner can inspect the evidence.",
        ],
        "practical_example": "For an internal handbook assistant, store each chunk with a source ID, retrieve top candidates, and require the answer to cite only those IDs.",
        "common_mistakes": [
            "Assuming retrieval automatically prevents hallucination",
            "Using chunks that are too large or too small for the task",
            "Omitting source traceability",
        ],
        "quick_recap": [
            "Retrieve first, then generate with context.",
            "Grounding needs source traceability.",
            "Evaluate both retrieval and final answers.",
        ],
        "analogy": "RAG is an open-book exam: retrieval finds the relevant pages, but the writer still has to answer accurately from those pages.",
    },
    "evaluation-safety": {
        "overview": "LLM evaluation and safety make quality visible through representative tests, boundaries, monitoring, and careful failure handling.",
        "learning_objectives": [
            "Define useful quality criteria for an LLM feature",
            "Identify common hallucination and safety risks",
            "Use deterministic validation and fallback paths",
        ],
        "explanation": "Evaluation begins with the behavior that matters: correctness, groundedness, helpfulness, latency, cost, or safety. Build a representative set of examples and compare model outputs against explicit criteria. Safety is also a system property: limit tools, validate inputs and outputs, protect secrets, and provide a controlled fallback when the model or network is unavailable.",
        "key_concepts": ["evaluation sets", "hallucination", "guardrails", "fallbacks"],
        "examples": [
            "Test whether an answer cites a supplied source instead of merely sounding confident.",
            "Send malformed model output to a curated fallback rather than rendering broken content.",
        ],
        "practical_example": "Maintain a small regression set of learner questions and check structure, topic scope, and evidence before accepting generated content.",
        "common_mistakes": [
            "Measuring only fluency",
            "Logging secrets while debugging failures",
            "Having no recovery behavior for provider outages",
        ],
        "quick_recap": [
            "Quality needs explicit criteria and test examples.",
            "Safety belongs in the surrounding application.",
            "Fallbacks are part of a reliable AI experience.",
        ],
        "analogy": "Evaluation is the test suite and safety rail around a fast prototype: it turns impressive examples into dependable behavior.",
    },
    "ai-agents": {
        "overview": "AI agents coordinate a model with tools and observations to complete multi-step tasks under application-controlled boundaries.",
        "learning_objectives": [
            "Explain the agent loop of plan, act, and observe",
            "Identify tool validation and permission boundaries",
            "Recognize when a simpler workflow is safer",
        ],
        "explanation": "An agent loop can interpret a goal, choose a tool, receive an observation, and decide what to do next. The application should define the available tools, validate arguments, enforce permissions, limit loops, and record outcomes. Not every problem needs an agent: a deterministic workflow is usually easier to test when the steps are known in advance.",
        "key_concepts": ["tool use", "planning", "observations", "orchestration"],
        "examples": [
            "An agent can search a knowledge base, inspect the result, and draft a cited response.",
            "A fixed checkout flow should remain deterministic instead of delegating every step to an agent.",
        ],
        "practical_example": "Expose a read-only search tool first, validate its query length, and require application code to approve any later write action.",
        "common_mistakes": [
            "Giving an agent unrestricted tool access",
            "Using agents where a simple function is sufficient",
            "Failing to cap retries or tool loops",
        ],
        "quick_recap": [
            "Agents combine models with tools and observations.",
            "Tools need permissions and input validation.",
            "Deterministic workflows are often preferable.",
        ],
        "analogy": "An agent is a junior operator with a toolbox: it can choose actions, but a supervisor still controls access and checks the work.",
    },
    "production-llm-systems": {
        "overview": "Production LLM systems balance quality, reliability, latency, cost, observability, and safe recovery.",
        "learning_objectives": [
            "Identify operational concerns in LLM applications",
            "Design useful monitoring signals",
            "Plan graceful behavior when a provider is unavailable",
        ],
        "explanation": "A production LLM feature needs more than a successful local prompt. Track request latency, token or provider cost, failure rates, validation failures, and user outcomes. Use timeouts, retries with limits, fallback content, and redacted logs. Changes to prompts or models should be evaluated against a representative test set before release.",
        "key_concepts": ["observability", "latency", "cost", "reliability"],
        "examples": [
            "Count structured-output validation failures separately from network errors.",
            "Keep a curated response path available during provider downtime.",
        ],
        "practical_example": "A learning service can return curated content within a timeout while recording only a safe failure category, never the API key or raw sensitive prompt.",
        "common_mistakes": [
            "Retrying indefinitely",
            "Logging full requests that contain secrets",
            "Ignoring cost and latency until launch",
        ],
        "quick_recap": [
            "Reliable AI is an operational system.",
            "Measure failures, latency, cost, and outcomes.",
            "Recovery paths should be designed before deployment.",
        ],
        "analogy": "A production AI feature is a small service with a dashboard, a budget, and an emergency exit, not just a clever prompt.",
    },
}


def _fallback_content(topic: Topic, learner: Learner, weak_concepts: list[str]) -> LearningContent:
    data = CURATED_CONTENT.get("ai-foundations", {}) | CURATED_CONTENT.get(topic.id, {})
    explanation = data["explanation"]
    if weak_concepts:
        explanation += " This review gives extra attention to " + ", ".join(
            concept.replace("_", " ") for concept in weak_concepts
        ) + ", because those concepts are currently developing for you."
    if learner.experience_level == "advanced":
        explanation += " At an advanced level, focus on the trade-offs between quality, control, and system complexity."
    return LearningContent.model_validate({"topic_id": topic.id, "topic_title": topic.title, **data, "explanation": explanation})


def _openrouter_content(
    topic: Topic,
    learner: Learner,
    weak_concepts: list[str],
    completed_topics: list[str],
    recent_assessments: list[dict[str, Any]],
) -> LearningContent:
    context = {
        "learner": {
            "experience_level": learner.experience_level,
            "goal": learner.goal_text,
            "weak_concepts": weak_concepts,
            "completed_topics": completed_topics,
            "recent_assessments": recent_assessments,
        },
        "current_topic": {
            "id": topic.id,
            "title": topic.title,
            "description": topic.description,
            "concepts": topic.concept_tags,
        },
    }
    client = OpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url)
    response = client.chat.completions.create(
        model=settings.openrouter_model,
        temperature=0.3,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a careful Generative AI instructor. Teach only the supplied current topic. "
                    "Adapt depth to experience and address weak concepts. Return only JSON matching the "
                    "requested learning-content schema. Keep topic_id exactly equal to the supplied ID. "
                    "Do not invent topic IDs or unrelated curriculum topics."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({"schema": LearningContent.model_json_schema(), "context": context}),
            },
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("OpenRouter returned empty learning content")
    parsed = LearningContent.model_validate_json(content)
    if parsed.topic_id != topic.id or parsed.topic_title != topic.title:
        raise ValueError("AI content topic does not match the curated topic")
    return parsed


def generate_learning_content(
    topic: Topic,
    learner: Learner,
    database: Session,
) -> tuple[LearningContent, str]:
    skills = database.scalars(select(SkillScore).where(SkillScore.learner_id == learner.id)).all()
    weak_concepts = [
        skill.concept for skill in skills if skill.score < 0.5 and skill.concept in topic.concept_tags
    ]
    progress = database.scalars(
        select(TopicProgress).where(TopicProgress.learner_id == learner.id)
    ).all()
    completed_topics = [item.topic_id for item in progress if item.status == "completed"]
    assessments = database.scalars(
        select(Assessment).where(Assessment.learner_id == learner.id).order_by(Assessment.created_at.desc()).limit(5)
    ).all()
    recent_assessments = [
        {"topic_id": item.topic_id, "score": item.score}
        for item in assessments
        if item.topic_id and item.score is not None
    ]
    if settings.openrouter_api_key:
        try:
            return (
                _openrouter_content(topic, learner, weak_concepts, completed_topics, recent_assessments),
                "openrouter",
            )
        except (Exception, ValidationError):
            pass
    return _fallback_content(topic, learner, weak_concepts), "curated_fallback"