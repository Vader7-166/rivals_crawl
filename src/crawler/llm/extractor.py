"""Ghep html_cleaner + prompt + provider + validate thanh 1 ham tien ich.

Day la diem vao chinh cua tang 2 (llm-attribute-normalization) ma cac module
khac (vd pipeline crawl TLC) se goi, thay vi tu ghep tung buoc.
"""
from __future__ import annotations

from .html_cleaner import clean_html_for_llm
from .provider import LLMProvider
from .schema import EXTRACTION_JSON_SCHEMA, ExtractionOutput, build_prompt
from .validate import ExtractionValidationError, parse_and_validate


def extract_tags_from_html(
    product_name: str, html: str, provider: LLMProvider
) -> ExtractionOutput:
    """Lam sach HTML (7.5) -> goi LLM (7.2-7.4) -> validate output (7.6).

    Loi provider (LLMProviderError) va loi validate (ExtractionValidationError)
    duoc de nguyen throw ra ngoai - ben goi (pipeline crawl) quyet dinh coi day
    la crawl_status=error hay giu ban ghi o partial-missing-fields.
    """
    cleaned_text = clean_html_for_llm(html)
    prompt = build_prompt(product_name, cleaned_text)
    raw_response = provider.generate_json(prompt, EXTRACTION_JSON_SCHEMA)
    return parse_and_validate(raw_response)


__all__ = [
    "extract_tags_from_html",
    "ExtractionOutput",
    "ExtractionValidationError",
]
