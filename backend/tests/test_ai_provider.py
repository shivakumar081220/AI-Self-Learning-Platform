import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.services import ai_provider


class TutorPayload(BaseModel):
    answer: str = Field(min_length=4)


class FakeOpenRouter:
    init_kwargs = None
    request_kwargs = None
    content = '{"answer":"A validated answer."}'

    def __init__(self, **kwargs):
        FakeOpenRouter.init_kwargs = kwargs
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        FakeOpenRouter.request_kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=FakeOpenRouter.content))]
        )


def test_structured_request_uses_configured_openrouter_and_learner_context(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-provider-key")
    monkeypatch.setattr(settings, "openrouter_base_url", "https://router.example/v1")
    monkeypatch.setattr(settings, "openrouter_model", "router/test-model")
    monkeypatch.setattr(settings, "openrouter_timeout_seconds", 12.5)
    monkeypatch.setattr(ai_provider, "OpenAI", FakeOpenRouter)

    result = ai_provider.request_structured_json(
        system_prompt="Answer as a tutor.",
        user_payload={"learner": {"experience_level": "intermediate"}, "question": "Explain embeddings."},
        response_model=TutorPayload,
        temperature=0.4,
        max_tokens=180,
    )

    assert result.answer == "A validated answer."
    assert FakeOpenRouter.init_kwargs == {
        "api_key": "test-provider-key",
        "base_url": "https://router.example/v1",
        "timeout": 12.5,
    }
    request = FakeOpenRouter.request_kwargs
    assert request["model"] == "router/test-model"
    assert request["response_format"] == {"type": "json_object"}
    assert request["max_tokens"] == 180
    assert request["messages"][0]["content"] == "Answer as a tutor."
    assert json.loads(request["messages"][1]["content"])["learner"]["experience_level"] == "intermediate"


def test_invalid_structured_response_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-provider-key")
    FakeOpenRouter.content = '{"answer":"x"}'
    monkeypatch.setattr(ai_provider, "OpenAI", FakeOpenRouter)

    with pytest.raises(ValidationError):
        ai_provider.request_structured_json(
            system_prompt="Answer as a tutor.",
            user_payload={"learner": {"experience_level": "beginner"}},
            response_model=TutorPayload,
        )

    FakeOpenRouter.content = '{"answer":"A validated answer."}'


def test_provider_failure_does_not_log_credentials(monkeypatch, caplog):
    def fail_request(**kwargs):
        raise RuntimeError("request failed with test-provider-key")

    class FailingOpenRouter:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=fail_request))

    monkeypatch.setattr(settings, "openrouter_api_key", "test-provider-key")
    monkeypatch.setattr(ai_provider, "OpenAI", FailingOpenRouter)

    with pytest.raises(ai_provider.AIProviderError):
        ai_provider.request_structured_json(
            system_prompt="Answer as a tutor.",
            user_payload={"question": "Explain embeddings."},
            response_model=TutorPayload,
        )

    assert "test-provider-key" not in caplog.text