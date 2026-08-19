"""Noi tang 1 (structured data) -> tang 1.5 (CSS fallback) -> tang 2 (LLM)
thanh 1 pipeline crawl 1 danh sach URL san pham thanh ProductRecord.

Dung chung cho moi site (khong rieng cho TLC) - xem src/crawler/sites/tlc.py
cho phan logic rieng cua TLC (tim URL san pham thuoc 1 category cu the).
"""
from __future__ import annotations

import logging

from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Sequence
from urllib.parse import urlparse

from .config import CRAWL
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
    llm_provider: LLMProvider,
    fetcher: Optional[StealthFetcher] = None,
    existing: Optional[dict[str, ProductRecord]] = None,
    workers: Optional[int] = None,
) -> list[ProductRecord]:
    """Crawl danh sach URL san pham. Neu `existing` duoc truyen vao (tu
    excel_reader.load_existing_records), cac URL da co ban ghi trang thai OK
    se duoc tai su dung thay vi crawl lai (crawl-lai-co-chon-loc, task 2.4/8.6).

    `workers` > 1 thi fetch van TUAN TU (1 browser duy nhat) nhung phan xu ly
    tang 1/1.5/2 chay song song va chong len phan fetch - xem _crawl_pipelined
    de biet vi sao KHONG song song hoa phan fetch.
    """
    existing = existing or {}
    workers = CRAWL.workers if workers is None else workers

    # Tach truoc: ban ghi da OK thi khong ton fetch lan goi LLM nao.
    results: list[Optional[ProductRecord]] = [None] * len(urls)
    todo: list[tuple[int, str]] = []
    for index, url in enumerate(urls):
        prior = existing.get(url)
        if prior is not None and prior.crawl_status == CrawlStatus.OK:
            results[index] = prior
        else:
            todo.append((index, url))

    if todo:
        logger.info(
            "Cần crawl %d/%d URL (%d tái sử dụng từ lần trước), %d luồng xử lý",
            len(todo), len(urls), len(urls) - len(todo), max(1, workers),
        )
        owned = None
        if fetcher is None:
            owned = StealthFetcher()
            owned.__enter__()
            fetcher = owned
        try:
            if workers > 1:
                _crawl_pipelined(todo, results, fetcher, llm_provider, workers)
            else:
                for index, url in todo:
                    results[index] = _crawl_single_product(
                        url, fallback_product_id=str(index + 1),
                        fetcher=fetcher, llm_provider=llm_provider,
                    )
        finally:
            if owned is not None:
                owned.__exit__(None, None, None)

    return [r for r in results if r is not None]


def _crawl_pipelined(
    todo: list[tuple[int, str]],
    results: list[Optional[ProductRecord]],
    fetcher: StealthFetcher,
    llm_provider: LLMProvider,
    workers: int,
) -> None:
    """Fetch TUAN TU (1 browser) nhung xu ly SONG SONG, 2 phan chong len nhau.

    Kien truc BAT DOI XUNG nay dua tren do thuc te, khong phai suy luan - va no
    nguoc voi truc giac "song song hoa tat ca":

    Fetch song song lam CHAM DI (tlclighting.com.vn, 24 san pham):
        1 luong 3.38s/SP | 4 luong 4.04s/SP (0.84x) | 8 luong 5.77s/SP (0.59x)
    kem theo timeout 30s -> MAT san pham. Server doi thu bop bang thong theo so
    ket noi dong thoi; may minh (12 core, CPU rank ranh) khong phai nut that.

    Nguoc lai, goi LLM song song thi CO an that (phia Google):
        1 luong 16.6 SP/phut | 3 luong 28.8 | 6 luong 39.5

    Nen: main thread fetch tung trang mot (lich su voi server ho), moi trang
    fetch xong duoc day ngay vao pool de tang 1/1.5/2 chay nen. Trong luc worker
    dang goi LLM cho san pham N thi main thread da fetch san pham N+1 - thoi
    gian LLM bi "giau" sau thoi gian fetch. Tran moi la phan fetch tuan tu, va
    do la tran KHONG the pha bo them ma khong lam phien server doi thu.
    """
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = []
        for index, url in todo:
            # Chi buoc nay chiem main thread; submit() tra ve ngay lap tuc nen
            # vong lap chay tiep sang URL ke tiep trong khi worker dang xu ly.
            fetch_result = fetcher.fetch(url)
            futures.append(
                pool.submit(
                    _record_from_fetch, index, url, fetch_result,
                    str(index + 1), llm_provider,
                )
            )
        for future in futures:
            index, record = future.result()
            results[index] = record


def _crawl_single_product(
    url: str, *, fallback_product_id: str, fetcher: StealthFetcher, llm_provider: LLMProvider
) -> ProductRecord:
    """Duong chay tuan tu: fetch roi xu ly ngay trong cung 1 luong."""
    fetch_result = fetcher.fetch(url)
    return _build_record(url, fetch_result, fallback_product_id, llm_provider)


def _record_from_fetch(
    index: int,
    url: str,
    fetch_result,
    fallback_product_id: str,
    llm_provider: LLMProvider,
) -> tuple[int, ProductRecord]:
    """Ban chay trong worker pool: nhan HTML da fetch san, chi lam tang 1/1.5/2.

    Tra kem `index` de ben goi ghep lai dung thu tu URL ban dau.
    """
    return index, _build_record(url, fetch_result, fallback_product_id, llm_provider)


def _build_record(
    url: str, fetch_result, fallback_product_id: str, llm_provider: LLMProvider
) -> ProductRecord:
    """Tang 1 -> tang 1.5 -> tang 2 tren HTML da co san (khong fetch nua)."""
    domain = urlparse(url).netloc

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
    llm_error: Optional[str] = None
    try:
        extraction = extract_tags_from_html(structured.ten_san_pham or "", html, llm_provider)
        tags = extraction.tags
        ma_san_pham = ma_san_pham or extraction.ma_san_pham
    except (LLMProviderError, ExtractionValidationError) as exc:
        logger.warning("Tầng 2 (LLM) thất bại cho %s: %s", url, exc)
        llm_error = str(exc)

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
    # `tags` rong (do llm_error) lam recompute_status() ha trang thai xuong
    # PARTIAL_MISSING_FIELDS - ban ghi tu dong thanh ung vien crawl lai. Ghi
    # them ly do de log/debug, khong xuat ra Excel.
    record.recompute_status()
    if llm_error is not None:
        record.crawl_error = f"Tầng 2 (LLM) thất bại: {llm_error}"
    return record
