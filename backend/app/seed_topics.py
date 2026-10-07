from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Topic, TopicPrerequisite


TOPIC_CATALOG = [
    {
        "id": "ai-foundations",
        "title": "Generative AI Foundations",
        "description": "Core ideas behind generative models, language models, and AI application workflows.",
        "difficulty": "beginner",
        "concept_tags": ["ai_fundamentals", "generative_models", "llm_fundamentals"],
        "goal_relevance": {"llm_apps": 1.0, "prompt_engineering": 0.9, "rag": 0.8, "ai_agents": 0.8},
        "content_source": "Curated internal topic brief based on OpenAI developer concepts",
    },
    {
        "id": "prompt-engineering",
        "title": "Prompt Engineering",
        "description": "Designing clear, testable prompts with context, constraints, examples, and output contracts.",
        "difficulty": "beginner",
        "concept_tags": ["prompt_design", "few_shot_learning", "structured_outputs"],
        "goal_relevance": {"llm_apps": 1.0, "prompt_engineering": 1.0, "rag": 0.8, "ai_agents": 0.9},
        "content_source": "Curated internal topic brief based on OpenAI prompting guidance",
    },
    {
        "id": "tokenization-embeddings",
        "title": "Tokenization and Embeddings",
        "description": "How text becomes tokens and vectors, and why representations matter for retrieval and generation.",
        "difficulty": "beginner",
        "concept_tags": ["tokenization", "embeddings", "vector_representation"],
        "goal_relevance": {"llm_apps": 0.9, "prompt_engineering": 0.6, "rag": 1.0, "ai_agents": 0.8},
        "content_source": "Curated internal topic brief based on transformer and retrieval fundamentals",
    },
    {
        "id": "attention-transformers",
        "title": "Attention and Transformers",
        "description": "The attention mechanism and transformer architecture that power modern language models.",
        "difficulty": "intermediate",
        "concept_tags": ["attention", "self_attention", "positional_encoding", "transformers"],
        "goal_relevance": {"llm_apps": 0.8, "prompt_engineering": 0.4, "rag": 0.7, "ai_agents": 0.7},
        "content_source": "Curated internal topic brief based on transformer architecture fundamentals",
    },
    {
        "id": "llm-application-patterns",
        "title": "LLM Application Patterns",
        "description": "Reliable application patterns for prompting, tool calls, structured responses, and evaluation loops.",
        "difficulty": "intermediate",
        "concept_tags": ["llm_workflows", "structured_outputs", "tool_calls", "evaluation"],
        "goal_relevance": {"llm_apps": 1.0, "prompt_engineering": 0.9, "rag": 0.9, "ai_agents": 1.0},
        "content_source": "Curated internal topic brief based on production LLM application patterns",
    },
    {
        "id": "retrieval-augmented-generation",
        "title": "Retrieval-Augmented Generation",
        "description": "Grounding model responses in retrieved context using chunking, embeddings, search, and citations.",
        "difficulty": "intermediate",
        "concept_tags": ["rag", "retrieval", "chunking", "grounding", "citations"],
        "goal_relevance": {"llm_apps": 1.0, "prompt_engineering": 0.7, "rag": 1.0, "ai_agents": 0.9},
        "content_source": "Curated internal topic brief based on retrieval and grounding fundamentals",
    },
    {
        "id": "evaluation-safety",
        "title": "LLM Evaluation and Safety",
        "description": "Testing quality, factuality, robustness, and safety of generative AI applications.",
        "difficulty": "intermediate",
        "concept_tags": ["evaluation", "hallucination", "safety", "quality_metrics"],
        "goal_relevance": {"llm_apps": 0.9, "prompt_engineering": 0.8, "rag": 0.9, "ai_agents": 0.9},
        "content_source": "Curated internal topic brief based on evaluation and responsible AI practices",
    },
    {
        "id": "ai-agents",
        "title": "AI Agents and Tool Use",
        "description": "How models plan, call tools, observe results, and complete multi-step tasks with safeguards.",
        "difficulty": "advanced",
        "concept_tags": ["agents", "tool_use", "planning", "orchestration"],
        "goal_relevance": {"llm_apps": 0.9, "prompt_engineering": 0.8, "rag": 0.8, "ai_agents": 1.0},
        "content_source": "Curated internal topic brief based on agentic application patterns",
    },
    {
        "id": "production-llm-systems",
        "title": "Production LLM Systems",
        "description": "Putting an LLM application into practice with monitoring, latency, cost, and reliability controls.",
        "difficulty": "advanced",
        "concept_tags": ["observability", "latency", "cost", "reliability"],
        "goal_relevance": {"llm_apps": 1.0, "prompt_engineering": 0.7, "rag": 0.9, "ai_agents": 1.0},
        "content_source": "Curated internal topic brief based on production system design principles",
    },
]


PREREQUISITES = {
    "prompt-engineering": ["ai-foundations"],
    "tokenization-embeddings": ["ai-foundations"],
    "attention-transformers": ["ai-foundations", "tokenization-embeddings"],
    "llm-application-patterns": ["ai-foundations", "prompt-engineering"],
    "retrieval-augmented-generation": ["tokenization-embeddings", "llm-application-patterns"],
    "evaluation-safety": ["llm-application-patterns"],
    "ai-agents": ["llm-application-patterns", "evaluation-safety"],
    "production-llm-systems": ["retrieval-augmented-generation", "evaluation-safety", "ai-agents"],
}


def seed_topics(database: Session) -> None:
    existing_topic_ids = set(database.scalars(select(Topic.id)).all())

    for topic_data in TOPIC_CATALOG:
        if topic_data["id"] not in existing_topic_ids:
            database.add(Topic(**topic_data))

    database.flush()

    existing_relationships = set(
        database.execute(
            select(TopicPrerequisite.topic_id, TopicPrerequisite.prerequisite_id)
        ).all()
    )
    for topic_id, prerequisite_ids in PREREQUISITES.items():
        for prerequisite_id in prerequisite_ids:
            relationship = (topic_id, prerequisite_id)
            if relationship not in existing_relationships:
                database.add(
                    TopicPrerequisite(
                        topic_id=topic_id,
                        prerequisite_id=prerequisite_id,
                    )
                )

    database.commit()
