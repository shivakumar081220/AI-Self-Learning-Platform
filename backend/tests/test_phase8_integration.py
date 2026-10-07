from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.seed_topics import seed_topics
from app.services.diagnostic_service import CURATED_DIAGNOSTIC_QUESTIONS


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


def test_diagnostic_scores_follow_actual_answers(client: TestClient):
    learner_response = client.post(
        "/api/learners",
        json={
            "name": "Answer Sensitive Learner",
            "experience_level": "beginner",
            "goal_key": "rag",
        },
    )
    assert learner_response.status_code == 201
    learner_id = learner_response.json()["id"]

    answer_key = {question["id"]: question["correct_option"] for question in CURATED_DIAGNOSTIC_QUESTIONS}

    mostly_correct_diagram = client.post(f"/api/learners/{learner_id}/diagnostic/generate").json()
    mostly_correct_answers = [
        {
            "question_id": question["id"],
            "selected_option": answer_key[question["id"]],
        }
        for question in mostly_correct_diagram["questions"]
    ]
    mostly_correct_result = client.post(
        f"/api/learners/{learner_id}/diagnostic/{mostly_correct_diagram['assessment_id']}/submit",
        json={"answers": mostly_correct_answers},
    )
    assert mostly_correct_result.status_code == 200
    mostly_correct_body = mostly_correct_result.json()
    assert mostly_correct_body["overall_percentage"] == 100

    mostly_wrong_diagram = client.post(f"/api/learners/{learner_id}/diagnostic/generate").json()
    mostly_wrong_answers = []
    for question in mostly_wrong_diagram["questions"]:
        correct = answer_key[question["id"]]
        wrong = (correct + 1) % len(question["options"])
        if wrong == correct:
            wrong = (wrong + 1) % len(question["options"])
        mostly_wrong_answers.append({"question_id": question["id"], "selected_option": wrong})
    mostly_wrong_result = client.post(
        f"/api/learners/{learner_id}/diagnostic/{mostly_wrong_diagram['assessment_id']}/submit",
        json={"answers": mostly_wrong_answers},
    )
    assert mostly_wrong_result.status_code == 200
    mostly_wrong_body = mostly_wrong_result.json()
    assert mostly_wrong_body["overall_percentage"] == 0
    assert mostly_wrong_body["overall_percentage"] != mostly_correct_body["overall_percentage"]

    mixed_diagram = client.post(f"/api/learners/{learner_id}/diagnostic/generate").json()
    mixed_answers = []
    for index, question in enumerate(mixed_diagram["questions"]):
        correct = answer_key[question["id"]]
        alternate = (correct + 1) % len(question["options"])
        if alternate == correct:
            alternate = (alternate + 1) % len(question["options"])
        mixed_answers.append(
            {"question_id": question["id"], "selected_option": correct if index % 2 == 0 else alternate}
        )
    mixed_result = client.post(
        f"/api/learners/{learner_id}/diagnostic/{mixed_diagram['assessment_id']}/submit",
        json={"answers": mixed_answers},
    )
    assert mixed_result.status_code == 200
    mixed_body = mixed_result.json()
    assert 0 < mixed_body["overall_percentage"] < 100

    concept_levels = {skill["concept"]: skill["percentage"] for skill in mixed_body["skills"]}
    assert concept_levels
    assert any(value == 0 for value in concept_levels.values())
    assert any(value == 100 for value in concept_levels.values())


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
    assert len(result_body["question_review"]) == len(assessment_body["questions"])
    assert all("correct_option" in question for question in result_body["question_review"])

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
