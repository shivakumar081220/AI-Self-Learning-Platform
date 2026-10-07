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
from app.services import diagnostic_service
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
    response_content = json.dumps({"questions": CURATED_DIAGNOSTIC_QUESTIONS})
    constructor_args: dict[str, str] = {}

    def __init__(self, **kwargs):
        self.constructor_args = kwargs
        FakeOpenAI.constructor_args = kwargs
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self.create_completion)
        )

    def create_completion(self, **kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.response_content))]
        )


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

    configured = Settings()

    assert configured.openrouter_api_key == "test-key"
    assert configured.openrouter_base_url == "https://router.example/v1"
    assert configured.openrouter_model == "router/test-model"


def test_openrouter_client_uses_configured_provider(monkeypatch, database: Session):
    learner = database.query(Learner).first()
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "openrouter_base_url", "https://router.example/v1")
    monkeypatch.setattr(settings, "openrouter_model", "router/test-model")
    monkeypatch.setattr(diagnostic_service, "OpenAI", FakeOpenAI)

    question_set, generated_by = diagnostic_service.generate_diagnostic(learner, database)

    assert generated_by == "openai"
    assert len(question_set.questions) == 8
    assert FakeOpenAI.constructor_args == {
        "api_key": "test-key",
        "base_url": "https://router.example/v1",
    }


def test_provider_error_uses_fallback_without_logging_key(monkeypatch, caplog, database: Session):
    learner = database.query(Learner).first()

    def failing_provider(**kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(diagnostic_service, "OpenAI", failing_provider)
    question_set, generated_by = diagnostic_service.generate_diagnostic(learner, database)

    assert generated_by == "curated_fallback"
    assert len(question_set.questions) == 8
    assert "test-key" not in caplog.text


def test_invalid_structured_output_uses_fallback(monkeypatch, database: Session):
    learner = database.query(Learner).first()
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    FakeOpenAI.response_content = json.dumps({"questions": []})
    monkeypatch.setattr(diagnostic_service, "OpenAI", FakeOpenAI)

    _, generated_by = diagnostic_service.generate_diagnostic(learner, database)

    assert generated_by == "curated_fallback"
    FakeOpenAI.response_content = json.dumps({"questions": CURATED_DIAGNOSTIC_QUESTIONS})


def test_api_response_never_returns_provider_key(monkeypatch, client: TestClient):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(diagnostic_service, "OpenAI", FakeOpenAI)
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
