import json
import logging
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from ..config import settings


logger = logging.getLogger(__name__)
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class AIProviderError(RuntimeError):
    pass


def request_structured_json(
    *,
    system_prompt: str,
    user_payload: dict,
    response_model: type[ResponseModel],
    temperature: float = 0.2,
    max_tokens: int = 1600,
) -> ResponseModel:
    if not settings.openrouter_api_key:
        raise AIProviderError("OpenRouter is not configured")

    client = OpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        timeout=settings.openrouter_timeout_seconds,
    )
    try:
        response = client.chat.completions.create(
            model=settings.openrouter_model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=True)},
            ],
        )
    except Exception as error:
        logger.warning("OpenRouter request failed; error_type=%s", type(error).__name__)
        raise AIProviderError("OpenRouter request failed") from None

    if not response.choices or not response.choices[0].message.content:
        logger.warning("OpenRouter returned empty structured content")
        raise AIProviderError("OpenRouter returned empty structured content")
    content = response.choices[0].message.content
    try:
        return response_model.model_validate_json(content)
    except ValidationError:
        logger.warning("OpenRouter structured response failed validation; model=%s", settings.openrouter_model)
        raise