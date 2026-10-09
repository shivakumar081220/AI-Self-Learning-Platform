import json
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (
    AIArtifactCache,
    Assessment,
    GeneratedCourse,
    Learner,
    SkillScore,
    Topic,
    TopicPrerequisite,
    TopicProgress,
    Weakness,
)
from ..schemas import (
    CodingExample,
    LearningContent,
    LessonCodeExample,
    LessonMistake,
    LessonSection,
    LessonSelfCheck,
    LessonSubsection,
)
from ..topic_titles import display_topic_title
from ..track_catalog import TRACK_BY_ID
from .ai_cache import get_or_generate_artifact
from .ai_provider import AIProviderError, request_structured_json


logger = logging.getLogger(__name__)


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


def _is_technical_topic(topic: Topic) -> bool:
    if topic.track_id in {"python_for_ai", "machine_learning", "deep_learning", "nlp"}:
        return True
    return bool(
        set(topic.concept_tags).intersection(
            {
                "prompt_design", "structured_outputs", "tool_calling",
                "document_chunking", "embeddings", "vector_search",
                "retrieval_ranking", "hybrid_search", "grounded_generation",
                "tool_schemas", "argument_validation", "task_decomposition",
                "state_management", "orchestration",
            }
        )
    )


def _fallback_coding_example(topic: Topic) -> CodingExample:
    topic_title = display_topic_title(topic.title)
    concepts = set(topic.concept_tags)
    track_id = topic.track_id or "generative_ai"
    if concepts.intersection({"tool_schemas", "argument_validation", "task_decomposition", "planning", "orchestration"}):
        track_id = "ai_agents"
    elif concepts.intersection({"retrieval", "embeddings", "vector_search", "grounded_generation", "citations"}):
        track_id = "rag"
    if track_id == "python_for_ai" and "variables_and_types" in concepts:
        code = (
            'model_name = "Linear Regression"\n'
            "learning_rate = 0.01\n"
            "epochs = 100\n"
            "is_trained = False\n\n"
            "print(model_name)\n"
            "print(learning_rate)\n"
            "print(epochs)\n"
            "print(is_trained)"
        )
        output = "Linear Regression\n0.01\n100\nFalse"
        explanation = "Strings name the model, floats store a rate, integers store a count, and a boolean records training state."
        mistake = "Using a string for a number that must be compared or used in arithmetic."
    elif track_id == "python_for_ai":
        code = (
            'records = [{"score": 0.8}, {"score": None}, {"score": 0.6}]\n'
            'valid_scores = [row["score"] for row in records if row["score"] is not None]\n'
            "mean_score = sum(valid_scores) / len(valid_scores)\n"
            "print(round(mean_score, 2))"
        )
        output = "0.7"
        explanation = "A list comprehension filters a missing value before calculating a summary used in data analysis."
        mistake = "Calculating a statistic before checking whether missing values are present."
    elif track_id == "machine_learning":
        code = (
            "actual = [0, 1, 1]\n"
            "predicted = [0, 1, 0]\n"
            "correct = sum(a == p for a, p in zip(actual, predicted))\n"
            "accuracy = correct / len(actual)\n"
            'print(f"accuracy: {accuracy:.2f}")'
        )
        output = "accuracy: 0.67"
        explanation = "This held-out comparison counts correct predictions; accuracy alone may hide class imbalance."
        mistake = "Reporting training accuracy as evidence that a model generalizes to unseen data."
    elif track_id == "deep_learning":
        code = (
            "inputs = [0.5, 1.0]\n"
            "weights = [0.2, 0.4]\n"
            "bias = 0.1\n"
            "activation = sum(x * w for x, w in zip(inputs, weights)) + bias\n"
            'print(f"pre-activation: {activation:.2f}")'
        )
        output = "pre-activation: 0.60"
        explanation = "A neuron combines inputs, weights, and bias before an activation function transforms the result."
        mistake = "Combining input and weight vectors with mismatched dimensions."
    elif track_id == "nlp":
        code = (
            'text = "Models learn from labeled examples"\n'
            "tokens = text.lower().split()\n"
            "print(tokens[:3])"
        )
        output = "['models', 'learn', 'from']"
        explanation = "This simple tokenizer creates word-level units; production tokenizers also handle punctuation and subwords."
        mistake = "Removing negation or punctuation without checking whether it changes the label meaning."
    elif track_id == "generative_ai":
        code = (
            'task = "Summarize the support request"\n'
            'constraints = ["Use two bullets", "Do not invent policy"]\n'
            'prompt = task + ". Constraints: " + "; ".join(constraints)\n'
            "print(prompt)"
        )
        output = "Summarize the support request. Constraints: Use two bullets; Do not invent policy"
        explanation = "The prompt separates the task from constraints that can later be checked."
        mistake = "Assuming a well-formed prompt guarantees the model response is factual."
    elif track_id == "llms":
        code = (
            'messages = [{"role": "user", "content": "Explain attention"}]\n'
            'approximate_words = len(messages[0]["content"].split())\n'
            "print(approximate_words)"
        )
        output = "2"
        explanation = "The example inspects a message payload; word counts are not model token counts."
        mistake = "Treating word count as an exact token count or ignoring the model context limit."
    elif track_id == "rag":
        code = (
            'documents = ["Refunds take five days", "Shipping takes two days"]\n'
            'query = "refund timing"\n'
            'matches = [doc for doc in documents if "refund" in doc.lower()]\n'
            "print(matches[0])"
        )
        output = "Refunds take five days"
        explanation = "This toy lexical retrieval selects candidate context; production RAG also needs ranking and citations."
        mistake = "Treating a keyword match as proof the retrieved statement fully answers the question."
    else:
        code = (
            'tools = {"search": lambda query: f"Results for: {query}"}\n'
            'requested_tool = "search"\n'
            "if requested_tool in tools:\n"
            '    print(tools[requested_tool]("vector databases"))'
        )
        output = "Results for: vector databases"
        explanation = "The application checks a requested tool against an allowlist before executing it."
        mistake = "Executing a model-proposed tool name or arguments without application validation."
    return CodingExample(
        title=f"Apply {topic_title}",
        code=code,
        explanation=explanation,
        expected_output=output,
        why_it_matters=f"This runnable example connects {topic_title} to a practical {track_id.replace('_', ' ')} task.",
        common_mistake=mistake,
    )


