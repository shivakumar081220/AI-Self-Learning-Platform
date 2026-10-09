import json
from collections.abc import Generator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import Learner, LearningPath, SkillScore, TopicProgress
from app.seed_topics import seed_topics
from app.services import ai_provider, content_service
from app.services.content_service import CURATED_CONTENT
from app.services.path_engine import generate_path_plan
from app.schemas import LearningContent


class FakeContentProvider:
    response_content: str = ""
    captured_messages: list[dict] = []

    def __init__(self, **kwargs):
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(
                with_raw_response=SimpleNamespace(create=self.create_raw_response)
            )
        )

    def create_raw_response(self, **kwargs):
        FakeContentProvider.captured_messages = kwargs["messages"]
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.response_content))]
        )
        return SimpleNamespace(status_code=200, parse=lambda: response)


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase6-api.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as database:
        seed_topics(database)

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine) as database:
            yield database

    app.dependency_overrides[get_db] = override_get_db
    app.state.phase6_test_engine = engine
    yield TestClient(app)
    app.dependency_overrides.clear()
    del app.state.phase6_test_engine


def create_learner_and_path(client: TestClient) -> tuple[dict, dict]:
    learner = client.post(
        "/api/learners",
        json={
            "name": "Learning User",
            "experience_level": "beginner",
            "goal_key": "llm_apps",
        },
    ).json()
    path = client.post(f"/api/learners/{learner['id']}/learning-path/generate").json()
    return learner, path


def fallback_content(topic_id: str, title: str) -> str:
    data = CURATED_CONTENT[topic_id]
    return json.dumps(
        {
            "topic_id": topic_id,
            "topic_title": title,
            **data,
            "real_world_example": data["practical_example"],
            "practice_suggestion": "Explain the idea and test it with one example.",
            "prerequisites": [],
            "introduction": data["overview"],
            "why_it_matters": data["practical_example"],
            "sections": [
                {
                    "title": "Core ideas",
                    "summary": data["explanation"],
                    "subsections": [
                        {
                            "title": data["key_concepts"][0],
                            "explanation": data["explanation"],
                            "key_points": data["quick_recap"][:2],
                            "examples": data["examples"][:1],
                            "practical_application": data["practical_example"],
                            "tutor_prompts": ["Explain the idea", "Show an example"],
                        }
                    ],
                }
            ],
            "common_mistake_details": [
                {
                    "mistake": data["common_mistakes"][0],
                    "explanation": data["explanation"],
                    "correction": data["practical_example"],
                }
            ],
            "key_takeaways": data["quick_recap"][:2],
            "self_check": [
                {
                    "question": f"How does {title} apply to a real task?",
                    "hint": data["practical_example"],
                }
            ],
            "assessment_recommendation": "Explain the concept, then apply it to a new example.",
            "coding_example": {
                "title": "Inspect a message",
                "code": "message = {'role': 'user'}\nprint(message['role'])",
                "explanation": "A small structured value makes the concept concrete.",
                "expected_output": "user",
                "why_it_matters": "Small examples make abstract implementation details easier to inspect.",
                "common_mistake": "Assuming a structured value is valid without checking its fields.",
            },
        }
    )


def test_current_topic_and_unknown_learner(client: TestClient):
    learner, path = create_learner_and_path(client)
    current = client.get(f"/api/learners/{learner['id']}/learning-path/current")

    assert current.status_code == 200
    assert current.json()["topic_id"] == path["current_topic_id"]
    assert client.get("/api/learners/99999/learning-path/current").status_code == 404


def test_valid_topic_returns_curated_fallback_and_starts_progress(client: TestClient, monkeypatch):
    learner, path = create_learner_and_path(client)
    monkeypatch.setattr(settings, "openrouter_api_key", "")

    response = client.get(
        f"/api/learners/{learner['id']}/topics/{path['current_topic_id']}/content"
    )

    assert response.status_code == 200
    assert response.json()["source"] == "curated_fallback"
    assert response.json()["content"]["topic_id"] == path["current_topic_id"]
    content = response.json()["content"]
    assert content["title"]
    assert content["introduction"]
    assert content["why_it_matters"]
    assert content["sections"]
    assert all(section["subsections"] for section in content["sections"])
    assert content["common_mistake_details"]
    assert content["key_takeaways"]
    assert content["self_check"]
    assert content["assessment_recommendation"]
    assert response.json()["content"]["sections"][0]["subsections"][0]["examples"]
    assert response.json()["content"]["practice_suggestion"]
    with Session(app.state.phase6_test_engine) as database:
        progress = database.scalar(
            select(TopicProgress).where(
                TopicProgress.learner_id == learner["id"],
                TopicProgress.topic_id == path["current_topic_id"],
            )
        )
        assert progress.status == "in_progress"


