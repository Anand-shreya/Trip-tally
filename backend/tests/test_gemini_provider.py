import json

import httpx
import pytest
from pydantic import BaseModel, Field


class Greeting(BaseModel):
    greeting: str = Field(min_length=1)


def test_gemini_provider_requests_and_validates_structured_json():
    from app.providers.gemini import GeminiProvider

    captured_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v1beta/models/gemini-3.5-flash-lite:generateContent")
        assert request.headers["x-goog-api-key"] == "test-gemini-key"
        payload = json.loads(request.content)
        captured_payload.update(payload)
        assert payload["systemInstruction"]["parts"] == [
            {"text": "Return only the requested facts."}
        ]
        assert payload["contents"] == [
            {"role": "user", "parts": [{"text": '{"destination":"Kyoto"}'}]}
        ]
        config = payload["generationConfig"]
        assert config["responseMimeType"] == "application/json"
        assert config["responseJsonSchema"]["required"] == ["greeting"]
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": '{"greeting":"Hello from Gemini"}'}],
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 6},
                "modelVersion": "gemini-3.5-flash-lite",
            },
        )

    provider = GeminiProvider(
        api_key="test-gemini-key",
        model="gemini-3.5-flash-lite",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.generate_structured(
        instructions="Return only the requested facts.",
        input_messages=[{"role": "user", "content": '{"destination":"Kyoto"}'}],
        text_format=Greeting,
        max_output_tokens=900,
    )

    assert result == Greeting(greeting="Hello from Gemini")
    assert captured_payload["generationConfig"]["maxOutputTokens"] == 900


def test_gemini_provider_omits_token_limit_when_not_requested():
    from app.providers.gemini import GeminiProvider

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert "maxOutputTokens" not in payload["generationConfig"]
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": '{"greeting":"Hello"}'}]}}]},
        )

    provider = GeminiProvider(
        api_key="test-gemini-key",
        model="gemini-3.5-flash-lite",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.generate_structured(
        instructions="Return JSON.",
        input_messages=[{"role": "user", "content": "Hello"}],
        text_format=Greeting,
    )

    assert result.greeting == "Hello"


def test_gemini_provider_rejects_a_response_without_structured_text():
    from app.providers.gemini import GeminiProvider

    provider = GeminiProvider(
        api_key="test-gemini-key",
        model="gemini-3.5-flash-lite",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    json={
                        "candidates": [
                            {
                                "content": {"role": "model", "parts": []},
                                "finishReason": "STOP",
                            }
                        ]
                    },
                )
            )
        ),
    )

    with pytest.raises(RuntimeError, match="no structured output"):
        provider.generate_structured(
            instructions="Return JSON.",
            input_messages=[{"role": "user", "content": "Hello"}],
            text_format=Greeting,
        )
