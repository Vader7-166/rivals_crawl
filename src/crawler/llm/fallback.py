"""Fallback tu dong Vertex AI -> DeepSeek. Task 7.4."""
from __future__ import annotations

import logging
from typing import Sequence

from ..config import DEEPSEEK, VERTEX
from .deepseek_provider import DeepSeekProvider
from .provider import LLMProvider, LLMProviderError
from .vertex_provider import VertexAIProvider

logger = logging.getLogger(__name__)


class FallbackLLMProvider(LLMProvider):
    name = "fallback"

    def __init__(self, providers: Sequence[LLMProvider]):
        if not providers:
            raise ValueError("Cần ít nhất 1 provider cho FallbackLLMProvider")
        self._providers = list(providers)

    def generate_json(self, prompt: str, json_schema: dict | None = None) -> str:
        last_error: Exception | None = None
        for provider in self._providers:
            try:
                logger.info("Gọi LLM provider: %s", provider.name)
                return provider.generate_json(prompt, json_schema)
            except LLMProviderError as exc:
                logger.warning(
                    "Provider %s thất bại (%s), chuyển sang provider tiếp theo", provider.name, exc
                )
                last_error = exc
        raise LLMProviderError(f"Tất cả LLM provider đều thất bại: {last_error}")


def build_default_llm_provider() -> LLMProvider:
    """Vertex AI (Gemini 2.5 Flash) chính, DeepSeek v4-flash fallback - theo
    design.md Decision 5. Chỉ dựng provider nao thuc su co cau hinh."""
    providers: list[LLMProvider] = []
    if VERTEX.is_configured:
        providers.append(VertexAIProvider(VERTEX))
    if DEEPSEEK.is_configured:
        providers.append(DeepSeekProvider(DEEPSEEK))
    if not providers:
        raise LLMProviderError(
            "Chưa cấu hình LLM provider nào - cần VERTEX_PROJECT_ID hoặc DEEPSEEK_API_KEY trong .env"
        )
    return FallbackLLMProvider(providers)
