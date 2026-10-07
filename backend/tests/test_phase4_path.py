from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, get_db
from app.main import app
from app.models import Assessment, Learner, SkillScore, Topic, TopicProgress
from app.seed_topics import seed_topics
from app.services.path_engine import (
    generate_path_plan,
    validate_path_payload,
)


@pytest.fixture
def database(tmp_path) -> Generator[Session, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase4-engine.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        seed_topics(session)
        yield session


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase4-api.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        seed_topics(session)

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def add_learner(database: Session, goal: str, experience: str = "beginner") -> Learner:
    learner = Learner(
        name=f"Learner {goal}",
        experience_level=experience,
        goal_text=goal,
    )
    database.add(learner)
    database.commit()
    database.refresh(learner)
    return learner


def add_skill(database: Session, learner_id: int, concept: str, score: float) -> None:
    database.add(
        SkillScore(
            learner_id=learner_id,
            concept=concept,
            score=score,
            evidence_count=3,
            confidence=1.0,
            source="diagnostic",
        )
    )


def complete_topics(database: Session, learner_id: int, topic_ids: list[str]) -> None:
    database.add_all(
        [
            TopicProgress(
                learner_id=learner_id,
                topic_id=topic_id,
                status="completed",
                mastery_score=1.0,
            )
            for topic_id in topic_ids
        ]
    )
    database.commit()


def test_different_goals_produce_different_engine_paths(database: Session):
    rag_learner = add_learner(database, "Build a RAG application")
    prompt_learner = add_learner(database, "Master prompt engineering")

    rag_path = generate_path_plan(database, rag_learner)
    prompt_path = generate_path_plan(database, prompt_learner)

    rag_ids = [item["topic_id"] for item in rag_path["topics"]]
    prompt_ids = [item["topic_id"] for item in prompt_path["topics"]]
    assert rag_ids != prompt_ids
    assert rag_ids[1] == "tokenization-embeddings"
    assert prompt_ids[1] == "prompt-engineering"


def test_prerequisites_are_ordered_before_dependents(database: Session):
    learner = add_learner(database, "Build a RAG application")
    path = generate_path_plan(database, learner)
    positions = {item["topic_id"]: index for index, item in enumerate(path["topics"])}

    for item in path["topics"]:
        for prerequisite_id in item["prerequisites"]:
            assert positions[prerequisite_id] < positions[item["topic_id"]]


def test_weak_concept_is_prioritized_with_goal_relevance(database: Session):
    learner = add_learner(database, "Build a RAG application")
    add_skill(database, learner.id, "retrieval", 0.2)
    database.commit()

    path = generate_path_plan(database, learner)
    rag_item = next(item for item in path["topics"] if item["topic_id"] == "retrieval-augmented-generation")

    assert "weak concepts: retrieval" in rag_item["reason"]
    assert rag_item["relevance_score"] == 1.0


def test_completed_topics_are_retained_as_history_and_not_recommended_again(database: Session):
    learner = add_learner(database, "Build a RAG application")
    complete_topics(database, learner.id, ["ai-foundations"])

    path = generate_path_plan(database, learner)
    foundation_items = [item for item in path["topics"] if item["topic_id"] == "ai-foundations"]

    assert len(foundation_items) == 1
    assert foundation_items[0]["status"] == "completed"
    assert [item["topic_id"] for item in path["topics"]].count("ai-foundations") == 1


def test_strong_learner_progresses_to_goal_relevant_advanced_topic(database: Session):
    learner = add_learner(database, "Create AI agents", experience="advanced")
    complete_topics(
        database,
        learner.id,
        [
            "ai-foundations",
            "prompt-engineering",
            "tokenization-embeddings",
            "llm-application-patterns",
            "evaluation-safety",
            "retrieval-augmented-generation",
        ],
    )

    path = generate_path_plan(database, learner)
    pending_ids = [item["topic_id"] for item in path["topics"] if item["status"] != "completed"]

    assert pending_ids[0] == "ai-agents"


def test_weak_learner_receives_remediation_topic(database: Session):
    learner = add_learner(database, "Understand transformer architecture")
    complete_topics(database, learner.id, ["ai-foundations", "tokenization-embeddings"])
    add_skill(database, learner.id, "self_attention", 0.2)
    database.add(
        TopicProgress(
            learner_id=learner.id,
            topic_id="attention-transformers",
            status="remediation",
            mastery_score=0.3,
        )
    )
    database.commit()

    path = generate_path_plan(database, learner)
    attention = next(item for item in path["topics"] if item["topic_id"] == "attention-transformers")

    assert attention["status"] == "remediation"
    assert "weak concepts: self attention" in attention["reason"]


def test_learning_path_api_persists_and_regenerates(client: TestClient):
    learner = client.post(
        "/api/learners",
        json={
            "name": "Path User",
            "experience_level": "intermediate",
            "goal_key": "rag",
        },
    ).json()

    generated = client.post(f"/api/learners/{learner['id']}/learning-path/generate")
    assert generated.status_code == 200
    generated_body = generated.json()
    fetched = client.get(f"/api/learners/{learner['id']}/learning-path")
    regenerated = client.post(f"/api/learners/{learner['id']}/learning-path/regenerate")

    assert fetched.status_code == 200
    assert fetched.json()["path_id"] == generated_body["path_id"]
    assert regenerated.status_code == 200
    assert regenerated.json()["path_id"] != generated_body["path_id"]
    assert regenerated.json()["current_topic_id"] == generated_body["current_topic_id"]


def test_unknown_topic_payload_is_rejected(database: Session):
    learner = add_learner(database, "Build a RAG application")
    path = generate_path_plan(database, learner)
    path["topics"][0]["topic_id"] = "not-in-catalog"
    topic_by_id = {topic.id: topic for topic in database.query(Topic).all()}

    with pytest.raises(ValueError, match="Unknown topic"):
        validate_path_payload(path, topic_by_id)
