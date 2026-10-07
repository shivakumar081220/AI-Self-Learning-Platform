from .schemas import AITrackOption


AI_TRACKS = [
    AITrackOption(
        id="python_for_ai",
        name="Python for AI",
        description="Build the programming foundations used in data and AI workflows.",
        learning_objective="Prepare, inspect, and transform data with Python for AI tasks.",
        difficulty="beginner",
        example_goals=["Learn Python for model experiments", "Prepare datasets for machine learning"],
        prerequisite_tracks=[],
    ),
    AITrackOption(
        id="machine_learning",
        name="Machine Learning",
        description="Understand data-driven models, training, evaluation, and practical prediction.",
        learning_objective="Train and evaluate suitable machine-learning models for a real problem.",
        difficulty="beginner",
        example_goals=["Learn ML for data analysis", "Build a classifier and evaluate its errors"],
        prerequisite_tracks=["python_for_ai"],
    ),
    AITrackOption(
        id="deep_learning",
        name="Deep Learning",
        description="Explore neural networks, tensors, training loops, and model evaluation.",
        learning_objective="Explain and train a small neural network, then interpret its behavior.",
        difficulty="intermediate",
        example_goals=["Understand neural networks", "Train a small image classifier"],
        prerequisite_tracks=["python_for_ai", "machine_learning"],
    ),
    AITrackOption(
        id="nlp",
        name="Natural Language Processing",
        description="Work with text, language representations, and NLP evaluation workflows.",
        learning_objective="Turn text into useful representations and build an evaluated NLP feature.",
        difficulty="intermediate",
        example_goals=["Build a text classifier", "Understand tokenization and language representations"],
        prerequisite_tracks=["python_for_ai", "machine_learning"],
    ),
    AITrackOption(
        id="generative_ai",
        name="Generative AI",
        description="Design useful generative systems with prompts, validation, and evaluation.",
        learning_objective="Build a bounded generative AI application and assess its quality.",
        difficulty="beginner",
        example_goals=["Build an LLM-powered application", "Learn reliable prompt and output patterns"],
        prerequisite_tracks=[],
    ),
    AITrackOption(
        id="llms",
        name="Large Language Models",
        description="Understand language-model behavior and build applications around LLMs.",
        learning_objective="Explain model inputs and limits, then build a validated LLM feature.",
        difficulty="intermediate",
        example_goals=["Learn how LLMs work", "Build a structured-output LLM application"],
        prerequisite_tracks=["nlp", "deep_learning"],
    ),
    AITrackOption(
        id="rag",
        name="Retrieval-Augmented Generation (RAG)",
        description="Ground generated answers in retrieved documents and traceable evidence.",
        learning_objective="Build and evaluate a document question-answering workflow with retrieval.",
        difficulty="intermediate",
        example_goals=["Build a document chatbot", "Add citations to a knowledge assistant"],
        prerequisite_tracks=["nlp", "llms"],
    ),
    AITrackOption(
        id="ai_agents",
        name="AI Agents / Agentic Systems",
        description="Build controlled agents that use tools, observe results, and complete tasks.",
        learning_objective="Implement an agent workflow with validated tools and measurable outcomes.",
        difficulty="intermediate",
        example_goals=["Build an AI agent that uses tools", "Design a safe multi-step assistant"],
        prerequisite_tracks=["llms"],
    ),
]

TRACK_BY_ID = {track.id: track for track in AI_TRACKS}

LEGACY_GOAL_TRACK = {
    "llm_apps": "generative_ai",
    "prompt_engineering": "generative_ai",
    "rag": "generative_ai",
    "ai_agents": "ai_agents",
}


def infer_track_id(goal_text: str, goal_key: str | None = None) -> str:
    if goal_key in LEGACY_GOAL_TRACK:
        return LEGACY_GOAL_TRACK[goal_key]
    normalized = goal_text.lower()
    if "agent" in normalized or "tool use" in normalized:
        return "ai_agents"
    if "rag" in normalized or "retriev" in normalized or "document chatbot" in normalized:
        return "rag"
    if "large language model" in normalized or "llm" in normalized:
        return "llms"
    if "natural language" in normalized or "nlp" in normalized or "text classification" in normalized:
        return "nlp"
    if "deep learning" in normalized or "neural network" in normalized:
        return "deep_learning"
    if "machine learning" in normalized or "ml for" in normalized:
        return "machine_learning"
    if "python" in normalized or "pandas" in normalized or "numpy" in normalized:
        return "python_for_ai"
    return "generative_ai"