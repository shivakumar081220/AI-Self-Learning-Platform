import asyncio
import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import settings
from app.services import ai_provider


class TutorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=4)


class FakeOpenRouter:
    init_kwargs = None
    request_kwargs = None
    content = '{"answer":"A validated answer."}'

    def __init__(self, **kwargs):
        FakeOpenRouter.init_kwargs = kwargs
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(
                with_raw_response=SimpleNamespace(create=self.create_raw)
            )
        )

    def create_raw(self, **kwargs):
        FakeOpenRouter.request_kwargs = kwargs
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=FakeOpenRouter.content))]
        )
        return SimpleNamespace(status_code=200, parse=lambda: response)


def test_structured_request_uses_configured_openrouter_and_learner_context(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-provider-key")
    monkeypatch.setattr(settings, "openrouter_base_url", "https://router.example/v1")
    monkeypatch.setattr(settings, "openrouter_model", "router/test-model")
    monkeypatch.setattr(settings, "openrouter_timeout_seconds", 12.5)
    monkeypatch.setattr(ai_provider, "OpenAI", FakeOpenRouter)

    result = ai_provider.request_structured_json(
        operation="provider_test",
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
        "max_retries": 0,
    }
    request = FakeOpenRouter.request_kwargs
    assert request["model"] == "router/test-model"
    assert request["response_format"]["type"] == "json_schema"
    assert request["response_format"]["json_schema"]["strict"] is True
    assert request["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert request["max_tokens"] == 180
    assert request["messages"][0]["content"].startswith("Answer as a tutor.")
    assert "valid JSON object" in request["messages"][0]["content"]
    assert "additionalProperties" in request["messages"][0]["content"]
    assert json.loads(request["messages"][1]["content"])["learner"]["experience_level"] == "intermediate"


def test_invalid_structured_response_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-provider-key")
    FakeOpenRouter.content = '{"answer":"x"}'
    monkeypatch.setattr(ai_provider, "OpenAI", FakeOpenRouter)

    with pytest.raises(ValidationError):
        ai_provider.request_structured_json(
            operation="provider_test",
            system_prompt="Answer as a tutor.",
            user_payload={"learner": {"experience_level": "beginner"}},
            response_model=TutorPayload,
        )

    FakeOpenRouter.content = '{"answer":"A validated answer."}'


@pytest.mark.parametrize(
    ("content", "missing_field", "unexpected_field"),
    [
        ('{"other":"value"}', "answer", "other"),
        ('{"answer":"A valid answer.","extra":"unsupported"}', "", "extra"),
    ],
)
def test_missing_and_unexpected_fields_are_reported_safely(
    monkeypatch, caplog, content, missing_field, unexpected_field
):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-provider-key")
    monkeypatch.setattr(settings, "openrouter_model", "router/test-model")
    FakeOpenRouter.content = content
    monkeypatch.setattr(ai_provider, "OpenAI", FakeOpenRouter)

    with pytest.raises(ValidationError):
        ai_provider.request_structured_json(
            operation="provider_validation_test",
            system_prompt="Answer as a tutor.",
            user_payload={"question": "Explain embeddings."},
            response_model=TutorPayload,
        )

    assert "operation=provider_validation_test" in caplog.text
    assert "http_status=200" in caplog.text
    assert "response_type=dict" in caplog.text
    if missing_field:
        assert "missing_fields=['answer']" in caplog.text
    assert f"'{unexpected_field}'" in caplog.text
    assert "test-provider-key" not in caplog.text
    FakeOpenRouter.content = '{"answer":"A validated answer."}'


def test_malformed_json_is_reported_as_provider_error(monkeypatch, caplog):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-provider-key")
    FakeOpenRouter.content = "```json\n{\"answer\":\n```"
    monkeypatch.setattr(ai_provider, "OpenAI", FakeOpenRouter)

    with pytest.raises(ai_provider.AIProviderError, match="malformed JSON"):
        ai_provider.request_structured_json(
            operation="provider_malformed_test",
            system_prompt="Answer as a tutor.",
            user_payload={"question": "Explain embeddings."},
            response_model=TutorPayload,
        )

    assert "validation_error=malformed_json" in caplog.text
    assert "OPENROUTER_API_KEY" not in caplog.text
    FakeOpenRouter.content = '{"answer":"A validated answer."}'


def test_empty_model_response_gets_one_retry_then_returns_provider_error(monkeypatch):
    class EmptyResponseOpenRouter:
        attempts = 0

        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    with_raw_response=SimpleNamespace(create=self.create_raw)
                )
            )

        def create_raw(self, **kwargs):
            EmptyResponseOpenRouter.attempts += 1
            response = SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(content=" "),
                    )
                ]
            )
            return SimpleNamespace(status_code=200, parse=lambda: response)

    monkeypatch.setattr(settings, "openrouter_api_key", "test-provider-key")
    monkeypatch.setattr(ai_provider, "OpenAI", EmptyResponseOpenRouter)

    with pytest.raises(ai_provider.AIProviderError, match="empty structured content"):
        ai_provider.request_structured_json(
            operation="provider_empty_response_test",
            system_prompt="Answer as a tutor.",
            user_payload={"question": "Explain embeddings."},
            response_model=TutorPayload,
        )

    assert EmptyResponseOpenRouter.attempts == 2


