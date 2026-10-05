from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_ai_status_reports_gemini_without_exposing_its_key(monkeypatch):
    monkeypatch.setenv("TRIPWISE_GEMINI_ENABLED", "true")
    monkeypatch.setenv("TRIPWISE_GEMINI_API_KEY", "private-gemini-key")
    monkeypatch.setenv("TRIPWISE_GEMINI_MODEL", "gemini-3.5-flash-lite")
    get_settings.cache_clear()
    client = TestClient(create_app(init_database=False))

    response = client.get("/api/v1/ai/status")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "gemini",
        "label": "Gemini free tier",
        "model": "gemini-3.5-flash-lite",
        "ai_enabled": True,
    }
    assert "private-gemini-key" not in response.text


def test_ai_status_reports_deterministic_fallback_without_a_gemini_key(monkeypatch):
    monkeypatch.setenv("TRIPWISE_GEMINI_ENABLED", "true")
    monkeypatch.setenv("TRIPWISE_GEMINI_API_KEY", "")
    get_settings.cache_clear()
    client = TestClient(create_app(init_database=False))

    response = client.get("/api/v1/ai/status")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "local",
        "label": "Local planning",
        "model": None,
        "ai_enabled": False,
    }
