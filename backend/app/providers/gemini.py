from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider:
    """Generate schema-validated text with Gemini without exposing its key."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self._http = http_client or httpx.Client(timeout=45.0)

    def generate_structured(
        self,
        *,
        instructions: str,
        input_messages: list[dict[str, Any]],
        text_format: type[BaseModel],
        max_output_tokens: int | None = None,
    ) -> BaseModel:
        contents = []
        for message in input_messages:
            role = "model" if message.get("role") == "assistant" else "user"
            content = message.get("content")
            if not isinstance(content, str):
                raise ValueError("Gemini input message content must be text")
            contents.append({"role": role, "parts": [{"text": content}]})

        generation_config: dict[str, Any] = {
            "responseMimeType": "application/json",
            "responseJsonSchema": text_format.model_json_schema(),
        }
        if max_output_tokens is not None:
            generation_config["maxOutputTokens"] = max_output_tokens

        response = self._http.post(
            f"{GEMINI_API_BASE}/models/{quote(self.model, safe='')}:generateContent",
            headers={"x-goog-api-key": self._api_key},
            json={
                "systemInstruction": {"parts": [{"text": instructions}]},
                "contents": contents,
                "generationConfig": generation_config,
            },
        )
        response.raise_for_status()
        payload = response.json()
        candidates = payload.get("candidates") if isinstance(payload, dict) else None
        if not isinstance(candidates, list) or not candidates:
            raise RuntimeError("Gemini returned no structured output")
        content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list):
            raise RuntimeError("Gemini returned no structured output")
        output = "".join(
            part["text"]
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
        if not output:
            raise RuntimeError("Gemini returned no structured output")
        return text_format.model_validate_json(output)

    def close(self) -> None:
        self._http.close()
