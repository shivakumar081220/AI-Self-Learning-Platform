from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import GeneratedCourse, Learner, TopicProgress
from app.seed_topics import seed_topics
from app.services import curriculum_service


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

    path = client.post(f"/api/learners/{learner['id']}/learning-path/generate", headers=headers)
    assert path.status_code == 200
    body = path.json()
    assert body["topics"]
    assert all(item["topic_id"].startswith("generated-") for item in body["topics"])


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