def test_fenced_json_is_extracted_then_schema_validated(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-provider-key")
    FakeOpenRouter.content = '```json\n{"answer":"A validated answer."}\n```'
    monkeypatch.setattr(ai_provider, "OpenAI", FakeOpenRouter)

    result = ai_provider.request_structured_json(
        operation="provider_fenced_json_test",
        system_prompt="Answer as a tutor.",
        user_payload={"question": "Explain embeddings."},
        response_model=TutorPayload,
    )

    assert result.answer == "A validated answer."
    FakeOpenRouter.content = '{"answer":"A validated answer."}'


def test_malformed_response_gets_one_real_provider_retry(monkeypatch):
    class RetryingOpenRouter:
        attempts = 0

        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    with_raw_response=SimpleNamespace(create=self.create_raw)
                )
            )

        def create_raw(self, **kwargs):
            RetryingOpenRouter.attempts += 1
            content = (
                "not JSON"
                if RetryingOpenRouter.attempts == 1
                else '{"answer":"A validated answer."}'
            )
            response = SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            )
            return SimpleNamespace(status_code=200, parse=lambda: response)

    monkeypatch.setattr(settings, "openrouter_api_key", "test-provider-key")
    monkeypatch.setattr(ai_provider, "OpenAI", RetryingOpenRouter)

    result = ai_provider.request_structured_json(
        operation="provider_retry_test",
        system_prompt="Answer as a tutor.",
        user_payload={"question": "Explain embeddings."},
        response_model=TutorPayload,
    )

    assert result.answer == "A validated answer."
    assert RetryingOpenRouter.attempts == 2


def test_request_can_bound_timeout_and_disable_retry(monkeypatch):
    class SingleAttemptOpenRouter:
        attempts = 0
        init_kwargs = {}

        def __init__(self, **kwargs):
            type(self).init_kwargs = kwargs
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    with_raw_response=SimpleNamespace(create=self.create_raw)
                )
            )

        def create_raw(self, **kwargs):
            type(self).attempts += 1
            response = SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(content="not JSON"),
                    )
                ]
            )
            return SimpleNamespace(status_code=200, parse=lambda: response)

    monkeypatch.setattr(settings, "openrouter_api_key", "test-provider-key")
    monkeypatch.setattr(ai_provider, "OpenAI", SingleAttemptOpenRouter)

    with pytest.raises(ai_provider.AIProviderError, match="malformed JSON"):
        ai_provider.request_structured_json(
            operation="provider_single_attempt_test",
            system_prompt="Answer as a tutor.",
            user_payload={"question": "Explain embeddings."},
            response_model=TutorPayload,
            timeout_seconds=8.0,
            retry_on_failure=False,
        )

    assert SingleAttemptOpenRouter.init_kwargs["timeout"] == 8.0
    assert SingleAttemptOpenRouter.attempts == 1


