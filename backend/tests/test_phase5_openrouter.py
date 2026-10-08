import json
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.database import Base, get_db
from app.main import app
from app.models import Learner
from app.seed_topics import seed_topics
from app.services import ai_provider, diagnostic_service
from app.services.diagnostic_service import CURATED_DIAGNOSTIC_QUESTIONS


@pytest.fixture
def database(tmp_path) -> Generator[Session, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase5-provider.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as database_session:
        seed_topics(database_session)
        learner = Learner(
            name="Provider Test Learner",
            experience_level="beginner",
            goal_text="Build LLM-powered applications",
        )
        database_session.add(learner)
        database_session.commit()
        database_session.refresh(learner)
        yield database_session


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase5-api.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as database_session:
        seed_topics(database_session)

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine) as database_session:
            yield database_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class FakeOpenAI:
    response_content = json.dumps(
        {
            "questions": [
                {**question, "difficulty": "beginner"}
                for question in CURATED_DIAGNOSTIC_QUESTIONS
            ]
        }
    )
    constructor_args: dict[str, str] = {}

    def __init__(self, **kwargs):
        self.constructor_args = kwargs
        FakeOpenAI.constructor_args = kwargs
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(
                with_raw_response=SimpleNamespace(create=self.create_raw_response)
            )
        )

    def create_raw_response(self, **kwargs):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.response_content))]
        )
        return SimpleNamespace(status_code=200, parse=lambda: response)


def test_application_starts_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    database_path = Path("adaptive_learning.db")
    database_existed = database_path.exists()

    with TestClient(app) as test_client:
        response = test_client.get("/api/health")
        assert response.status_code == 200

    if not database_existed and database_path.exists():
        database_path.unlink()


def test_openrouter_configuration_loads_from_environment(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://router.example/v1")
    monkeypatch.setenv("OPENROUTER_MODEL", "router/test-model")
    monkeypatch.setenv("OPENROUTER_TIMEOUT_SECONDS", "12.5")

    configured = Settings()

    assert configured.openrouter_api_key == "test-key"
    assert configured.openrouter_base_url == "https://router.example/v1"
    assert configured.openrouter_model == "router/test-model"
    assert configured.openrouter_timeout_seconds == 12.5


def test_openrouter_client_uses_configured_provider(monkeypatch, database: Session):
    learner = database.query(Learner).first()
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "openrouter_base_url", "https://router.example/v1")
    monkeypatch.setattr(settings, "openrouter_model", "router/test-model")
    monkeypatch.setattr(ai_provider, "OpenAI", FakeOpenAI)

    question_set, generated_by = diagnostic_service.generate_diagnostic(learner, database)

    assert generated_by == "openrouter"
    assert len(question_set.questions) == 8
    assert FakeOpenAI.constructor_args == {
        "api_key": "test-key",
        "base_url": "https://router.example/v1",
        "timeout": settings.openrouter_timeout_seconds,
    }


def test_diagnostic_endpoint_reuses_pending_assessment_and_hides_answer_key(
    client: TestClient, monkeypatch
):
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    learner = client.post(
        "/api/learners",
        json={
            "name": "Diagnostic Cache",
            "experience_level": "beginner",
            "goal_key": "llm_apps",
        },
    ).json()

    first = client.post(f"/api/learners/{learner['id']}/diagnostic")
    second = client.post(f"/api/learners/{learner['id']}/diagnostic")

    assert first.status_code == second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert first_body["assessment_id"] == second_body["assessment_id"]
    assert first_body["generated_by"] == second_body["generated_by"] == "curated_fallback"
    assert len(first_body["questions"]) == 8
    assert all("concept" in item and "difficulty" in item for item in first_body["questions"])
    assert all("correct_option" not in item and "explanation" not in item for item in first_body["questions"])


def test_diagnostic_rejects_concepts_outside_catalog(monkeypatch, caplog, database: Session):
    learner = database.query(Learner).first()
    invalid_questions = [
        {**question, "difficulty": "beginner"}
        for question in CURATED_DIAGNOSTIC_QUESTIONS
    ]
    invalid_questions[0]["concept"] = "invented_concept_id"
    FakeOpenAI.response_content = json.dumps({"questions": invalid_questions})
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(ai_provider, "OpenAI", FakeOpenAI)

    question_set, generated_by = diagnostic_service.generate_diagnostic(learner, database)

    assert generated_by == "curated_fallback"
    assert len(question_set.questions) == 8
    assert "validation_error=unknown_concept" in caplog.text
    FakeOpenAI.response_content = json.dumps(
        {
            "questions": [
                {**question, "difficulty": "beginner"}
                for question in CURATED_DIAGNOSTIC_QUESTIONS
            ]
        }
    )


def test_provider_error_uses_fallback_without_logging_key(monkeypatch, caplog, database: Session):
    learner = database.query(Learner).first()

    def failing_provider(**kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(ai_provider, "OpenAI", failing_provider)
    question_set, generated_by = diagnostic_service.generate_diagnostic(learner, database)

    assert generated_by == "curated_fallback"
    assert len(question_set.questions) == 8
    assert "test-key" not in caplog.text


def test_invalid_structured_output_uses_fallback(monkeypatch, database: Session):
    learner = database.query(Learner).first()
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    FakeOpenAI.response_content = json.dumps({"questions": []})
    monkeypatch.setattr(ai_provider, "OpenAI", FakeOpenAI)

    _, generated_by = diagnostic_service.generate_diagnostic(learner, database)

    assert generated_by == "curated_fallback"
    FakeOpenAI.response_content = json.dumps({"questions": CURATED_DIAGNOSTIC_QUESTIONS})


def test_api_response_never_returns_provider_key(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(ai_provider, "OpenAI", FakeOpenAI)
    learner = client.post(
        "/api/learners",
        json={
            "name": "No Secret",
            "experience_level": "beginner",
            "goal_key": "llm_apps",
        },
    ).json()

    response = client.post(f"/api/learners/{learner['id']}/diagnostic/generate")

    assert response.status_code == 200
    assert "test-key" not in response.text
