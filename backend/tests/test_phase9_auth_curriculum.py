from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import GeneratedCourse, Learner, LearningPath, Topic, TopicProgress
from app.seed_topics import seed_topics
from app.services import content_service, curriculum_service
from app.topic_titles import display_topic_title
from app.track_catalog import AI_TRACKS


@pytest.fixture
def client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase9.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as database:
        seed_topics(database)
    monkeypatch.setattr(settings, "jwt_secret_key", "phase9-test-secret")
    monkeypatch.setattr(settings, "openrouter_api_key", "")

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine) as database:
            yield database

    app.dependency_overrides[get_db] = override_get_db
    app.state.phase9_engine = engine
    yield TestClient(app)
    app.dependency_overrides.clear()
    del app.state.phase9_engine


def register(client: TestClient, name: str, email: str, password: str = "password123") -> tuple[dict, dict]:
    response = client.post("/api/auth/register", json={"name": name, "email": email, "password": password})
    assert response.status_code == 201
    body = response.json()
    return body["user"], {"Authorization": f"Bearer {body['access_token']}"}


def onboard(client: TestClient, headers: dict, goal_key: str, name: str) -> dict:
    response = client.post(
        "/api/learners",
        headers=headers,
        json={"name": name, "experience_level": "beginner", "goal_key": goal_key},
    )
    assert response.status_code == 201
    curriculum = client.post("/api/curriculum/generate", headers=headers)
    assert curriculum.status_code == 200
    return response.json()


def test_auth_registration_login_and_protected_access(client: TestClient):
    user, headers = register(client, "Asha", "asha@example.com")
    assert user["email"] == "asha@example.com"
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    failed = client.post("/api/auth/login", json={"email": "asha@example.com", "password": "wrongpass"})
    assert failed.status_code == 401
    duplicate = client.post("/api/auth/register", json={"name": "Asha", "email": "asha@example.com", "password": "password123"})
    assert duplicate.status_code == 409
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_two_users_receive_different_persisted_curricula_and_isolated_data(client: TestClient):
    user_a, headers_a = register(client, "Rag Learner", "rag@example.com")
    user_b, headers_b = register(client, "Agent Learner", "agent@example.com")
    learner_a = onboard(client, headers_a, "rag", "Rag Learner")
    learner_b = onboard(client, headers_b, "ai_agents", "Agent Learner")

    course_a = client.get("/api/curriculum/current", headers=headers_a).json()
    course_b = client.get("/api/curriculum/current", headers=headers_b).json()
    assert course_a["course_id"] != course_b["course_id"]
    assert course_a["course_title"] != course_b["course_title"]
    assert course_a["learning_objectives"] and course_b["learning_objectives"]
    assert all(topic["learning_objectives"] for topic in course_a["topics"])
    assert all(topic["estimated_minutes"] for topic in course_a["topics"])
    assert all("prerequisites" in topic for topic in course_a["topics"])
    assert client.get(f"/api/learners/{learner_b['id']}/summary", headers=headers_a).status_code == 403
    assert client.get(f"/api/learners/{learner_a['id']}/summary", headers=headers_b).status_code == 403
    assert client.get(f"/api/learners/{learner_b['id']}", headers=headers_a).status_code == 403
    assert client.get(f"/api/learners/{learner_a['id']}/skills", headers=headers_b).status_code == 403
    assert client.get(f"/api/learners/{learner_b['id']}/learning-path", headers=headers_a).status_code == 403
    assert client.get(f"/api/learners/{learner_a['id']}/learning-path/current", headers=headers_b).status_code == 403
    assert (
        client.post(f"/api/learners/{learner_b['id']}/diagnostic/generate", headers=headers_a).status_code
        == 403
    )
    assert client.get("/api/curriculum/current", headers=headers_a).json()["course_id"] == course_a["course_id"]
    assert client.get("/api/curriculum/current", headers=headers_b).json()["course_id"] == course_b["course_id"]


