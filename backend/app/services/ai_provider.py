import asyncio
import json
import logging
import time
from copy import deepcopy
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import TypeVar

from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel, ValidationError

from ..config import settings


logger = logging.getLogger(__name__)
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class AIProviderError(RuntimeError):
    pass


def _request_with_hard_timeout(
    client_kwargs: dict,
    request_kwargs: dict,
    timeout_seconds: float,
) -> tuple[int, object]:
    async def send_request() -> tuple[int, object]:
        async with AsyncOpenAI(**client_kwargs) as client:
            raw_response = await asyncio.wait_for(
                client.chat.completions.with_raw_response.create(**request_kwargs),
                timeout=timeout_seconds,
            )
            return raw_response.status_code, await raw_response.parse()

    return asyncio.run(send_request())


def _validation_diagnostics(error: ValidationError) -> tuple[list[str], list[str], list[str]]:
    missing: set[str] = set()
    unexpected: set[str] = set()
    errors: list[str] = []
    for item in error.errors(include_input=False, include_url=False):
        location = ".".join(str(part) for part in item["loc"]) or "<root>"
        errors.append(f"{location}:{item['type']}")
        if item["type"] == "missing":
            missing.add(location)
        elif item["type"] == "extra_forbidden":
            unexpected.add(location)
    return sorted(missing), sorted(unexpected), errors


def _strict_json_schema(schema: dict) -> dict:
    strict_schema = deepcopy(schema)

    def close_objects(value: object) -> None:
        if isinstance(value, dict):
            properties = value.get("properties")
            if isinstance(properties, dict):
                for child in properties.values():
                    close_objects(child)
                value["required"] = list(properties)
                value["additionalProperties"] = False
            for key, child in value.items():
                if key != "properties":
                    close_objects(child)
        elif isinstance(value, list):
            for child in value:
                close_objects(child)

    close_objects(strict_schema)
    return strict_schema


def _response_status(error: Exception) -> int | None:
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(getattr(error, "response", None), "status_code", None)
    return status if isinstance(status, int) else None


def _retry_delay(error: Exception) -> float:
    headers = getattr(getattr(error, "response", None), "headers", None)
    retry_after = headers.get("retry-after") if headers else None
    if retry_after:
        try:
            return min(5.0, max(0.0, float(retry_after)))
        except (TypeError, ValueError):
            try:
                retry_at = parsedate_to_datetime(retry_after)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return min(5.0, max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds()))
            except (TypeError, ValueError, OverflowError):
                pass
    return 1.0


def _log_operation(
    *,
    operation: str,
    started_at: str,
    started_clock: float,
    status: str,
    http_status: int | None,
    validation_status: str,
    source: str = "openrouter",
) -> None:
    logger.info(
        "ai_operation=%s started_at=%s duration_ms=%d status=%s source=%s model=%s "
        "http_status=%s validation_status=%s",
        operation,
        started_at,
        round((time.monotonic() - started_clock) * 1000),
        status,
        source,
        settings.openrouter_model,
        http_status,
        validation_status,
    )


def log_ai_fallback(operation: str, reason: str) -> None:
    started_at = datetime.now(timezone.utc).isoformat()
    started_clock = time.monotonic()
    logger.info(
        "ai_operation=%s started_at=%s duration_ms=0 status=fallback source=fallback model=%s "
        "http_status=None validation_status=not_run reason=%s",
        operation,
        started_at,
        settings.openrouter_model,
        reason,
    )