def _ensure_structured_lesson(content: LearningContent, topic: Topic, weak_concepts: list[str]) -> LearningContent:
    topic_title = display_topic_title(topic.title)
    concepts = content.key_concepts or [topic_title]
    examples = content.examples or [content.practical_example]
    tutor_prompts = [
        f"Explain {topic_title} using a simpler example",
        f"How is {topic_title} used in practice?",
        f"What can go wrong when applying {topic_title}?",
    ]
    sections = content.sections
    if not sections:
        sections = [
            LessonSection(
                title=f"How {topic_title} works",
                summary=content.explanation[:1200],
                subsections=[
                    LessonSubsection(
                        title=concepts[0],
                        explanation=topic.description,
                        key_points=content.important_notes[:4],
                        examples=examples[:2],
                        practical_application=content.practical_example,
                        tutor_prompts=tutor_prompts,
                    )
                ],
            ),
            LessonSection(
                title=f"Apply {topic_title}",
                summary=content.practical_example[:1200],
                subsections=[
                    LessonSubsection(
                        title="Worked example",
                        explanation=content.real_world_example or examples[0],
                        key_points=content.key_concepts[:4],
                        examples=examples[1:3],
                        practical_application=content.practice_suggestion or content.practical_example,
                        tutor_prompts=tutor_prompts,
                    )
                ],
            ),
        ]
    else:
        sections = [
            section.model_copy(
                update={
                    "subsections": [
                        subsection.model_copy(
                            update={
                                "key_points": subsection.key_points,
                                "examples": subsection.examples,
                                "practical_application": subsection.practical_application,
                                "tutor_prompts": subsection.tutor_prompts or tutor_prompts,
                            }
                        )
                        for subsection in section.subsections
                    ]
                }
            )
            for section in sections
        ]

    code_examples = content.code_examples
    if not code_examples:
        if content.coding_example:
            code_examples = [
                LessonCodeExample(
                    title=content.coding_example.title,
                    language="python",
                    code=content.coding_example.code,
                    explanation=content.coding_example.explanation,
                    expected_output=content.coding_example.expected_output,
                )
            ]
        elif content.code_example:
            code_examples = [
                LessonCodeExample(
                    title=f"{topic_title} example",
                    language="python",
                    code=content.code_example,
                    explanation=content.practical_example,
                )
            ]

    mistake_details = content.common_mistake_details
    if not mistake_details:
        mistake_details = [
            LessonMistake(
                mistake=mistake,
                explanation=(
                    f"For {topic_title}, this can undermine the intended result: "
                    f"{topic.description}"
                ),
                correction=(
                    content.practice_suggestion
                    or f"Apply the lesson objective to a small {topic.track_id.replace('_', ' ')} example and inspect the result."
                ),
            )
            for mistake in content.common_mistakes[:6]
        ]

    payload = content.model_dump()
    payload.update(
        {
            "title": content.title or topic_title,
            "introduction": content.introduction or content.overview,
            "why_it_matters": content.why_it_matters or content.real_world_example or content.practical_example,
            "sections": sections,
            "code_examples": code_examples,
            "common_mistake_details": mistake_details,
            "key_takeaways": content.key_takeaways or content.quick_recap[:6],
            "self_check": content.self_check or [
                LessonSelfCheck(
                    question=f"How would you explain {concept} in the context of {topic_title}?",
                    hint=f"Connect it to the lesson's practical example: {examples[0][:200]}",
                )
                for concept in concepts[:3]
            ],
            "important_points": content.important_points or content.important_notes[:6] or concepts[:6],
            "recommended_focus": content.recommended_focus or [
                concept for concept in weak_concepts if concept in topic.concept_tags
            ],
            "assessment_recommendation": (
                content.assessment_recommendation
                or "Try a short assessment with both concept questions and a practical application."
            ),
            "prerequisites": content.prerequisites,
        }
    )
    return LearningContent.model_validate(payload)


