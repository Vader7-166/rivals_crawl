"""Ghep html_cleaner + prompt + provider + validate thanh 1 ham tien ich.

Day la diem vao chinh cua tang 2 (llm-attribute-normalization) ma cac module
khac (vd pipeline crawl TLC) se goi, thay vi tu ghep tung buoc.
"""
from __future__ import annotations

from .html_cleaner import clean_html_for_llm
from .provider import LLMProvider
from .schema import EXTRACTION_JSON_SCHEMA, ExtractionOutput, build_prompt
from .validate import (
    ExtractionValidationError,
    drop_ungrounded_tags,
    parse_and_validate,
)


def extract_tags_from_html(
    product_name: str,
    html: str,
    provider: LLMProvider,
    spec_root_selector: str | None = None,
    noise_selector: str | None = None,
) -> ExtractionOutput:
    """Lam sach HTML (7.5) -> goi LLM (7.2-7.4) -> validate output (7.6).

    `spec_root_selector` (tuy chon, dang ky theo domain o
    extraction.css_fallback.DOMAIN_SPEC_ROOT_SELECTORS) khoanh vung khoi thong
    so ky thuat cho site khong dung <table>; `noise_selector` go cac khoi
    KHONG thuoc san pham dang xem (vd luoi "san pham lien quan") truoc khi
    dua trang cho model - xem html_cleaner.

    Loi provider (LLMProviderError) va loi validate (ExtractionValidationError)
    duoc de nguyen throw ra ngoai - ben goi (pipeline crawl) quyet dinh coi day
    la crawl_status=error hay giu ban ghi o partial-missing-fields.
    """
    cleaned_text = clean_html_for_llm(
        html, spec_root_selector=spec_root_selector, noise_selector=noise_selector
    )
    prompt = build_prompt(product_name, cleaned_text)
    raw_response = provider.generate_json(prompt, EXTRACTION_JSON_SCHEMA)
    result = parse_and_validate(raw_response)
    # Doi chieu voi DUNG text da dua cho model: gia tri model tu nghi ra bi loai
    # o day thay vi lot vao file giao cho nguoi dung (xem drop_ungrounded_tags).
    result.tags = drop_ungrounded_tags(result.tags, cleaned_text)
    return result


__all__ = [
    "extract_tags_from_html",
    "ExtractionOutput",
    "ExtractionValidationError",
]
