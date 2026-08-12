"""Kiem tra co che fallback tu dong (task 7.4) bang provider gia - khong can
credential that."""
import pytest

from crawler.llm.fallback import FallbackLLMProvider
from crawler.llm.provider import LLMProvider, LLMProviderError


class _FailingProvider(LLMProvider):
    name = "failing"

    def generate_json(self, prompt, json_schema=None):
        raise LLMProviderError("hết quota (giả lập)")


class _WorkingProvider(LLMProvider):
    name = "working"

    def generate_json(self, prompt, json_schema=None):
        return '{"tags": {"ok": "true"}}'


class _AllFailProvider(LLMProvider):
    name = "also-failing"

    def generate_json(self, prompt, json_schema=None):
        raise LLMProviderError("lỗi khác (giả lập)")


def test_falls_back_to_next_provider_when_primary_fails():
    fallback = FallbackLLMProvider([_FailingProvider(), _WorkingProvider()])

    result = fallback.generate_json("prompt")

    assert result == '{"tags": {"ok": "true"}}'


def test_uses_primary_when_it_succeeds():
    fallback = FallbackLLMProvider([_WorkingProvider(), _FailingProvider()])

    result = fallback.generate_json("prompt")

    assert result == '{"tags": {"ok": "true"}}'


def test_raises_when_all_providers_fail():
    fallback = FallbackLLMProvider([_FailingProvider(), _AllFailProvider()])

    with pytest.raises(LLMProviderError):
        fallback.generate_json("prompt")
