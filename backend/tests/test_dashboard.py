from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import (
    Assessment,
    Recommendation,
    SkillScore,
    Topic,
    TopicProgress,
    TutorConversation,
    TutorMessage,
)
from app.seed_topics import seed_topics


@pytest.fixture
def client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'dashboard.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as database:
        seed_topics(database)
    monkeypatch.setattr(settings, "jwt_secret_key", "dashboard-test-secret")
    monkeypatch.setattr(settings, "openrouter_api_key", "")

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine) as database:
            yield database

    app.dependency_overrides[get_db] = override_get_db
    app.state.dashboard_engine = engine
    yield TestClient(app)
    app.dependency_overrides.clear()
    del app.state.dashboard_engine
    engine.dispose()


def register(client: TestClient, name: str, email: str) -> tuple[dict, dict]:
    response = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "password123"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["user"], {"Authorization": f"Bearer {body['access_token']}"}


def create_course(client: TestClient, headers: dict, name: str, goal: str = "rag") -> dict:
    response = client.post(
        "/api/learners",
        headers=headers,
        json={"name": name, "experience_level": "intermediate", "goal_key": goal},
    )
    assert response.status_code == 201, response.text
    generated = client.post("/api/curriculum/generate", headers=headers)
    assert generated.status_code == 200, generated.text
    return response.json()


def test_dash_001_002_016_dashboard_requires_auth_and_rejects_cross_user_access(
    client: TestClient,
):
    _, headers_a = register(client, "Learner A", "dashboard-a@example.com")
    _, headers_b = register(client, "Learner B", "dashboard-b@example.com")
    learner_a = create_course(client, headers_a, "Learner A")
    learner_b = create_course(client, headers_b, "Learner B", "ai_agents")

    assert client.get(f"/api/learners/{learner_a['id']}/dashboard").status_code == 401
    assert (
        client.get(f"/api/learners/{learner_b['id']}/dashboard", headers=headers_a).status_code
        == 403
    )
    assert (
        client.get(f"/api/learners/{learner_a['id']}/dashboard", headers=headers_b).status_code
        == 403
    )
    own = client.get(f"/api/learners/{learner_a['id']}/dashboard", headers=headers_a)
    assert own.status_code == 200
    assert own.json()["learner_id"] == learner_a["id"]