def _fallback_content(
    topic: Topic,
    learner: Learner,
    weak_concepts: list[str],
    prerequisites: list[str],
) -> LearningContent:
    topic_title = display_topic_title(topic.title)
    data = CURATED_CONTENT.get(topic.id)
    key_concepts = (
        list(data.get("key_concepts", []))
        if data
        else [concept.replace("_", " ") for concept in topic.concept_tags[:6]]
        if topic.concept_tags
        else [topic_title]
    )
    if len(key_concepts) == 1:
        key_concepts.append(topic_title)
    if not data:
        track_name = TRACK_BY_ID.get(learner.track, TRACK_BY_ID["generative_ai"]).name
        practice_by_track = {
            "python_for_ai": (
                f"Create a small data record for {learner.goal_text}, apply {topic_title}, "
                "and print the transformed value so you can verify its type and result."
            ),
            "machine_learning": (
                f"Use {topic_title} to build or inspect a classifier for {learner.goal_text}; "
                "compare predictions with held-out labels and explain one error."
            ),
            "deep_learning": (
                f"Trace how {topic_title} transforms a small input tensor in a neural network, "
                "record its shape, and explain how the result affects training."
            ),
            "nlp": (
                f"Apply {topic_title} to two short text examples for {learner.goal_text}; "
                "inspect the transformed text and explain what information is preserved."
            ),
            "generative_ai": (
                f"Write a bounded prompt for {learner.goal_text}, validate its output format, "
                "and identify one claim that needs independent evidence."
            ),
            "llms": (
                f"Trace how {topic_title} affects an LLM request for {learner.goal_text}; "
                "inspect the input, output constraints, and one reliability trade-off."
            ),
            "rag": (
                f"Retrieve source passages for {learner.goal_text}, check their relevance, and "
                "link each generated claim to evidence from those passages."
            ),
            "ai_agents": (
                f"Specify an allowed tool action for {learner.goal_text}, validate its arguments, "
                "and inspect the observation before allowing the next step."
            ),
        }
        mistake_by_track = {
            "python_for_ai": "Using values of the wrong type or silently dropping missing records.",
            "machine_learning": "Evaluating on training examples and assuming the score generalizes.",
            "deep_learning": "Ignoring tensor dimensions or applying an update with the wrong shape.",
            "nlp": "Normalizing away negation or meaningful token boundaries.",
            "generative_ai": "Treating fluent generated text as proof that its claims are supported.",
            "llms": "Ignoring token limits or assuming generation settings guarantee correctness.",
            "rag": "Citing a retrieved passage that does not support the answer claim.",
            "ai_agents": "Executing unvalidated tool names or arguments suggested by a model.",
        }
        practice = practice_by_track.get(
            learner.track,
            f"Apply {topic_title} to {learner.goal_text} and check the result against the topic objectives.",
        )
        objectives = topic.learning_objectives_json or [
            f"Explain {topic_title} in the context of {track_name}",
            f"Apply {topic_title} to the learner's selected goal and verify the result",
        ]
        mistake = mistake_by_track.get(
            learner.track,
            f"Applying {topic_title} without checking the evidence or intended outcome.",
        )
        data = {
            "overview": topic.description,
            "learning_objectives": objectives[:6],
            "explanation": (
                f"{topic.description} In the {track_name} workflow for {learner.goal_text}, "
                f"{topic_title} helps connect the task inputs to a result that can be checked."
            ),
            "key_concepts": key_concepts,
            "examples": [
                f"{practice} Record the input, each step, and the observed output."
            ],
            "practical_example": practice,
            "common_mistakes": [mistake],
            "quick_recap": [
                topic.description,
                f"Verify {topic_title} against the objective: {objectives[0]}",
            ],
            "analogy": None,
            "important_notes": [
                f"Focus on {', '.join(key_concepts[:3])} and verify the result with evidence."
            ],
            "introduction": topic.description,
            "why_it_matters": (
                f"{topic_title} supports the learner's goal, {learner.goal_text}, "
                f"by making the {track_name} workflow more explicit and testable."
            ),
            "common_mistake_details": [
                {
                    "mistake": mistake,
                    "explanation": (
                        f"This mistake can produce an unreliable result when using {topic_title} "
                        f"for {learner.goal_text}."
                    ),
                    "correction": practice,
                }
            ],
            "key_takeaways": [
                topic.description,
                f"Use {topic_title} to advance {learner.goal_text} and verify the result.",
            ],
            "self_check": [
                {
                    "question": f"What input and outcome would you check when applying {topic_title}?",
                    "hint": f"Start with the objective: {objectives[0]}",
                }
            ],
            "assessment_recommendation": (
                f"Explain {topic_title}, then apply it to a small task related to {learner.goal_text}."
            ),
        }
    else:
        data = data.copy()
    explanation = data["explanation"]
    if weak_concepts:
        explanation += " This review gives extra attention to " + ", ".join(
            concept.replace("_", " ") for concept in weak_concepts
        ) + ", because they are identified as areas to focus on."
    if learner.experience_level == "advanced":
        explanation += " At an advanced level, focus on the trade-offs between quality, control, and system complexity."
    payload = {
        "topic_id": topic.id,
        "topic_title": topic_title,
        **data,
        "explanation": explanation,
        "real_world_example": data.get("real_world_example", data["practical_example"]),
        "prerequisites": prerequisites,
        "practice_suggestion": data.get(
            "practice_suggestion",
            data["practical_example"],
        ),
    }
    if _is_technical_topic(topic):
        payload["coding_example"] = _fallback_coding_example(topic).model_dump()
    coding_example = payload.get("coding_example")
    worked_explanation = (
        coding_example["explanation"]
        if coding_example
        else data.get("real_world_example", data["practical_example"])
    )
    worked_points = (
        [
            coding_example["why_it_matters"],
            f"Expected output: {coding_example['expected_output']}"
            if coding_example.get("expected_output")
            else "Compare the observed result with the stated objective.",
        ]
        if coding_example
        else data.get("important_notes", [])[:3]
    )
    worked_examples = (
        [f"Expected output: {coding_example['expected_output']}"]
        if coding_example and coding_example.get("expected_output")
        else data.get("examples", [])[:2]
    )
    payload["sections"] = [
        LessonSection(
            title=f"Understand {topic_title}",
            summary=data["explanation"][:1200],
            subsections=[
                LessonSubsection(
                    title=key_concepts[0],
                    explanation=data["explanation"],
                    key_points=data.get("important_notes", [])[:4] or key_concepts[:4],
                    examples=data.get("examples", [])[:2],
                    practical_application=data["practical_example"],
                    tutor_prompts=[
                        f"Explain {topic_title} with a simpler example",
                        f"How does {topic_title} apply to {learner.goal_text}?",
                    ],
                )
            ],
        ),
        LessonSection(
            title=f"Apply {topic_title}",
            summary=worked_explanation[:1200],
            subsections=[
                LessonSubsection(
                    title="Worked example",
                    explanation=worked_explanation,
                    key_points=worked_points[:4] or key_concepts[:4],
                    examples=worked_examples,
                    practical_application=data["practical_example"],
                    tutor_prompts=[
                        f"Walk me through this {topic_title} example",
                        f"What could go wrong when applying {topic_title}?",
                    ],
                )
            ],
        ),
    ]
    return _ensure_structured_lesson(LearningContent.model_validate(payload), topic, weak_concepts)


