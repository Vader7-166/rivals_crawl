"""Adapter Vertex AI (Gemini 2.5 Flash) - provider LLM chinh. Task 7.2."""
from __future__ import annotations

from google import genai
from google.genai import types

from ..config import VERTEX, VertexConfig
from .provider import LLMProvider, LLMProviderError


class VertexAIProvider(LLMProvider):
    name = "vertex-ai"

    def __init__(self, config: VertexConfig = VERTEX):
        if not config.is_configured:
            raise LLMProviderError("Vertex AI chưa được cấu hình (thiếu VERTEX_PROJECT_ID)")
        self._config = config
        self._client = genai.Client(
            vertexai=True, project=config.project_id, location=config.location
        )

    def generate_json(self, prompt: str, json_schema: dict | None = None) -> str:
        gen_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            **({"response_json_schema": json_schema} if json_schema else {}),
        )
        try:
            response = self._client.models.generate_content(
                model=self._config.model,
                contents=prompt,
                config=gen_config,
            )
        except Exception as exc:  # SDK co the nem nhieu loai loi (quota, auth, network...)
            raise LLMProviderError(f"Vertex AI lỗi: {exc}") from exc

        text = getattr(response, "text", None)
        if not text:
            raise LLMProviderError("Vertex AI trả về nội dung rỗng")
        return text
