import json
from collections.abc import Generator
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base
from app.models import Assessment, Learner, SkillScore, Topic, Weakness
from app.seed_topics import seed_topics
from app.services import ai_provider
from app.services.curriculum_service import generate_curriculum
from app.services.learning_ai_service import generate_remediation_aid, interpret_skill_results
from app.services.tutor_service import answer_tutor_question


class FakeOpenRouter:
    content = "{}"
    request = None

    def __init__(self, **kwargs):
        FakeOpenRouter.client_options = kwargs
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        FakeOpenRouter.request = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=FakeOpenRouter.content))]
        )


@pytest.fixture
def learning_context(tmp_path, monkeypatch) -> Generator[tuple[Session, Learner], None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'ai-pipeline.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as database:
        seed_topics(database)
        learner = Learner(
            name="AI Pipeline",
            experience_level="intermediate",
            goal_text="Build a retrieval-augmented support assistant",
            target_outcome="Ship a cited support-answer prototype",
            track="rag",
        )
        database.add(learner)
        database.flush()
        database.add(
            SkillScore(
                learner_id=learner.id,
                concept="embeddings",
                score=0.35,
                evidence_count=2,
                confidence=0.6,
                source="diagnostic",
            )
        )
        database.add(
            Weakness(
                learner_id=learner.id,
                topic_id="retrieval-augmented-generation",
                concept="embeddings",
                severity="high",
                status="open",
            )
        )
        database.add(
            Assessment(
                learner_id=learner.id,
                assessment_type="diagnostic",
                questions_json=[],
                answers_json=[],
                score=0.5,
                completed_at=datetime.utcnow(),
            )
        )
        database.commit()
        database.refresh(learner)
        monkeypatch.setattr(settings, "openrouter_api_key", "test-provider-key")
        monkeypatch.setattr(settings, "openrouter_model", "router/pipeline-test")
        monkeypatch.setattr(ai_provider, "OpenAI", FakeOpenRouter)
        yield database, learner
    engine.dispose()


def curriculum_response(goal: str) -> str:
    return json.dumps(
        {
            "course_title": "Grounded Support Assistants",
            "description": "A progression toward shipping a grounded support assistant.",
            "track_id": "rag",
            "goal": goal,
            "level": "intermediate",
            "estimated_duration": "180 minutes",
            "topics": [
                {
                    "title": "Embeddings",
                    "description": "Represent text as vectors for semantic comparison.",
                    "learning_objectives": ["Explain vectors", "Compare semantic similarity"],
                    "difficulty": "beginner",
                    "concepts": ["embeddings"],
                    "prerequisites": [],
                    "estimated_minutes": 40,
                },
                {
                    "title": "Retrieval",
                    "description": "Retrieve relevant chunks for a learner question.",
                    "learning_objectives": ["Select chunks", "Inspect relevance"],
                    "difficulty": "intermediate",
                    "concepts": ["retrieval"],
                    "prerequisites": ["Embeddings"],
                    "estimated_minutes": 50,
                },
                {
                    "title": "Grounded Responses",
                    "description": "Generate answers using retrieved evidence and citations.",
                    "learning_objectives": ["Use evidence", "Preserve citations"],
                    "difficulty": "intermediate",
                    "concepts": ["grounding"],
                    "prerequisites": ["Retrieval"],
                    "estimated_minutes": 60,
                },
            ],
        }
    )


def test_curriculum_prompt_uses_outcome_skill_gaps_and_catalog(learning_context):
    database, learner = learning_context
    FakeOpenRouter.content = curriculum_response(learner.goal_text)

    curriculum, source = generate_curriculum(learner, database)

    payload = json.loads(FakeOpenRouter.request["messages"][1]["content"])
    context = payload
    assert source == "openrouter"
    assert curriculum.topics[1].prerequisites == ["Embeddings"]
    assert context["learner"]["target_outcome"] == "Ship a cited support-answer prototype"
    assert context["learner"]["track"] == "rag"
    assert context["learner"]["weak_concepts"] == ["embeddings"]
    assert context["learner"]["recent_assessments"][0]["score"] == 0.5
    assert any("retrieval" in item["title"].lower() for item in context["topic_catalog"])
    assert FakeOpenRouter.request["model"] == "router/pipeline-test"


def test_tutor_receives_level_goal_course_modules_and_returns_structured_help(learning_context):
    database, learner = learning_context
    FakeOpenRouter.content = json.dumps(
        {
            "answer": "Embeddings represent text as vectors so similar meanings can be compared.",
            "simple_explanation": "Embeddings turn pieces of text into numbers that reflect their meaning.",
            "example": "A refund question can retrieve a policy paragraph with similar meaning.",
            "coding_example": {
                "title": "Compare two vectors",
                "code": "left = [1.0, 0.0]\nright = [0.8, 0.2]\nprint(len(left) == len(right))",
                "explanation": "Vector dimensions must align before comparison.",
                "expected_output": "True",
                "why_it_matters": "Matching dimensions are required for vector similarity operations.",
                "common_mistake": "Comparing vectors with different dimensions.",
            },
            "key_points": ["Vectors represent meaning.", "Similarity ranks candidate context."],
            "related_topic": "Retrieval",
            "suggested_next_action": "Continue to Retrieval in the course.",
            "follow_up": "What text would you compare first?",
        }
    )
    topic = database.get(Topic, "retrieval-augmented-generation")

    answer, source = answer_tutor_question(
        learner,
        topic,
        "How do embeddings help retrieval?",
        ["embeddings"],
        "Grounded Support Assistants",
        ["Embeddings", "Retrieval", "Grounded Responses"],
        ["Python for AI"],
        [{"topic_id": "embedding-topic", "score": 0.62}],
    )

    payload = json.loads(FakeOpenRouter.request["messages"][1]["content"])
    context = payload["context"]
    assert source == "openrouter"
    assert answer.key_points
    assert context["learner"]["experience_level"] == "intermediate"
    assert context["learner"]["goal"] == learner.goal_text
    assert context["learner"]["track_id"] == "rag"
    assert context["learner"]["completed_topics"] == ["Python for AI"]
    assert context["learner"]["recent_assessments"][0]["score"] == 0.62
    assert context["course"]["allowed_module_titles"] == ["Embeddings", "Retrieval", "Grounded Responses"]
    assert "Never invent courses" in FakeOpenRouter.request["messages"][0]["content"]


def test_skill_interpretation_preserves_deterministic_score_and_limits_concepts(learning_context):
    _, learner = learning_context
    FakeOpenRouter.content = json.dumps(
        {
            "summary": "Your score is developing; strengthen embeddings before building retrieval workflows.",
            "focus_concepts": ["embeddings"],
        }
    )

    interpretation, source = interpret_skill_results(
        learner, 62, ["embeddings"], ["retrieval"], ["prompt_design"]
    )

    context = json.loads(FakeOpenRouter.request["messages"][1]["content"])
    assert source == "openrouter"
    assert context["deterministic_score_percentage"] == 62
    assert interpretation.focus_concepts == ["embeddings"]


def test_invalid_interpretation_and_remediation_use_labeled_fallbacks(learning_context):
    database, learner = learning_context
    FakeOpenRouter.content = json.dumps(
        {"summary": "Focus on a fabricated concept.", "focus_concepts": ["invented_module"]}
    )
    interpretation, interpretation_source = interpret_skill_results(
        learner, 42, ["embeddings"], [], []
    )
    assert interpretation_source == "deterministic_fallback"
    assert "42%" in interpretation.summary

    FakeOpenRouter.content = json.dumps(
        {
            "explanation": "Revisit embeddings by comparing the representation of related texts.",
            "practice_suggestion": "Compare two short strings and explain which should be closer.",
        }
    )
    aid, remediation_source = generate_remediation_aid(
        learner,
        database.get(Topic, "retrieval-augmented-generation"),
        ["embeddings"],
        42,
        "Revisit weak concepts.",
    )
    assert remediation_source == "openrouter"
    assert "Compare two short strings" in aid.practice_suggestion


def test_tutor_fallback_answers_topic_question_and_rejects_unknown_modules(
    learning_context, monkeypatch
):
    database, learner = learning_context
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    topic = database.get(Topic, "ai-agents")

    answer, source = answer_tutor_question(
        learner,
        topic,
        "How does an agent decide when to use a tool?",
        ["tool_use"],
        "Grounded Support Assistants",
        ["Embeddings", "Retrieval", "Grounded Responses"],
    )
    unrelated, unrelated_source = answer_tutor_question(
        learner,
        topic,
        "Show me a new course module about game monetization.",
        ["tool_use"],
        "Grounded Support Assistants",
        ["Embeddings", "Retrieval", "Grounded Responses"],
    )
    current_module, current_module_source = answer_tutor_question(
        learner,
        topic,
        "Explain the current Agent Planning module.",
        ["tool_use"],
        "Create AI agents",
        ["Agent Planning · 3", "Agent Evaluation · 3"],
    )

    assert source == unrelated_source == "deterministic_fallback"
    assert current_module_source == "deterministic_fallback"
    assert "validate" in answer.answer.lower()
    assert answer.example
    assert "won't invent one" in unrelated.answer
    assert "won't invent one" not in current_module.answer
