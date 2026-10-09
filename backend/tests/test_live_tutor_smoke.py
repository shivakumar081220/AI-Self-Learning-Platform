import os
from base64 import b64encode

import pytest
from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.services.ai_provider import request_structured_json
from app.services.code_sandbox import run_python


class VisionSmokeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=300)


_LIVE_ENABLED = os.getenv("RUN_LIVE_TUTOR_SMOKE") == "1"


@pytest.mark.skipif(not _LIVE_ENABLED, reason="Set RUN_LIVE_TUTOR_SMOKE=1 for optional live checks.")
def test_live_vision_model_smoke():
    if not settings.openrouter_api_key or not settings.openrouter_vision_model:
        pytest.skip("OPENROUTER_API_KEY and OPENROUTER_VISION_MODEL are required.")
    one_pixel_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\x0bIDAT\x08\xd7c\xf8\x0f\x00\x01\x01\x01\x00\x18\xdd\x8d\xb0"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    response = request_structured_json(
        operation="vision_smoke_test",
        system_prompt="Describe only the visible pixel color in the image in one short phrase.",
        user_payload={},
        user_content=[
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{b64encode(one_pixel_png).decode('ascii')}",
                    "detail": "low",
                },
            },
        ],
        response_model=VisionSmokeResponse,
        model_name=settings.openrouter_vision_model,
        max_tokens=100,
        retry_on_failure=False,
    )
    assert response.description.strip()


@pytest.mark.skipif(not _LIVE_ENABLED, reason="Set RUN_LIVE_TUTOR_SMOKE=1 for optional live checks.")
def test_live_sandbox_smoke():
    if not settings.tutor_code_sandbox_url:
        pytest.skip("TUTOR_CODE_SANDBOX_URL is not configured.")
    result = run_python('print("isolated sandbox smoke")', "")
    assert result["status"] == "completed"
    assert "isolated sandbox smoke" in result["output"]