def test_invalid_and_outside_path_topics_are_rejected(client: TestClient):
    learner, path = create_learner_and_path(client)
    invalid = client.get(f"/api/learners/{learner['id']}/topics/not-a-topic/content")
    assert invalid.status_code == 404

    with Session(app.state.phase6_test_engine) as database:
        stored_path = database.scalar(
            select(LearningPath).where(LearningPath.learner_id == learner["id"])
        )
        stored_path.path_json = [stored_path.path_json[stored_path.current_index]]
        stored_path.current_index = 0
        database.commit()

    outside = client.get(
        f"/api/learners/{learner['id']}/topics/prompt-engineering/content"
    )
    assert outside.status_code == 404


def test_mocked_openrouter_content_uses_learner_context(client: TestClient, monkeypatch):
    learner, path = create_learner_and_path(client)
    topic_id = path["current_topic_id"]
    title = path["topics"][path["current_index"]]["title"]
    FakeContentProvider.response_content = fallback_content(topic_id, title)
    FakeContentProvider.captured_messages = []
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(ai_provider, "OpenAI", FakeContentProvider)
    with Session(app.state.phase6_test_engine) as database:
        database.add(
            SkillScore(
                learner_id=learner["id"],
                concept="llm_fundamentals",
                score=0.2,
                evidence_count=2,
                confidence=0.6,
                source="diagnostic",
            )
        )
        database.commit()

    response = client.post(
        f"/api/learners/{learner['id']}/topics/{topic_id}/content/generate"
    )
    prompt_text = FakeContentProvider.captured_messages[1]["content"]

    assert response.status_code == 200
    assert response.json()["source"] == "openrouter"
    assert "Build LLM-powered applications" in prompt_text
    assert "llm_fundamentals" in prompt_text
    assert topic_id in prompt_text


def test_provider_failure_invalid_output_and_missing_key_fallback(
    client: TestClient, monkeypatch
):
    learner, path = create_learner_and_path(client)
    topic_id = path["current_topic_id"]
    title = path["topics"][path["current_index"]]["title"]
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(ai_provider, "OpenAI", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("down")))

    failed = client.post(
        f"/api/learners/{learner['id']}/topics/{topic_id}/content/generate"
    )
    assert failed.status_code == 200
    assert failed.json()["source"] == "curated_fallback"

    FakeContentProvider.response_content = json.dumps(
        {"topic_id": "arbitrary-topic", "topic_title": title, **CURATED_CONTENT[topic_id]}
    )
    monkeypatch.setattr(ai_provider, "OpenAI", FakeContentProvider)
    invalid = client.post(
        f"/api/learners/{learner['id']}/topics/{topic_id}/content/generate"
    )
    assert invalid.status_code == 200
    assert invalid.json()["source"] == "curated_fallback"

    monkeypatch.setattr(settings, "openrouter_api_key", "")
    missing = client.get(
        f"/api/learners/{learner['id']}/topics/{topic_id}/content"
    )
    assert missing.status_code == 200
    assert missing.json()["source"] == "curated_fallback"


def test_completion_persists_and_repeated_completion_is_safe(client: TestClient):
    learner, path = create_learner_and_path(client)
    topic_id = path["current_topic_id"]

    first = client.post(f"/api/learners/{learner['id']}/topics/{topic_id}/complete")
    second = client.post(f"/api/learners/{learner['id']}/topics/{topic_id}/complete")

    assert first.status_code == 200
    assert second.status_code == 200
    with Session(app.state.phase6_test_engine) as database:
        progress = database.scalar(
            select(TopicProgress).where(
                TopicProgress.learner_id == learner["id"], TopicProgress.topic_id == topic_id
            )
        )
        assert progress.status == "in_progress"
        assert progress.lesson_completed is True
        assert progress.mastery_score == 0
        stored_path = database.scalar(
            select(LearningPath).where(LearningPath.learner_id == learner["id"])
        )
        assert stored_path.current_index == 0
