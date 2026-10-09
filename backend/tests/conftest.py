import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def disable_live_openrouter_requests(monkeypatch, request):
    if request.node.name != "test_live_openrouter_structured_response":
        monkeypatch.setattr(settings, "openrouter_api_key", "")
