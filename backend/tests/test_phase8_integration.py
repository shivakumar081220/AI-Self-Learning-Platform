from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.seed_topics import seed_topics


@pytest.fixture
def client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase8-e2e.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as database:
        seed_topics(database)
    monkeypatch.setattr(settings, "openrouter_api_key", "")

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine) as database:
            yield database

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_fresh_learner_completes_full_adaptive_journey(client: TestClient):
    learner_response = client.post(
        "/api/learners",
        json={
            "name": "End To End Learner",
            "experience_level": "beginner",
            "goal_key": "rag",
        },
    )
    assert learner_response.status_code == 201
    learner_id = learner_response.json()["id"]

    diagnostic = client.post(f"/api/learners/{learner_id}/diagnostic/generate").json()
    assert diagnostic["generated_by"] == "curated_fallback"
    diagnostic_result = client.post(
        f"/api/learners/{learner_id}/diagnostic/{diagnostic['assessment_id']}/submit",
        json={
            "answers": [
                {"question_id": question["id"], "selected_option": 0}
                for question in diagnostic["questions"]
            ]
        },
    )
    assert diagnostic_result.status_code == 200

    path = client.post(f"/api/learners/{learner_id}/learning-path/generate")
    assert path.status_code == 200
    current = client.get(f"/api/learners/{learner_id}/learning-path/current").json()
    topic_id = current["topic_id"]

    content = client.get(f"/api/learners/{learner_id}/topics/{topic_id}/content")
    assert content.status_code == 200
    assert content.json()["content"]["topic_id"] == topic_id

    completed = client.post(f"/api/learners/{learner_id}/topics/{topic_id}/complete")
    assert completed.status_code == 200
    assessment = client.post(
        f"/api/learners/{learner_id}/topics/{topic_id}/assessment/generate"
    )
    assert assessment.status_code == 200
    assessment_body = assessment.json()

    result = client.post(
        f"/api/learners/{learner_id}/assessments/{assessment_body['assessment_id']}/submit",
        json={
            "answers": [
                {"question_id": question["question_id"], "selected_option": 1}
                for question in assessment_body["questions"]
            ]
        },
    )
    assert result.status_code == 200
    result_body = result.json()
    assert result_body["recommendation"]["action_type"] == "remediate"
    assert result_body["weak_concepts"]
    assert "correct_option" not in result.text

    updated_path = client.get(f"/api/learners/{learner_id}/learning-path").json()
    assert updated_path["current_topic_id"] == topic_id
    summary = client.get(f"/api/learners/{learner_id}/summary")
    assert summary.status_code == 200
    assert summary.json()["latest_assessment"]["percentage"] == 0
    assert summary.json()["recommendation"]["action_type"] == "remediate"

    persisted_result = client.get(
        f"/api/learners/{learner_id}/assessments/{assessment_body['assessment_id']}"
    )
    assert persisted_result.status_code == 200
    assert persisted_result.json()["percentage"] == result_body["percentage"]