def request_structured_json(
    *,
    operation: str,
    system_prompt: str,
    user_payload: dict,
    response_model: type[ResponseModel],
    temperature: float = 0.2,
    max_tokens: int = 1600,
    timeout_seconds: float | None = None,
    hard_timeout_seconds: float | None = None,
    retry_on_failure: bool = True,
) -> ResponseModel:
    started_at = datetime.now(timezone.utc).isoformat()
    started_clock = time.monotonic()
    http_status: int | None = None
    validation_status = "not_run"
    operation_status = "failure"
    request_timeout = (
        settings.openrouter_timeout_seconds
        if timeout_seconds is None
        else timeout_seconds
    )
    if request_timeout <= 0:
        raise ValueError("timeout_seconds must be positive")
    if hard_timeout_seconds is not None and hard_timeout_seconds <= 0:
        raise ValueError("hard_timeout_seconds must be positive")
    if not settings.openrouter_api_key:
        _log_operation(
            operation=operation,
            started_at=started_at,
            started_clock=started_clock,
            status=operation_status,
            http_status=None,
            validation_status="not_run",
            source="fallback",
        )
        raise AIProviderError("OpenRouter is not configured")

    client_kwargs = {
        "api_key": settings.openrouter_api_key,
        "base_url": settings.openrouter_base_url,
        "timeout": request_timeout,
        "max_retries": 0,
    }
    client = None
    try:
        if hard_timeout_seconds is None:
            client = OpenAI(**client_kwargs)
    except Exception as error:
        logger.warning(
            "OpenRouter client initialization failed; operation=%s model=%s http_status=None "
            "response_type=unavailable validation_error=%s missing_fields=[] unexpected_fields=[]",
            operation,
            settings.openrouter_model,
            type(error).__name__,
        )
        _log_operation(
            operation=operation,
            started_at=started_at,
            started_clock=started_clock,
            status=operation_status,
            http_status=None,
            validation_status="not_run",
        )
        raise AIProviderError("OpenRouter client initialization failed") from None

    try:
        schema = _strict_json_schema(response_model.model_json_schema())
        structured_prompt = (
            f"{system_prompt}\n\n"
            "OUTPUT CONTRACT: Return exactly one valid JSON object and nothing else. "
            "Do not use Markdown, code fences, comments, or prose outside the JSON. "
            "Use exactly the property names and JSON value types in this schema. "
            "Include every required property, omit every unsupported property, and satisfy all constraints. "
            f"JSON schema: {json.dumps(schema, ensure_ascii=True, separators=(',', ':'))}"
        )
        attempt_limit = 2 if retry_on_failure else 1
        for attempt in range(1, attempt_limit + 1):
            attempt_prompt = structured_prompt
            if attempt == 2:
                attempt_prompt += (
                    "\nThis is the single retry. Return a corrected JSON object only."
                )
            request_kwargs = {
                "model": settings.openrouter_model,
                "temperature": temperature if attempt == 1 else 0,
                "max_tokens": max_tokens,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": operation,
                        "strict": True,
                        "schema": schema,
                    },
                },
                "messages": [
                    {"role": "system", "content": attempt_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=True)},
                ],
            }
            try:
                if hard_timeout_seconds is not None:
                    http_status, response = _request_with_hard_timeout(
                        client_kwargs,
                        request_kwargs,
                        hard_timeout_seconds,
                    )
                else:
                    if client is None:
                        raise AIProviderError("OpenRouter client is unavailable")
                    raw_response = client.chat.completions.with_raw_response.create(
                        **request_kwargs
                    )
                    http_status = raw_response.status_code
                    response = raw_response.parse()
            except Exception as error:
                http_status = _response_status(error)
                transient = http_status == 429 or (http_status is not None and 500 <= http_status < 600)
                logger.warning(
                    "OpenRouter request failed; operation=%s model=%s http_status=%s attempt=%s "
                    "response_type=unavailable validation_error=%s missing_fields=[] unexpected_fields=[]",
                    operation,
                    settings.openrouter_model,
                    http_status,
                    attempt,
                    type(error).__name__,
                )
                if transient and attempt < attempt_limit:
                    time.sleep(_retry_delay(error))
                    continue
                raise AIProviderError("OpenRouter request failed") from None

            choice = response.choices[0] if response.choices else None
            message = choice.message if choice else None
            content = message.content if message else None
            if not isinstance(content, str) or not content.strip():
                finish_reason = getattr(choice, "finish_reason", None)
                logger.warning(
                    "OpenRouter returned empty structured content; operation=%s model=%s "
                    "http_status=%s attempt=%s response_type=%s finish_reason=%s refusal_present=%s "
                    "tool_calls_count=%s validation_error=%s missing_fields=[] unexpected_fields=[]",
                    operation,
                    settings.openrouter_model,
                    http_status,
                    attempt,
                    type(content).__name__,
                    finish_reason,
                    bool(getattr(message, "refusal", None)),
                    len(getattr(message, "tool_calls", None) or []),
                    "truncated_generation" if finish_reason == "length" else "empty_content",
                )
                if attempt < attempt_limit:
                    continue
                validation_status = "failed"
                raise AIProviderError("OpenRouter returned empty structured content")

            normalized_content = content.strip()
            if normalized_content.startswith("```") and normalized_content.endswith("```"):
                fenced_lines = normalized_content.splitlines()
                if len(fenced_lines) >= 3 and fenced_lines[0].strip().lower() in {"```", "```json"}:
                    normalized_content = "\n".join(fenced_lines[1:-1]).strip()
            try:
                payload = json.loads(normalized_content)
            except json.JSONDecodeError as error:
                content_format = (
                    "fenced_json"
                    if content.lstrip().startswith("```")
                    else "json_object"
                    if content.lstrip().startswith("{")
                    else "plain_text"
                )
                logger.warning(
                    "OpenRouter structured response failed validation; operation=%s model=%s "
                    "http_status=%s attempt=%s response_type=text content_format=%s content_length=%s "
                    "finish_reason=%s validation_error=malformed_json parse_error=%s line=%s column=%s "
                    "missing_fields=[] unexpected_fields=[]",
                    operation,
                    settings.openrouter_model,
                    http_status,
                    attempt,
                    content_format,
                    len(content),
                    getattr(choice, "finish_reason", None),
                    error.msg,
                    error.lineno,
                    error.colno,
                )
                if attempt < attempt_limit:
                    continue
                validation_status = "failed"
                raise AIProviderError("OpenRouter returned malformed JSON") from None
            try:
                result = response_model.model_validate(payload)
            except ValidationError as error:
                missing, unexpected, details = _validation_diagnostics(error)
                logger.warning(
                    "OpenRouter structured response failed validation; operation=%s model=%s "
                    "http_status=%s attempt=%s response_type=%s validation_error=%s missing_fields=%s "
                    "unexpected_fields=%s",
                    operation,
                    settings.openrouter_model,
                    http_status,
                    attempt,
                    type(payload).__name__,
                    details,
                    missing,
                    unexpected,
                )
                if attempt < attempt_limit:
                    continue
                validation_status = "failed"
                raise

            operation_status = "success"
            validation_status = "passed"
            return result

        validation_status = "failed"
        raise AIProviderError("OpenRouter structured response failed")
    finally:
        _log_operation(
            operation=operation,
            started_at=started_at,
            started_clock=started_clock,
            status=operation_status,
            http_status=http_status,
            validation_status=validation_status,
        )