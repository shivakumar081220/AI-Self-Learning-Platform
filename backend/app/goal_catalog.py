from .schemas import GoalOption


GOAL_OPTIONS = [
    GoalOption(
        key="llm_apps",
        label="Build LLM-powered applications",
        description="Learn the foundations and patterns needed to build useful LLM products.",
    ),
    GoalOption(
        key="prompt_engineering",
        label="Master prompt engineering",
        description="Design reliable prompts, structured outputs, and reusable prompt workflows.",
    ),
    GoalOption(
        key="rag",
        label="Build a RAG application",
        description="Learn how to ground LLM answers with retrieval, context, and citations.",
    ),
    GoalOption(
        key="ai_agents",
        label="Create AI agents",
        description="Understand tool use, orchestration, planning, and safe agentic systems.",
    ),
]


GOAL_BY_KEY = {goal.key: goal for goal in GOAL_OPTIONS}
