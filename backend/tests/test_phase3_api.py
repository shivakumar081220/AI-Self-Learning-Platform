from collections.abc import Generator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base, get_db
from app.main import app
from app.models import Assessment, Learner, SkillScore
from app.seed_topics import seed_topics
from app.services import diagnostic_service


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase3-api.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as database:
        seed_topics(database)

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine) as database:
            yield database

    app.dependency_overrides[get_db] = override_get_db
    app.state.phase3_engine = engine
    yield TestClient(app)
    app.dependency_overrides.clear()
    del app.state.phase3_engine
    engine.dispose()


def test_profile_creation_and_goal_selection(client: TestClient):
    response = client.post(
        "/api/learners",
        json={
            "name": "Maya",
            "experience_level": "beginner",
            "goal_key": "rag",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["track"] == "generative_ai"
    assert body["goal_text"] == "Build a RAG application"


def test_diagnostic_generation_hides_internal_metadata(client: TestClient):
    learner = client.post(
        "/api/learners",
        json={
            "name": "Noah",
            "experience_level": "intermediate",
            "goal_key": "llm_apps",
        },
    ).json()

    response = client.post(f"/api/learners/{learner['id']}/diagnostic/generate")

    assert response.status_code == 200
    body = response.json()
    assert body["generated_by"] == "curated_fallback"
    assert len(body["questions"]) == 8
    assert all("correct_option" not in question for question in body["questions"])
    assert all("concept" in question and "difficulty" in question for question in body["questions"])
    assert all("correct_option" not in question and "explanation" not in question for question in body["questions"])


def test_generated_course_fallback_uses_objectives_and_varies_question_design(monkeypatch):
    topics = [
        SimpleNamespace(
            id="topic-retrieval",
            title="Retrieval Foundations",
            concept_tags=["retrieval", "ranking"],
            learning_objectives_json=[
                "Select relevant source passages",
                "Rank passages against a user question",
            ],
        ),
        SimpleNamespace(
            id="topic-embeddings",
            title="Embedding Search",
            concept_tags=["embeddings"],
            learning_objectives_json=["Compare semantic vectors for similarity"],
        ),
    ]
    course = SimpleNamespace(id=42)
    monkeypatch.setattr(
        diagnostic_service,
        "_diagnostic_topic_catalog",
        lambda database, learner_id, track_id, owner_user_id: topics,
    )
    monkeypatch.setattr(
        diagnostic_service,
        "_current_course",
        lambda database, learner_id: course,
    )

    question_set = diagnostic_service._fallback_questions(
        database=None,
        experience_level="beginner",
        track_id="ai_agents",
        learner_id=7,
    )
    questions = question_set.questions

    assert len(questions) == 8
    assert len({question.id for question in questions}) == 8
    assert {question.concept for question in questions} == {"retrieval", "ranking", "embeddings"}
    assert {question.difficulty for question in questions} == {
        "beginner",
        "intermediate",
        "advanced",
    }
    assert {question.correct_option for question in questions} == {0, 1, 2, 3}
    assert any(
        "Select relevant source passages" in question.options[question.correct_option]
        for question in questions
    )
    assert all(len(set(question.options)) == len(question.options) for question in questions)


def test_diagnostic_submission_persists_deterministic_skill_scores(client: TestClient):
    learner = client.post(
        "/api/learners",
        json={
            "name": "Iris",
            "experience_level": "advanced",
            "goal_key": "ai_agents",
        },
    ).json()
    generated = client.post(
        f"/api/learners/{learner['id']}/diagnostic/generate"
    ).json()
    with Session(app.state.phase3_engine) as database:
        assessment = database.get(Assessment, generated["assessment_id"])
        answers = [
            {
                "question_id": question["id"],
                "selected_option": (
                    question["correct_option"]
                    if index % 2 == 0
                    else (question["correct_option"] + 1) % len(question["options"])
                ),
            }
            for index, question in enumerate(assessment.questions_json)
        ]

    response = client.post(
        f"/api/learners/{learner['id']}/diagnostic/{generated['assessment_id']}/submit",
        json={"answers": answers},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answered_questions"] == 8
    assert len(body["skills"]) == 8
    assert body["weak_areas"]
    assert body["strong_areas"]
    assert len(body["concept_insights"]) == 8
    assert all(insight["total_questions"] == 1 for insight in body["concept_insights"])
    assert all(insight["evidence_statement"].startswith("Evidence:") for insight in body["concept_insights"])
    assert all(insight["improvement_plan"] for insight in body["concept_insights"])

    skills = client.get(f"/api/learners/{learner['id']}/skills")
    assert skills.status_code == 200
    assert len(skills.json()["skills"]) == 8


def test_invalid_diagnostic_submission_is_rejected(client: TestClient):
    learner = client.post(
        "/api/learners",
        json={
            "name": "Leo",
            "experience_level": "beginner",
            "custom_goal": "Understand how LLMs work",
        },
    ).json()
    generated = client.post(
        f"/api/learners/{learner['id']}/diagnostic/generate"
    ).json()
    first_question = generated["questions"][0]

    response = client.post(
        f"/api/learners/{learner['id']}/diagnostic/{generated['assessment_id']}/submit",
        json={
            "answers": [
                {
                    "question_id": first_question["id"],
                    "selected_option": 99,
                }
            ]
        },
    )

    assert response.status_code == 422
    assert "every diagnostic question" in response.json()["detail"]


def test_ai_failure_uses_curated_fallback(monkeypatch, client: TestClient):
    learner = client.post(
        "/api/learners",
        json={
            "name": "Sam",
            "experience_level": "intermediate",
            "goal_key": "prompt_engineering",
        },
    ).json()

    monkeypatch.setattr(diagnostic_service.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(
        diagnostic_service,
        "_openrouter_questions",
        lambda learner, database: (_ for _ in ()).throw(
            diagnostic_service.AIProviderError("timeout")
        ),
    )

    response = client.post(f"/api/learners/{learner['id']}/diagnostic/generate")

    assert response.status_code == 200
    assert response.json()["generated_by"] == "curated_fallback"
