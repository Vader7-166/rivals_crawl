"""Entry point: crawl category "Đèn LED âm trần" cua TLC va xuat ra Excel.
Tasks 8.1-8.6 (tlc-downlight-crawler).

Chay: .venv/Scripts/python.exe scripts/crawl_tlc_downlight.py

Yeu cau: da cau hinh it nhat 1 trong VERTEX_PROJECT_ID hoac DEEPSEEK_API_KEY
trong .env (xem .env.example), va CLOAKBROWSER_EXECUTABLE_PATH neu co cloakBrowser
that (khong co se fallback ve Chromium mac dinh cua Playwright, xem canh bao
log luc chay).
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawler.config import OUTPUT  # noqa: E402
from crawler.fetch import StealthFetcher  # noqa: E402
from crawler.llm import LLMProviderError, build_default_llm_provider  # noqa: E402
from crawler.pipeline import crawl_product_urls  # noqa: E402
from crawler.probing import ProbeCache, probe_domain  # noqa: E402
from crawler.record import (  # noqa: E402
    CrawlStatus,
    load_existing_records,
    records_needing_recrawl,
    write_records_to_excel,
)
from crawler.sites.tlc import BASE_URL, CATEGORY_URL, discover_category_product_urls  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("crawl_tlc_downlight")

OUTPUT_PATH = OUTPUT.output_dir / "tlclighting.xlsx"


def main() -> None:
    try:
        llm_provider = build_default_llm_provider()
    except LLMProviderError as exc:
        logger.error("Không thể khởi tạo LLM provider: %s", exc)
        logger.error("Cấu hình VERTEX_PROJECT_ID hoặc DEEPSEEK_API_KEY trong .env rồi chạy lại.")
        raise SystemExit(1)

    with StealthFetcher() as fetcher:
        # Task 8.1: site-probing xac nhan nguon URL dang tin cay cho ca domain.
        probe = probe_domain(BASE_URL, fetcher, cache=ProbeCache())
        logger.info(
            "Site probing: strategy=%s reliability=%s sitemap_url=%s",
            probe.strategy,
            probe.reliability_score,
            probe.sitemap_url,
        )

        # Task 8.2: URL cua rieng category "Đèn LED âm trần" lay tu chinh
        # trang danh muc (sitemap khong mang thong tin category - xem
        # docstring trong sites/tlc.py), doi chieu voi ket qua probe.
        category_urls = discover_category_product_urls(fetcher, CATEGORY_URL)
        logger.info("Tìm thấy %d URL sản phẩm trong category Đèn LED âm trần", len(category_urls))

        if probe.strategy == "sitemap":
            known = set(probe.product_urls)
            unmatched = [u for u in category_urls if u not in known]
            if unmatched:
                logger.warning(
                    "%d/%d URL từ category listing KHÔNG khớp với product-sitemap.xml đã probe: %s",
                    len(unmatched),
                    len(category_urls),
                    unmatched[:5],
                )

        # Task 2.4/8.6: doc file .xlsx da co (neu co) de crawl-lai-co-chon-loc,
        # chi crawl lai ban ghi loi/thieu field thay vi toan bo category.
        existing = load_existing_records(OUTPUT_PATH)
        if existing:
            to_retry = records_needing_recrawl(existing)
            logger.info(
                "Tìm thấy dataset trước đó: %d bản ghi, %d cần crawl lại (lỗi/thiếu field)",
                len(existing),
                len(to_retry),
            )

        # Task 8.3: chay end-to-end fetch -> tang 1 -> tang 1.5 -> tang 2.
        # checkpoint_path=OUTPUT_PATH: neu tien trinh bi ngat giua chung (da
        # tung gap khi chay thuc te), lan chay lai se doc duoc phan da crawl
        # va chi crawl tiep phan con thieu thay vi lam lai tu dau.
        records = crawl_product_urls(
            category_urls,
            fetcher=fetcher,
            llm_provider=llm_provider,
            existing=existing,
            checkpoint_path=OUTPUT_PATH,
            checkpoint_every=5,
        )

    # Task 8.4: xuat Excel, xac nhan so dong khop so san pham tren site.
    write_records_to_excel(records, OUTPUT_PATH)
    ok = sum(1 for r in records if r.crawl_status == CrawlStatus.OK)
    logger.info(
        "Đã ghi %d bản ghi vào %s (%d OK, %d cần review)",
        len(records),
        OUTPUT_PATH,
        ok,
        len(records) - ok,
    )
    if len(records) != len(category_urls):
        logger.warning(
            "Số bản ghi (%d) khác số URL category tìm được (%d) - kiểm tra lại.",
            len(records),
            len(category_urls),
        )


if __name__ == "__main__":
    main()
