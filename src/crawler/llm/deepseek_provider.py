"""Adapter DeepSeek (v4-flash, tuong thich OpenAI API) - provider LLM fallback. Task 7.3."""
from __future__ import annotations

from openai import OpenAI

from ..config import DEEPSEEK, DeepSeekConfig
from .provider import LLMProvider, LLMProviderError


class DeepSeekProvider(LLMProvider):
    name = "deepseek"

    def __init__(self, config: DeepSeekConfig = DEEPSEEK):
        if not config.is_configured:
            raise LLMProviderError("DeepSeek chưa được cấu hình (thiếu DEEPSEEK_API_KEY)")
        self._config = config
        self._client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    def generate_json(self, prompt: str, json_schema: dict | None = None) -> str:
        # DeepSeek (API tuong thich OpenAI) chi ho tro JSON mode chung chung
        # (response_format={"type": "json_object"}), khong nhan 1 JSON schema
        # cu the nhu Vertex AI - json_schema bi bo qua co y, dua vao huong dan
        # trong prompt + validate.py o tang goi phia tren.
        try:
            response = self._client.chat.completions.create(
                model=self._config.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            raise LLMProviderError(f"DeepSeek lỗi: {exc}") from exc

        choices = getattr(response, "choices", None) or []
        content = choices[0].message.content if choices else None
        if not content:
            raise LLMProviderError("DeepSeek trả về nội dung rỗng")
        return content
