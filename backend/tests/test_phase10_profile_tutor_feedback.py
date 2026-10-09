from collections.abc import Generator

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import GeneratedCourse, Learner, LearningPath, Topic, TopicProgress
from app.seed_topics import seed_topics


@pytest.fixture
def phase10_context(tmp_path, monkeypatch) -> Generator[tuple[TestClient, dict], None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase10.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as database:
        seed_topics(database)
    monkeypatch.setattr(settings, "jwt_secret_key", "phase10-test-secret")
    monkeypatch.setattr(settings, "openrouter_api_key", "")

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine) as database:
            yield database

    app.dependency_overrides[get_db] = override_get_db
    app.state.phase10_engine = engine
    client = TestClient(app)
    user = client.post("/api/auth/register", json={"name": "Phase10 User", "email": "phase10@example.com", "password": "password123"})
    headers = {"Authorization": f"Bearer {user.json()['access_token']}"}
    learner = client.post(
        "/api/learners",
        headers=headers,
        json={"name": "Phase10 User", "experience_level": "beginner", "goal_key": "rag"},
    )
    yield client, {"headers": headers, "learner_id": learner.json()["id"]}
    app.dependency_overrides.clear()
    engine.dispose()
    del app.state.phase10_engine


def test_assessment_feedback_and_tutor_response_are_available(phase10_context):
    client, context = phase10_context
    headers = context["headers"]
    learner_id = context["learner_id"]
    current_topic_id = "ai-foundations"
    with Session(app.state.phase10_engine) as database:
        learner = database.get(Learner, learner_id)
        topic = database.get(Topic, current_topic_id)
        database.add(
            LearningPath(
                learner_id=learner_id,
                goal=learner.goal_text,
                path_json=[{"topic_id": topic.id, "title": topic.title}],
                overall_rationale="Focused test path",
                current_index=0,
            )
        )
        database.add(TopicProgress(learner_id=learner_id, topic_id=topic.id, status="completed"))
        database.commit()

    tutor = client.post(
        f"/api/learners/{learner_id}/tutor",
        headers=headers,
        json={"question": "Help me understand the main idea here.", "topic_id": current_topic_id},
    )
    assert tutor.status_code == 200, tutor.text
    tutor_body = tutor.json()
    assert tutor_body["answer"]
    assert tutor_body["topic_title"]
    assert "weak_concepts" in tutor_body
    assert tutor_body["source"] == "deterministic_fallback"
    assert tutor_body["example"]
    assert len(tutor_body["key_points"]) >= 2
    assert tutor_body["module_title"] == "Generative AI Foundations"

    assessment = client.post(f"/api/learners/{learner_id}/topics/{current_topic_id}/assessment/generate", headers=headers)
    assert assessment.status_code == 200
    assessment_body = assessment.json()
    assert assessment_body["questions"]

    answers = [
        {"question_id": question["question_id"], "selected_option": 0}
        for question in assessment_body["questions"]
    ]
    submitted = client.post(
        f"/api/learners/{learner_id}/assessments/{assessment_body['assessment_id']}/submit",
        headers=headers,
        json={"answers": answers},
    )
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()
    assert "question_review" in result
    assert len(result["question_review"]) == len(assessment_body["questions"])
    assert "correct_option" in result["question_review"][0]
    assert "selected_option" in result["question_review"][0]


def test_diagnostic_question_feedback_can_be_reloaded(phase10_context):
    client, context = phase10_context
    headers = context["headers"]
    learner_id = context["learner_id"]
    generated = client.post(f"/api/learners/{learner_id}/diagnostic/generate", headers=headers)
    assert generated.status_code == 200
    assessment = generated.json()

    submitted = client.post(
        f"/api/learners/{learner_id}/diagnostic/{assessment['assessment_id']}/submit",
        headers=headers,
        json={
            "answers": [
                {"question_id": question["id"], "selected_option": 0}
                for question in assessment["questions"]
            ]
        },
    )
    assert submitted.status_code == 200, submitted.text
    submitted_body = submitted.json()
    assert len(submitted_body["question_review"]) == len(assessment["questions"])
    assert submitted_body["ai_interpretation"]["source"] == "deterministic_fallback"
    assert str(submitted_body["overall_percentage"]) in submitted_body["ai_interpretation"]["summary"]
    assert submitted_body["concept_insights"]
    assert all(insight["improvement_plan"] for insight in submitted_body["concept_insights"])
    summary = client.get(f"/api/learners/{learner_id}/summary", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["latest_assessment"]["topic_id"] is None
    expected_percentage = round(
        sum(item["is_correct"] for item in submitted.json()["question_review"])
        / len(assessment["questions"])
        * 100,
        1,
    )
    assert summary.json()["latest_assessment"]["percentage"] == expected_percentage

    reloaded = client.get(
        f"/api/learners/{learner_id}/diagnostic/{assessment['assessment_id']}",
        headers=headers,
    )
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["question_review"] == submitted.json()["question_review"]
    assert reloaded.json()["ai_interpretation"] == submitted.json()["ai_interpretation"]
    assert reloaded.json()["concept_insights"] == submitted_body["concept_insights"]


def test_tutor_rejects_another_learners_generated_topic(phase10_context):
    client, context = phase10_context
    headers_a = context["headers"]
    learner_a_id = context["learner_id"]
    user_b = client.post(
        "/api/auth/register",
        json={"name": "User B", "email": "phase10-user-b@example.com", "password": "password123"},
    )
    assert user_b.status_code == 201
    headers_b = {"Authorization": f"Bearer {user_b.json()['access_token']}"}
    learner_b = client.post(
        "/api/learners",
        headers=headers_b,
        json={"name": "User B", "experience_level": "beginner", "goal_key": "ai_agents"},
    )
    assert learner_b.status_code == 201
    assert client.post("/api/curriculum/generate", headers=headers_b).status_code == 200
    curriculum_b = client.get("/api/curriculum/current", headers=headers_b)
    assert curriculum_b.status_code == 200
    foreign_topic_id = curriculum_b.json()["topics"][0]["topic_id"]

    response = client.post(
        f"/api/learners/{learner_a_id}/tutor",
        headers=headers_a,
        json={"question": "Explain this topic to me.", "topic_id": foreign_topic_id},
    )
    assert response.status_code == 404


def test_tutor_does_not_offer_module_for_unmatched_course_request(phase10_context):
    client, context = phase10_context
    learner_id = context["learner_id"]
    with Session(app.state.phase10_engine) as database:
        learner = database.get(Learner, learner_id)
        topic = database.get(Topic, "ai-foundations")
        course = GeneratedCourse(
            user_id=learner.user_id,
            learner_id=learner_id,
            title="Generative AI Fundamentals",
            description="A validated test course.",
            goal=learner.goal_text,
            level=learner.experience_level,
            estimated_duration="120 minutes",
            generation_source="deterministic_fallback",
        )
        database.add(course)
        database.add(
            LearningPath(
                learner_id=learner_id,
                goal=learner.goal_text,
                path_json=[{"topic_id": topic.id, "title": topic.title}],
                overall_rationale="Test path",
                current_index=0,
            )
        )
        database.commit()

    response = client.post(
        f"/api/learners/{learner_id}/tutor",
        headers=context["headers"],
        json={
            "question": "Show me a course module about mobile game monetization.",
            "topic_id": "ai-foundations",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["module_title"] is None
    assert "No matching module" in response.json()["course_connection"]
