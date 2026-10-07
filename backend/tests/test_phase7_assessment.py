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
from app.models import Assessment, LearningPath, Recommendation, SkillScore, TopicProgress, Weakness
from app.seed_topics import seed_topics
from app.services import assessment_service
from app.services.assessment_service import QUESTION_BANK


class FakeAssessmentProvider:
    response_content = ""

    def __init__(self, **kwargs):
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self.create_completion)
        )

    def create_completion(self, **kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.response_content))]
        )


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase7-api.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as database:
        seed_topics(database)

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine) as database:
            yield database

    app.dependency_overrides[get_db] = override_get_db
    app.state.phase7_test_engine = engine
    yield TestClient(app)
    app.dependency_overrides.clear()
    del app.state.phase7_test_engine


def prepare_learned_topic(client: TestClient) -> tuple[dict, dict, str]:
    learner = client.post(
        "/api/learners",
        json={
            "name": "Assessment User",
            "experience_level": "beginner",
            "goal_key": "llm_apps",
        },
    ).json()
    path = client.post(f"/api/learners/{learner['id']}/learning-path/generate").json()
    topic_id = path["current_topic_id"]
    completed = client.post(f"/api/learners/{learner['id']}/topics/{topic_id}/complete")
    assert completed.status_code == 200
    return learner, path, topic_id


def generate_assessment(client: TestClient, learner_id: int, topic_id: str) -> dict:
    response = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate"
    )
    assert response.status_code == 200
    return response.json()


def answers_for(assessment: dict, selected_option: int) -> list[dict]:
    return [
        {"question_id": question["question_id"], "selected_option": selected_option}
        for question in assessment["questions"]
    ]


def test_assessment_requires_learned_topic_and_hides_answer_keys(client: TestClient):
    learner = client.post(
        "/api/learners",
        json={"name": "Not Ready", "experience_level": "beginner", "goal_key": "rag"},
    ).json()
    path = client.post(f"/api/learners/{learner['id']}/learning-path/generate").json()
    blocked = client.post(
        f"/api/learners/{learner['id']}/topics/{path['current_topic_id']}/assessment/generate"
    )
    assert blocked.status_code == 400

    learner, _, topic_id = prepare_learned_topic(client)
    learner_id = learner["id"]
    generated = generate_assessment(client, learner_id, topic_id)
    assert generated["source"] == "curated_fallback"
    assert all("correct_option" not in question for question in generated["questions"])
    assert all("explanation" not in question for question in generated["questions"])


def test_missing_key_and_invalid_ai_output_use_curated_questions(client: TestClient, monkeypatch):
    learner, _, topic_id = prepare_learned_topic(client)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    missing = generate_assessment(client, learner["id"], topic_id)
    assert missing["source"] == "curated_fallback"

    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    FakeAssessmentProvider.response_content = json.dumps({"questions": []})
    monkeypatch.setattr(assessment_service, "OpenAI", FakeAssessmentProvider)
    invalid = generate_assessment(client, learner["id"], topic_id)
    assert invalid["source"] == "curated_fallback"


def test_mocked_openrouter_assessment_is_validated(client: TestClient, monkeypatch):
    learner, _, topic_id = prepare_learned_topic(client)
    FakeAssessmentProvider.response_content = json.dumps({"questions": QUESTION_BANK[topic_id]})
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(assessment_service, "OpenAI", FakeAssessmentProvider)

    generated = generate_assessment(client, learner["id"], topic_id)

    assert generated["source"] == "openrouter"
    assert len(generated["questions"]) == 3


def test_weak_result_persists_skills_weakness_recommendation_and_remediation(client: TestClient):
    learner, _, topic_id = prepare_learned_topic(client)
    generated = generate_assessment(client, learner["id"], topic_id)
    result = client.post(
        f"/api/learners/{learner['id']}/assessments/{generated['assessment_id']}/submit",
        json={"answers": answers_for(generated, 1)},
    )

    assert result.status_code == 200
    body = result.json()
    assert body["percentage"] == 0
    assert body["weak_concepts"]
    assert body["recommendation"]["action_type"] == "remediate"
    assert topic_id == body["recommendation"]["target_topic_id"]
    assert "simpler" in body["recommendation"]["next_action"]
    with Session(app.state.phase7_test_engine) as database:
        weakness = database.scalar(select(Weakness).where(Weakness.learner_id == learner["id"]))
        progress = database.scalar(
            select(TopicProgress).where(
                TopicProgress.learner_id == learner["id"], TopicProgress.topic_id == topic_id
            )
        )
        recommendation = database.scalar(
            select(Recommendation).where(Recommendation.learner_id == learner["id"])
        )
        assert weakness.status == "open"
        assert progress.status == "remediation"
        assert recommendation.action_type == "remediate"


def test_strong_result_advances_and_updates_path(client: TestClient):
    learner, _, topic_id = prepare_learned_topic(client)
    generated = generate_assessment(client, learner["id"], topic_id)
    result = client.post(
        f"/api/learners/{learner['id']}/assessments/{generated['assessment_id']}/submit",
        json={"answers": answers_for(generated, 0)},
    )

    assert result.status_code == 200
    body = result.json()
    assert body["percentage"] == 100
    assert body["strong_concepts"]
    assert body["recommendation"]["action_type"] == "continue"
    assert body["recommendation"]["target_topic_id"] != topic_id
    with Session(app.state.phase7_test_engine) as database:
        progress = database.scalar(
            select(TopicProgress).where(
                TopicProgress.learner_id == learner["id"], TopicProgress.topic_id == topic_id
            )
        )
        path = database.scalar(
            select(LearningPath).where(LearningPath.learner_id == learner["id"])
        )
        assert progress.status == "completed"
        assert path.path_json[path.current_index]["topic_id"] != topic_id


def test_invalid_answers_duplicate_submission_and_persisted_result(client: TestClient):
    learner, _, topic_id = prepare_learned_topic(client)
    generated = generate_assessment(client, learner["id"], topic_id)
    invalid = client.post(
        f"/api/learners/{learner['id']}/assessments/{generated['assessment_id']}/submit",
        json={"answers": [{"question_id": "not-a-question", "selected_option": 0}]},
    )
    assert invalid.status_code == 422

    result = client.post(
        f"/api/learners/{learner['id']}/assessments/{generated['assessment_id']}/submit",
        json={"answers": answers_for(generated, 0)},
    )
    assert result.status_code == 200
    duplicate = client.post(
        f"/api/learners/{learner['id']}/assessments/{generated['assessment_id']}/submit",
        json={"answers": answers_for(generated, 0)},
    )
    assert duplicate.status_code == 409
    reloaded = client.get(
        f"/api/learners/{learner['id']}/assessments/{generated['assessment_id']}"
    )
    assert reloaded.status_code == 200
    assert reloaded.json()["percentage"] == result.json()["percentage"]
    assert "correct_option" not in reloaded.text


def test_skill_update_uses_historical_weighting(client: TestClient):
    learner, _, topic_id = prepare_learned_topic(client)
    generated = generate_assessment(client, learner["id"], topic_id)
    result = client.post(
        f"/api/learners/{learner['id']}/assessments/{generated['assessment_id']}/submit",
        json={"answers": answers_for(generated, 0)},
    ).json()
    first_score = result["concept_results"][0]["score"]

    with Session(app.state.phase7_test_engine) as database:
        skill = database.scalar(
            select(SkillScore).where(
                SkillScore.learner_id == learner["id"],
                SkillScore.concept == result["concept_results"][0]["concept"],
            )
        )
        assert skill.score == first_score
