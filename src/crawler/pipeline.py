"""Noi tang 1 (structured data) -> tang 1.5 (CSS fallback) -> tang 2 (LLM)
thanh 1 pipeline crawl 1 danh sach URL san pham thanh ProductRecord.

Dung chung cho moi site (khong rieng cho TLC) - xem src/crawler/sites/tlc.py
cho phan logic rieng cua TLC (tim URL san pham thuoc 1 category cu the).
"""
from __future__ import annotations

import logging
from typing import Optional, Sequence
from urllib.parse import urlparse

from .extraction import apply_css_fallback, extract_structured_data
from .fetch import StealthFetcher
from .llm.extractor import extract_tags_from_html
from .llm.provider import LLMProvider, LLMProviderError
from .llm.validate import ExtractionValidationError
from .llm.html_cleaner import extract_spec_text
from .record import CrawlStatus, ProductRecord

logger = logging.getLogger(__name__)


def crawl_product_urls(
    urls: Sequence[str],
    *,
    fetcher: StealthFetcher,
    llm_provider: LLMProvider,
    existing: Optional[dict[str, ProductRecord]] = None,
) -> list[ProductRecord]:
    """Crawl danh sach URL san pham. Neu `existing` duoc truyen vao (tu
    excel_reader.load_existing_records), cac URL da co ban ghi trang thai OK
    se duoc tai su dung thay vi crawl lai (crawl-lai-co-chon-loc, task 2.4/8.6)."""
    existing = existing or {}
    records: list[ProductRecord] = []

    for index, url in enumerate(urls, start=1):
        prior = existing.get(url)
        if prior is not None and prior.crawl_status == CrawlStatus.OK:
            records.append(prior)
            continue

        record = _crawl_single_product(url, fallback_product_id=str(index), fetcher=fetcher, llm_provider=llm_provider)
        records.append(record)

    return records


def _crawl_single_product(
    url: str, *, fallback_product_id: str, fetcher: StealthFetcher, llm_provider: LLMProvider
) -> ProductRecord:
    domain = urlparse(url).netloc

    fetch_result = fetcher.fetch(url)
    if not fetch_result.ok or not fetch_result.html:
        logger.warning("Fetch thất bại cho %s: %s", url, fetch_result.error)
        record = ProductRecord(product_id=fallback_product_id, link_san_pham=url)
        record.mark_error(fetch_result.error or f"HTTP {fetch_result.status}")
        return record

    html = fetch_result.html
    structured = extract_structured_data(html, url)

    patched = apply_css_fallback(
        html,
        {"gia": structured.gia, "ma_san_pham": structured.ma_san_pham},
        domain,
    )
    gia = patched.get("gia", structured.gia)
    ma_san_pham = patched.get("ma_san_pham") or structured.ma_san_pham

    tags: dict = {}
    try:
        extraction = extract_tags_from_html(structured.ten_san_pham or "", html, llm_provider)
        tags = extraction.tags
        ma_san_pham = ma_san_pham or extraction.ma_san_pham
    except (LLMProviderError, ExtractionValidationError) as exc:
        logger.warning("Tầng 2 (LLM) thất bại cho %s: %s", url, exc)

    record = ProductRecord(
        product_id=structured.raw_id or fallback_product_id,
        ten_san_pham=structured.ten_san_pham,
        ma_san_pham=ma_san_pham,
        category_1=structured.category_1,
        category_2=structured.category_2,
        category_3=structured.category_3,
        tags=tags,
        gia=gia,
        link_san_pham=url,
        link_anh_san_pham=structured.link_anh_san_pham,
        thong_so_ky_thuat=extract_spec_text(html) or None,
    )
    record.recompute_status()
    return record