def test_dash_003_012_empty_learner_has_zero_progress_and_no_fabricated_activity(
    client: TestClient,
):
    _, headers = register(client, "New Learner", "dashboard-new@example.com")
    learner = create_course(client, headers, "New Learner")

    response = client.get(f"/api/learners/{learner['id']}/dashboard", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["completed_topics"] == 0
    assert body["progress_percentage"] == 0
    assert body["total_topics"] > 0
    assert body["completed_topic_items"] == []
    assert body["current_topic"] is None
    assert body["strong_concepts"] == []
    assert body["weak_concepts"] == []
    assert body["assessment_performance"] == {
        "average_percentage": None,
        "latest_percentage": None,
        "completed_count": 0,
        "recent_scores": [],
    }
    assert body["recent_activity"] == []
    assert body["recommendation"] is None
    assert body["path_completed"] is False


def test_dash_013_completed_path_reports_full_progress_and_no_current_topic(
    client: TestClient,
):
    _, headers = register(client, "Completed Learner", "dashboard-complete@example.com")
    learner = create_course(client, headers, "Completed Learner")
    curriculum = client.get("/api/curriculum/current", headers=headers).json()
    path = client.get(
        f"/api/learners/{learner['id']}/learning-path?course_id={curriculum['course_id']}",
        headers=headers,
    ).json()

    with Session(app.state.dashboard_engine) as database:
        database.add_all(
            [
                TopicProgress(
                    learner_id=learner["id"],
                    topic_id=topic["topic_id"],
                    status="completed",
                    lesson_completed=True,
                    mastery_score=1.0,
                    attempt_count=1,
                    last_activity_at=datetime.now(timezone.utc).replace(tzinfo=None)
                    - timedelta(minutes=index),
                )
                for index, topic in enumerate(path["topics"])
            ]
        )
        database.commit()

    response = client.get(f"/api/learners/{learner['id']}/dashboard", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["completed_topics"] == body["total_topics"] == len(path["topics"])
    assert body["progress_percentage"] == 100
    assert body["current_topic"] is None
    assert body["recommendation"] is None
    assert body["path_completed"] is True


def test_dash_004_to_015_and_017_018_dashboard_uses_actual_adaptive_learner_state(
    client: TestClient,
):
    _, headers = register(client, "Adaptive Learner", "dashboard-state@example.com")
    learner = create_course(client, headers, "Adaptive Learner")
    curriculum = client.get("/api/curriculum/current", headers=headers).json()
    path_response = client.get(
        f"/api/learners/{learner['id']}/learning-path?course_id={curriculum['course_id']}",
        headers=headers,
    )
    assert path_response.status_code == 200, path_response.text
    topics = path_response.json()["topics"]
    completed_topic, current_topic = topics[:2]
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with Session(app.state.dashboard_engine) as database:
        completed_topic_row = database.get(Topic, completed_topic["topic_id"])
        current_topic_row = database.get(Topic, current_topic["topic_id"])
        assert completed_topic_row is not None and current_topic_row is not None
        completed_topic_row.concept_tags = ["retrieval"]
        current_topic_row.concept_tags = ["attention"]
        database.add_all(
            [
                TopicProgress(
                    learner_id=learner["id"],
                    topic_id=completed_topic["topic_id"],
                    status="completed",
                    lesson_completed=True,
                    mastery_score=0.9,
                    attempt_count=1,
                    last_activity_at=now - timedelta(hours=4),
                ),
                TopicProgress(
                    learner_id=learner["id"],
                    topic_id=current_topic["topic_id"],
                    status="remediation",
                    lesson_completed=True,
                    mastery_score=0.3,
                    attempt_count=2,
                    last_activity_at=now - timedelta(hours=1),
                ),
                SkillScore(
                    learner_id=learner["id"],
                    concept="retrieval",
                    score=0.92,
                    evidence_count=4,
                    confidence=0.9,
                    source="assessment",
                ),
                SkillScore(
                    learner_id=learner["id"],
                    concept="attention",
                    score=0.35,
                    evidence_count=2,
                    confidence=0.7,
                    source="assessment",
                ),
                Assessment(
                    learner_id=learner["id"],
                    topic_id=completed_topic["topic_id"],
                    assessment_type="topic",
                    status="completed",
                    score=0.8,
                    percentage=80,
                    completed_at=now - timedelta(days=1),
                ),
                Assessment(
                    learner_id=learner["id"],
                    topic_id=current_topic["topic_id"],
                    assessment_type="topic",
                    status="completed",
                    score=0.6,
                    percentage=60,
                    completed_at=now - timedelta(minutes=30),
                ),
                Recommendation(
                    learner_id=learner["id"],
                    action_type="remediate",
                    topic_id=current_topic["topic_id"],
                    reason="Recent assessment results show attention needs practice.",
                ),
            ]
        )
        conversation = TutorConversation(
            learner_id=learner["id"],
            topic_id=current_topic["topic_id"],
            title="Attention question",
        )
        database.add(conversation)
        database.flush()
        database.add(
            TutorMessage(
                conversation_id=conversation.id,
                role="user",
                content="Can you explain attention again?",
                created_at=now,
            )
        )
        database.commit()

    response = client.get(f"/api/learners/{learner['id']}/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["course_id"] == curriculum["course_id"]
    assert body["course_title"] == curriculum["course_title"]
    assert body["progress_percentage"] == round(1 / len(topics) * 100)
    assert body["completed_topics"] == 1
    assert body["total_topics"] == len(topics)
    assert body["completed_topic_items"][0]["topic_id"] == completed_topic["topic_id"]
    assert body["completed_topic_items"][0]["status"] == "completed"
    assert body["current_topic"]["topic_id"] == current_topic["topic_id"]
    assert body["current_topic"]["status"] == "remediation"
    assert body["strong_concepts"][0]["concept"] == "retrieval"
    assert body["strong_concepts"][0]["percentage"] == 92
    assert body["weak_concepts"][0]["concept"] == "attention"
    assert body["weak_concepts"][0]["percentage"] == 35
    assert body["assessment_performance"]["average_percentage"] == 70
    assert body["assessment_performance"]["latest_percentage"] == 60
    assert body["assessment_performance"]["completed_count"] == 2
    assert [item["percentage"] for item in body["assessment_performance"]["recent_scores"]] == [80, 60]
    assert body["recommendation"]["action_type"] == "remediate"
    assert body["recommendation"]["target_topic_id"] == current_topic["topic_id"]
    assert any(item["activity_type"] == "topic_completed" for item in body["recent_activity"])
    assert any(item["activity_type"] == "assessment_completed" for item in body["recent_activity"])
    tutor_activity = next(
        item for item in body["recent_activity"] if item["activity_type"] == "tutor_message"
    )
    assert tutor_activity["description"] == "Can you explain attention again?"


def test_dashboard_course_selection_returns_course_scoped_progress_and_rejects_foreign_course(
    client: TestClient,
):
    _, learner_headers = register(client, "Multi-course Learner", "dashboard-multi@example.com")
    learner = create_course(client, learner_headers, "Multi-course Learner")
    first_course = client.get("/api/curriculum/current", headers=learner_headers).json()
    first_path_response = client.get(
        f"/api/learners/{learner['id']}/learning-path?course_id={first_course['course_id']}",
        headers=learner_headers,
    )
    assert first_path_response.status_code == 200, first_path_response.text

    update = client.put(
        "/api/learners/me",
        headers=learner_headers,
        json={
            "name": "Multi-course Learner",
            "experience_level": "intermediate",
            "goal_key": "ai_agents",
        },
    )
    assert update.status_code == 200, update.text
    generated = client.post("/api/curriculum/generate", headers=learner_headers)
    assert generated.status_code == 200, generated.text
    second_course = generated.json()
    assert second_course["course_id"] != first_course["course_id"]
    second_path_response = client.get(
        f"/api/learners/{learner['id']}/learning-path?course_id={second_course['course_id']}",
        headers=learner_headers,
    )
    assert second_path_response.status_code == 200, second_path_response.text

    first_topics = first_path_response.json()["topics"]
    second_topics = second_path_response.json()["topics"]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with Session(app.state.dashboard_engine) as database:
        database.add_all(
            [
                TopicProgress(
                    learner_id=learner["id"],
                    topic_id=first_topics[0]["topic_id"],
                    status="completed",
                    lesson_completed=True,
                    mastery_score=0.9,
                    attempt_count=1,
                    last_activity_at=now,
                ),
                *[
                    TopicProgress(
                        learner_id=learner["id"],
                        topic_id=topic["topic_id"],
                        status="completed",
                        lesson_completed=True,
                        mastery_score=0.9,
                        attempt_count=1,
                        last_activity_at=now,
                    )
                    for topic in second_topics[:2]
                ],
            ]
        )
        first_topic_row = database.get(Topic, first_topics[0]["topic_id"])
        second_topic_row = database.get(Topic, second_topics[0]["topic_id"])
        assert first_topic_row is not None and second_topic_row is not None
        first_topic_row.concept_tags = ["first_course_skill"]
        second_topic_row.concept_tags = ["second_course_skill"]
        database.add_all(
            [
                SkillScore(
                    learner_id=learner["id"],
                    concept="first_course_skill",
                    score=0.9,
                    evidence_count=2,
                    confidence=1.0,
                    source="assessment",
                ),
                SkillScore(
                    learner_id=learner["id"],
                    concept="second_course_skill",
                    score=0.1,
                    evidence_count=2,
                    confidence=1.0,
                    source="assessment",
                ),
                SkillScore(
                    learner_id=learner["id"],
                    concept="unrelated_course_skill",
                    score=0.0,
                    evidence_count=2,
                    confidence=1.0,
                    source="assessment",
                ),
            ]
        )
        database.commit()

    first_dashboard = client.get(
        f"/api/learners/{learner['id']}/dashboard?course_id={first_course['course_id']}",
        headers=learner_headers,
    )
    second_dashboard = client.get(
        f"/api/learners/{learner['id']}/dashboard?course_id={second_course['course_id']}",
        headers=learner_headers,
    )
    assert first_dashboard.status_code == second_dashboard.status_code == 200
    first_summary = first_dashboard.json()
    second_summary = second_dashboard.json()
    assert first_summary["course_id"] == first_course["course_id"]
    assert first_summary["completed_topics"] == 1
    assert first_summary["total_topics"] == len(first_topics)
    assert first_summary["completed_topic_items"][0]["course_id"] == first_course["course_id"]
    assert second_summary["course_id"] == second_course["course_id"]
    assert second_summary["completed_topics"] == 2
    assert second_summary["total_topics"] == len(second_topics)
    assert all(
        topic["course_id"] == second_course["course_id"]
        for topic in second_summary["completed_topic_items"]
    )
    assert [skill["concept"] for skill in first_summary["strong_concepts"]] == [
        "first_course_skill"
    ]
    assert [skill["concept"] for skill in first_summary["weak_concepts"]] == []
    assert [skill["concept"] for skill in second_summary["weak_concepts"]] == [
        "second_course_skill"
    ]
    assert all(
        skill["concept"] != "unrelated_course_skill"
        for summary in (first_summary, second_summary)
        for skill in summary["strong_concepts"] + summary["weak_concepts"]
    )

    with Session(app.state.dashboard_engine) as database:
        skill = database.scalar(
            select(SkillScore).where(
                SkillScore.learner_id == learner["id"],
                SkillScore.concept == "first_course_skill",
            )
        )
        assert skill is not None
        skill.score = 0.2
        database.commit()
    refreshed_summary = client.get(
        f"/api/learners/{learner['id']}/dashboard?course_id={first_course['course_id']}",
        headers=learner_headers,
    ).json()
    assert [skill["concept"] for skill in refreshed_summary["weak_concepts"]] == [
        "first_course_skill"
    ]

    _, other_headers = register(client, "Other Learner", "dashboard-other@example.com")
    other_learner = create_course(client, other_headers, "Other Learner")
    other_course_id = client.get("/api/curriculum/current", headers=other_headers).json()["course_id"]
    assert other_learner["id"] != learner["id"]
    foreign_course = client.get(
        f"/api/learners/{learner['id']}/dashboard?course_id={other_course_id}",
        headers=learner_headers,
    )
    assert foreign_course.status_code == 404
