import os

import pytest
from pydantic import BaseModel, Field

from app.config import settings
from app.services.ai_provider import request_structured_json


class LiveSmokeResponse(BaseModel):
    answer: str = Field(min_length=3, max_length=240)


@pytest.mark.skipif(
    not settings.openrouter_api_key,
    reason="Live OpenRouter test skipped because no API key is configured.",
)
@pytest.mark.skipif(
    os.getenv("RUN_OPENROUTER_LIVE_TEST") != "1",
    reason="Set RUN_OPENROUTER_LIVE_TEST=1 to opt into the credit-consuming live smoke test.",
)
def test_live_openrouter_structured_response():
    response = request_structured_json(
        system_prompt="Return a JSON object with one short answer field. Do not include markdown.",
        user_payload={"question": "In one sentence, what does retrieval add to RAG?"},
        response_model=LiveSmokeResponse,
        temperature=0,
        max_tokens=100,
    )

    assert response.answer.strip()