def test_generated_curriculum_is_persisted_and_path_uses_generated_topics(client: TestClient):
    _, headers = register(client, "Persisted", "persisted@example.com")
    learner = onboard(client, headers, "rag", "Persisted")
    first = client.post("/api/curriculum/generate", headers=headers).json()
    second = client.post("/api/curriculum/generate", headers=headers).json()
    assert first["course_id"] == second["course_id"]
    assert first["source"] == "persisted"
    assert first["generation_source"] == "deterministic_fallback"
    assert second["source"] == "persisted"
    assert second["generation_source"] == "deterministic_fallback"

    path = client.post(f"/api/learners/{learner['id']}/learning-path/generate", headers=headers)
    assert path.status_code == 200
    body = path.json()
    assert body["topics"]
    assert all(item["topic_id"].startswith("generated-") for item in body["topics"])
    assert all("·" not in item["title"] for item in body["topics"])
    current = client.get(
        f"/api/learners/{learner['id']}/learning-path/current", headers=headers
    ).json()
    assert current["course_title"] == first["course_title"]
    assert current["title"] == next(
        item["title"] for item in first["topics"] if item["topic_id"] == current["topic_id"]
    )


def test_legacy_generated_title_marker_is_hidden_from_course_and_path_responses(
    client: TestClient,
):
    _, headers = register(client, "Legacy Title", "legacy-title@example.com")
    learner = onboard(client, headers, "rag", "Legacy Title")
    curriculum = client.get("/api/curriculum/current", headers=headers).json()
    path = client.post(
        f"/api/learners/{learner['id']}/learning-path/generate", headers=headers
    ).json()
    current_topic_id = path["current_topic_id"]

    with Session(app.state.phase9_engine) as database:
        topic = database.get(Topic, current_topic_id)
        topic.title = f"{display_topic_title(topic.title)} · {curriculum['course_id']}-1"
        expected_title = display_topic_title(topic.title)
        saved_path = database.scalar(
            select(LearningPath).where(LearningPath.learner_id == learner["id"])
        )
        saved_path.path_json = [
            {**item, "title": topic.title if item["topic_id"] == current_topic_id else item["title"]}
            for item in saved_path.path_json
        ]
        database.commit()

    current = client.get(
        f"/api/learners/{learner['id']}/learning-path/current", headers=headers
    ).json()
    refreshed_curriculum = client.get("/api/curriculum/current", headers=headers).json()
    refreshed_path = client.get(
        f"/api/learners/{learner['id']}/learning-path", headers=headers
    ).json()
    summary = client.get(f"/api/learners/{learner['id']}/summary", headers=headers).json()
    content = client.get(
        f"/api/learners/{learner['id']}/topics/{current_topic_id}/content",
        headers=headers,
    ).json()

    assert current["title"] == expected_title
    assert current["course_title"] == curriculum["course_title"]
    assert content["content"]["topic_title"] == expected_title
    assert all(
        display_topic_title(item["title"]) == item["title"]
        for item in refreshed_curriculum["topics"]
    )
    assert all(
        display_topic_title(item["title"]) == item["title"]
        for item in refreshed_path["topics"]
    )
    assert summary["current_topic_title"] == expected_title


def test_curriculum_is_regenerated_when_experience_level_changes(client: TestClient):
    _, headers = register(client, "Level Change", "level-change@example.com")
    initial_learner = client.post(
        "/api/learners",
        headers=headers,
        json={
            "name": "Level Change",
            "experience_level": "beginner",
            "goal_key": "llm_apps",
            "target_outcome": "Build a validated LLM assistant",
        },
    )
    assert initial_learner.status_code == 201
    assert client.post("/api/curriculum/generate", headers=headers).status_code == 200
    updated = client.post(
        "/api/learners",
        headers=headers,
        json={
            "name": "Level Change",
            "experience_level": "intermediate",
            "goal_key": "llm_apps",
            "target_outcome": "Build a validated LLM assistant",
        },
    )
    assert updated.status_code == 201

    curriculum = client.post("/api/curriculum/generate", headers=headers)

    assert curriculum.status_code == 200
    assert curriculum.json()["level"] == "intermediate"
    assert curriculum.json()["generation_source"] == "deterministic_fallback"
    assert len(curriculum.json()["courses"]) == 2
    assert {course["level"] for course in curriculum.json()["courses"]} == {
        "beginner",
        "intermediate",
    }