def _openrouter_content(
    topic: Topic,
    learner: Learner,
    weak_concepts: list[str],
    strong_concepts: list[str],
    completed_topics: list[str],
    recent_assessments: list[dict[str, Any]],
    prerequisites: list[str],
    course_context: dict[str, Any] | None,
) -> LearningContent:
    context = {
        "learner": {
            "experience_level": learner.experience_level,
            "goal": learner.goal_text,
            "target_outcome": learner.target_outcome,
            "track_id": course_context.get("track_id", learner.track) if course_context else learner.track,
            "weak_concepts": weak_concepts,
            "strong_concepts": strong_concepts,
            "completed_topics": completed_topics[-3:],
            "recent_assessments": recent_assessments[:5],
        },
        "course": course_context,
        "current_topic": {
            "id": topic.id,
            "title": display_topic_title(topic.title),
            "description": topic.description,
            "concepts": topic.concept_tags,
            "learning_objectives": topic.learning_objectives_json[:8],
        },
        "prerequisites": prerequisites,
    }
    parsed = request_structured_json(
        operation="learning_content",
        system_prompt=(
            "You are an expert instructional designer and technical teacher creating a complete, "
            "self-guided lesson for an adaptive AI learning platform. Help the learner understand, "
            "remember, apply, and practice; do not return a shallow summary or filler. Teach only the "
            "supplied topic in progressive steps: basic idea, deeper explanation, example, application. "
            "Respect completed and strong knowledge; do not re-teach mastered prerequisites. Connect "
            "the lesson to the learner's goal, current course, recent assessment results, and relevant "
            "weak concepts; identify relevant weak concepts in recommended_focus. Put each major idea "
            "in sections and subsections with a clear explanation, key points, a concrete example, "
            "practical application, and three short tutor_prompts. Explain mathematical intuition "
            "before formulas. For code or ML topics include a useful small code example; for architecture "
            "topics explain components or workflows and use scenarios instead of forced code. Include "
            "why_it_matters, prerequisites, important_points, common mistakes with explanations and "
            "corrections, key_takeaways, a short self_check with hints, a practice suggestion, and an "
            "assessment recommendation. Keep chunks concise, technically accurate, and relevant. "
            "Return JSON matching the requested LearningContent schema. Keep topic_id and topic_title "
            "exactly equal to the supplied values. Use valid JSON only; do not add Markdown fences, "
            "invent learner history, reveal secrets, or add unrelated topics."
        ),
        user_payload={"context": context},
        response_model=LearningContent,
        temperature=0.3,
        max_tokens=5000,
    )
    if parsed.topic_id != topic.id or parsed.topic_title != display_topic_title(topic.title):
        logger.warning(
            "OpenRouter structured response failed semantic validation; operation=learning_content "
            "model=%s validation_error=topic_identity_mismatch missing_fields=[] unexpected_fields=[]",
            settings.openrouter_model,
        )
        raise ValueError("AI content topic does not match the curated topic")
    missing_learning_sections = [
        name
        for name, value in (
            ("introduction", parsed.introduction),
            ("why_it_matters", parsed.why_it_matters),
            ("practice_suggestion", parsed.practice_suggestion),
            ("assessment_recommendation", parsed.assessment_recommendation),
        )
        if not value
    ]
    if (
        not parsed.sections
        or any(not section.subsections for section in parsed.sections)
        or not parsed.self_check
        or not parsed.common_mistake_details
        or len(parsed.key_takeaways) < 2
    ):
        missing_learning_sections.extend(
            [
                name
                for name, present in (
                    ("teaching_sections", bool(parsed.sections) and all(section.subsections for section in parsed.sections)),
                    ("self_check", bool(parsed.self_check)),
                    ("common_mistake_details", bool(parsed.common_mistake_details)),
                    ("key_takeaways", len(parsed.key_takeaways) >= 2),
                )
                if not present
            ]
        )
    if missing_learning_sections:
        logger.warning(
            "OpenRouter structured response failed semantic validation; operation=learning_content "
            "model=%s validation_error=incomplete_lesson missing_fields=%s unexpected_fields=[]",
            settings.openrouter_model,
            sorted(set(missing_learning_sections)),
        )
        raise ValueError("AI lesson is incomplete")
    if not parsed.real_world_example or not parsed.practice_suggestion:
        missing_fields = [
            field
            for field, value in (
                ("real_world_example", parsed.real_world_example),
                ("practice_suggestion", parsed.practice_suggestion),
            )
            if not value
        ]
        logger.warning(
            "OpenRouter structured response failed semantic validation; operation=learning_content "
            "model=%s validation_error=missing_learning_guidance missing_fields=%s unexpected_fields=[]",
            settings.openrouter_model,
            missing_fields,
        )
        raise ValueError("AI lesson is missing required learning guidance")
    if _is_technical_topic(topic) and not parsed.coding_example and not parsed.code_examples:
        logger.warning(
            "OpenRouter structured response failed semantic validation; operation=learning_content "
            "model=%s validation_error=missing_coding_example missing_fields=[coding_example] unexpected_fields=[]",
            settings.openrouter_model,
        )
        raise ValueError("AI lesson is missing its required coding example")
    lesson_text = json.dumps(parsed.model_dump(mode="json"), ensure_ascii=True).lower()
    concept_terms = [
        concept.replace("_", " ").casefold()
        for concept in topic.concept_tags
        if len(concept.replace("_", " ")) >= 4
    ]
    if concept_terms and not any(term in lesson_text for term in concept_terms):
        logger.warning(
            "OpenRouter structured response failed semantic validation; operation=learning_content "
            "model=%s validation_error=topic_relevance missing_fields=[] unexpected_fields=[]",
            settings.openrouter_model,
        )
        raise ValueError("AI lesson does not teach the selected topic concepts")
    filler_phrases = (
        "design a small exercise",
        "application practice",
        "larger system you are learning to design",
    )
    if any(phrase in lesson_text for phrase in filler_phrases):
        logger.warning(
            "OpenRouter structured response failed semantic validation; operation=learning_content "
            "model=%s validation_error=generic_filler missing_fields=[] unexpected_fields=[]",
            settings.openrouter_model,
        )
        raise ValueError("AI lesson contains generic filler")
    return parsed.model_copy(
        update={
            "prerequisites": prerequisites,
            "code_example": parsed.code_example or (parsed.coding_example.code if parsed.coding_example else None),
        }
    )