def test_hard_timeout_cancels_async_provider_request(monkeypatch):
    class SlowAsyncOpenRouter:
        cancelled = False

        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    with_raw_response=SimpleNamespace(create=self.create_raw)
                )
            )

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def create_raw(self, **kwargs):
            try:
                await asyncio.sleep(1)
            finally:
                type(self).cancelled = True

    monkeypatch.setattr(settings, "openrouter_api_key", "test-provider-key")
    monkeypatch.setattr(ai_provider, "AsyncOpenAI", SlowAsyncOpenRouter)

    with pytest.raises(ai_provider.AIProviderError, match="request failed"):
        ai_provider.request_structured_json(
            operation="provider_hard_timeout_test",
            system_prompt="Answer as a tutor.",
            user_payload={"question": "Explain embeddings."},
            response_model=TutorPayload,
            timeout_seconds=0.05,
            hard_timeout_seconds=0.05,
            retry_on_failure=False,
        )

    assert SlowAsyncOpenRouter.cancelled


def test_rate_limit_gets_one_retry_respecting_retry_after(monkeypatch, caplog):
    import logging

    caplog.set_level(logging.INFO)

    class RateLimitedOpenRouter:
        attempts = 0

        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    with_raw_response=SimpleNamespace(create=self.create_raw)
                )
            )

        def create_raw(self, **kwargs):
            RateLimitedOpenRouter.attempts += 1
            if RateLimitedOpenRouter.attempts == 1:
                response = SimpleNamespace(
                    status_code=429,
                    headers={"retry-after": "3"},
                )
                error = RuntimeError("rate limited")
                error.status_code = 429
                error.response = response
                raise error
            response = SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(content='{"answer":"A validated answer."}'),
                    )
                ]
            )
            return SimpleNamespace(status_code=200, parse=lambda: response)

    delays = []
    monkeypatch.setattr(settings, "openrouter_api_key", "test-provider-key")
    monkeypatch.setattr(settings, "openrouter_model", "router/test-model")
    monkeypatch.setattr(ai_provider, "OpenAI", RateLimitedOpenRouter)
    monkeypatch.setattr(ai_provider.time, "sleep", delays.append)

    result = ai_provider.request_structured_json(
        operation="provider_rate_limit_test",
        system_prompt="Answer as a tutor.",
        user_payload={"question": "Explain embeddings."},
        response_model=TutorPayload,
    )

    assert result.answer == "A validated answer."
    assert RateLimitedOpenRouter.attempts == 2
    assert delays == [3.0]
    assert "ai_operation=provider_rate_limit_test" in caplog.text
    assert "source=openrouter" in caplog.text
    assert "validation_status=passed" in caplog.text
    assert "test-provider-key" not in caplog.text


def test_provider_failure_does_not_log_credentials(monkeypatch, caplog):
    def fail_request(**kwargs):
        raise RuntimeError("request failed with test-provider-key")

    class FailingOpenRouter:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    with_raw_response=SimpleNamespace(create=fail_request)
                )
            )

    monkeypatch.setattr(settings, "openrouter_api_key", "test-provider-key")
    monkeypatch.setattr(ai_provider, "OpenAI", FailingOpenRouter)

    with pytest.raises(ai_provider.AIProviderError):
        ai_provider.request_structured_json(
            operation="provider_test",
            system_prompt="Answer as a tutor.",
            user_payload={"question": "Explain embeddings."},
            response_model=TutorPayload,
        )

    assert "test-provider-key" not in caplog.text