def test_each_enrolled_course_keeps_its_own_learning_path_and_progress(client: TestClient):
    _, headers = register(client, "Multi Course", "multi-course@example.com")
    learner = onboard(client, headers, "rag", "Multi Course")
    first_course = client.get("/api/curriculum/current", headers=headers).json()
    first_course_id = first_course["course_id"]
    first_path = client.get(
        f"/api/learners/{learner['id']}/learning-path?course_id={first_course_id}",
        headers=headers,
    ).json()
    first_topic_id = first_path["current_topic_id"]

    opened = client.get(
        f"/api/learners/{learner['id']}/topics/{first_topic_id}/content",
        headers=headers,
    )
    assert opened.status_code == 200
    completed = client.post(
        f"/api/learners/{learner['id']}/topics/{first_topic_id}/complete",
        headers=headers,
    )
    assert completed.status_code == 200

    updated_profile = client.post(
        "/api/learners",
        headers=headers,
        json={
            "name": "Multi Course",
            "experience_level": "beginner",
            "goal_key": "ai_agents",
        },
    )
    assert updated_profile.status_code == 201
    second_course_response = client.post("/api/curriculum/generate", headers=headers)
    assert second_course_response.status_code == 200
    courses = second_course_response.json()["courses"]
    assert len(courses) == 2
    second_course = next(
        course for course in courses if course["course_id"] != first_course_id
    )
    second_path = client.get(
        f"/api/learners/{learner['id']}/learning-path?course_id={second_course['course_id']}",
        headers=headers,
    ).json()
    resumed_first_path = client.get(
        f"/api/learners/{learner['id']}/learning-path?course_id={first_course_id}",
        headers=headers,
    ).json()

    assert second_path["course_id"] == second_course["course_id"]
    assert all(
        item["topic_id"] in {topic["topic_id"] for topic in second_course["topics"]}
        for item in second_path["topics"]
    )
    assert resumed_first_path["path_id"] == first_path["path_id"]
    assert resumed_first_path["course_id"] == first_course_id
    assert resumed_first_path["topics"][0]["topic_id"] == first_topic_id
    assert resumed_first_path["topics"][0]["status"] == "completed"
    assert all(item["status"] in {"current", "pending"} for item in second_path["topics"])


def test_user_can_resume_progress_after_login_again(client: TestClient):
    _, headers = register(client, "Resume", "resume@example.com")
    learner = onboard(client, headers, "prompt_engineering", "Resume")
    path = client.post(f"/api/learners/{learner['id']}/learning-path/generate", headers=headers).json()
    current_id = path["current_topic_id"]
    opened = client.get(f"/api/learners/{learner['id']}/topics/{current_id}/content", headers=headers)
    assert opened.status_code == 200
    client.post(f"/api/learners/{learner['id']}/topics/{current_id}/complete", headers=headers)

    login = client.post("/api/auth/login", json={"email": "resume@example.com", "password": "password123"})
    resumed_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    summary = client.get("/api/curriculum/current", headers=resumed_headers)
    assert summary.status_code == 200
    resumed_path = client.get(f"/api/learners/{learner['id']}/learning-path", headers=resumed_headers)
    assert resumed_path.status_code == 200
    assert resumed_path.json()["current_topic_id"] != current_id


def test_mocked_ai_curriculum_structures_differ(monkeypatch):
    from app.models import Learner

    rag = Learner(name="Rag", experience_level="beginner", goal_text="Learn RAG")
    agents = Learner(name="Agents", experience_level="advanced", goal_text="Build AI agents")
    rag_curriculum = curriculum_service._fallback_curriculum(rag)
    agent_curriculum = curriculum_service._fallback_curriculum(agents)
    assert rag_curriculum.course_title != agent_curriculum.course_title
    assert [topic.title for topic in rag_curriculum.topics] != [topic.title for topic in agent_curriculum.topics]


def test_fallback_curricula_and_lessons_use_track_specific_concepts():
    concept_sets = {}
    for track in AI_TRACKS:
        learner = Learner(
            name=f"{track.id} learner",
            experience_level="beginner",
            goal_text=f"Learn {track.name}",
            track=track.id,
        )
        curriculum = curriculum_service._fallback_curriculum(learner)
        concepts = [concept for topic in curriculum.topics for concept in topic.concepts]

        assert len(set(concepts)) >= 8
        assert all(track.id not in topic.concepts for topic in curriculum.topics)
        assert all(
            "Generative AI workflow" not in objective
            for topic in curriculum.topics
            for objective in topic.learning_objectives
        )
        concept_sets[track.id] = set(concepts)

        first_topic = curriculum.topics[0]
        lesson = content_service._fallback_content(
            Topic(
                id=f"generated-{track.id}",
                title=first_topic.title,
                description=first_topic.description,
                difficulty=first_topic.difficulty,
                concept_tags=first_topic.concepts,
            ),
            learner,
            [],
            [],
        )
        assert lesson.key_concepts == [
            concept.replace("_", " ") for concept in first_topic.concepts
        ]
        assert "application practice" not in lesson.key_concepts

    assert len({frozenset(concepts) for concepts in concept_sets.values()}) == len(AI_TRACKS)