def _previous_course_lesson(
    topic: Topic, learner: Learner, database: Session
) -> tuple[LearningContent, str] | None:
    if topic.course_id is None:
        return None
    artifacts = database.scalars(
        select(AIArtifactCache)
        .where(
            AIArtifactCache.learner_id == learner.id,
            AIArtifactCache.operation == "learning_content",
            AIArtifactCache.status.in_(("completed", "fallback")),
        )
        .order_by(AIArtifactCache.updated_at.desc())
    ).all()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for artifact in artifacts:
        if artifact.status == "fallback" and artifact.expires_at and artifact.expires_at <= now:
            continue
        if not isinstance(artifact.result_json, dict) or artifact.result_json.get("topic_id") != topic.id:
            continue
        try:
            content = LearningContent.model_validate(artifact.result_json)
        except ValidationError:
            logger.warning(
                "Stored lesson failed validation; learner_id=%s topic_id=%s",
                learner.id,
                topic.id,
            )
            continue
        source = "cache" if artifact.status == "completed" else "curated_fallback"
        return content, source
    return None


def generate_learning_content(
    topic: Topic,
    learner: Learner,
    database: Session,
) -> tuple[LearningContent, str]:
    skills = database.scalars(select(SkillScore).where(SkillScore.learner_id == learner.id)).all()
    weak_records = database.scalars(
        select(Weakness).where(
            Weakness.learner_id == learner.id,
            Weakness.status == "open",
        )
    ).all()
    weak_concepts = list(dict.fromkeys(
        [weakness.concept for weakness in weak_records]
        + [skill.concept for skill in skills if skill.score < 0.75]
    ))
    strong_concepts = [skill.concept for skill in skills if skill.score >= 0.75]
    progress = database.scalars(
        select(TopicProgress).where(TopicProgress.learner_id == learner.id)
    ).all()
    prerequisite_topics = database.scalars(
        select(Topic)
        .join(TopicPrerequisite, TopicPrerequisite.prerequisite_id == Topic.id)
        .where(TopicPrerequisite.topic_id == topic.id)
    ).all()
    prerequisites = [item.title for item in prerequisite_topics]
    course = database.get(GeneratedCourse, topic.course_id) if topic.course_id else None
    if course is not None and course.learner_id != learner.id:
        raise ValueError("Learning topic course is not owned by the learner")
    saved_course_lesson = _previous_course_lesson(topic, learner, database)
    if saved_course_lesson is not None:
        content, source = saved_course_lesson
        return _ensure_structured_lesson(content, topic, weak_concepts), source
    current_module = next(
        (
            module
            for module in (course.modules_json or [])
            if topic.id in module.get("topic_ids", [])
        ),
        None,
    ) if course else None
    course_context = (
        {
            "course_id": course.id,
            "title": course.title,
            "track_id": course.track_id,
            "learning_objectives": course.learning_objectives_json[:8],
            "module": (
                {
                    "module_id": current_module.get("module_id"),
                    "title": current_module.get("title"),
                    "description": current_module.get("description"),
                    "order": current_module.get("order"),
                    "learning_objectives": current_module.get("learning_objectives", []),
                }
                if current_module
                else None
            ),
        }
        if course
        else None
    )
    course_topic_ids = [item.id for item in course.topics] if course else [topic.id]
    completed_topics = [
        database.get(Topic, item.topic_id).title
        for item in progress
        if item.status == "completed"
        and item.topic_id in course_topic_ids
        and database.get(Topic, item.topic_id)
    ]
    assessments = database.scalars(
        select(Assessment)
        .where(Assessment.learner_id == learner.id, Assessment.topic_id.in_(course_topic_ids))
        .order_by(Assessment.created_at.desc())
        .limit(5)
    ).all()
    recent_assessments = []
    for assessment in assessments:
        if not assessment.topic_id or (
            assessment.score is None and assessment.percentage is None
        ):
            continue
        assessed_topic = database.get(Topic, assessment.topic_id)
        recent_assessments.append(
            {
                "topic": display_topic_title(assessed_topic.title) if assessed_topic else assessment.topic_id,
                "percentage": assessment.percentage
                if assessment.percentage is not None
                else round((assessment.score or 0.0) * 100, 1),
                "selected_types": assessment.selected_types,
            }
        )
    cache_context = {
        "lesson_schema_version": 3,
        "topic_id": topic.id,
        "topic_description": topic.description,
        "course": course_context,
        "learner": {
            "experience_level": learner.experience_level,
            "goal": learner.goal_text,
            "target_outcome": learner.target_outcome,
            "track": course.track_id if course else learner.track,
        },
        "prerequisites": prerequisites,
    }

    def generate() -> tuple[LearningContent, str]:
        if settings.openrouter_api_key:
            try:
                return (
                    _openrouter_content(
                        topic,
                        learner,
                        weak_concepts,
                        strong_concepts,
                        completed_topics,
                        recent_assessments,
                        prerequisites,
                        course_context,
                    ),
                    "openrouter",
                )
            except (AIProviderError, ValidationError, ValueError) as error:
                logger.warning(
                    "AI operation used curated fallback; operation=learning_content reason=%s",
                    type(error).__name__,
                )
        return _fallback_content(topic, learner, weak_concepts, prerequisites), "curated_fallback"

    content, source = get_or_generate_artifact(
        database,
        learner_id=learner.id,
        operation="learning_content",
        key_context=cache_context,
        response_model=LearningContent,
        generate=generate,
        fallback=lambda: _fallback_content(topic, learner, weak_concepts, prerequisites),
        persist_fallback=True,
    )
    return (
        _ensure_structured_lesson(content, topic, weak_concepts),
        source,
    )