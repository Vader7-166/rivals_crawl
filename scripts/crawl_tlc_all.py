"""Crawl TOAN BO san pham cua tlclighting.com.vn (khong gioi han 1 category).

Khac voi crawl_tlc_downlight.py (chi 129 SP cua "Đèn LED âm trần"), script nay
lay danh sach URL tu product-sitemap.xml - nguon da duoc site-probing xac nhan
do tin cay 100% cho ca domain - roi crawl het.

Ket qua ghi vao 1 file .xlsx duy nhat, MOI LOAI SAN PHAM 1 SHEET (chia theo
`category 1` cua chinh site nguon - xem record/excel_writer.py).

Chay: .venv/bin/python scripts/crawl_tlc_all.py [gioi_han_so_san_pham]
Tham so tuy chon `gioi_han_so_san_pham` de chay thu tren mau nho truoc.
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawler.config import CRAWL, OUTPUT  # noqa: E402
from crawler.fetch import StealthFetcher  # noqa: E402
from crawler.llm import LLMProviderError, build_default_llm_provider  # noqa: E402
from crawler.pipeline import crawl_product_urls  # noqa: E402
from crawler.probing import ProbeCache, probe_domain  # noqa: E402
from crawler.record import (  # noqa: E402
    CrawlStatus,
    ProductRecord,
    group_records_by_type,
    load_existing_records,
    write_records_to_excel,
)
from crawler.sites.tlc import BASE_URL  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("crawl_tlc_all")

OUTPUT_PATH = OUTPUT.output_dir / "tlclighting_all.xlsx"

# So san pham crawl xong thi ghi file 1 lan (xem chu thich o main()).
BATCH_SIZE = 40


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None

    try:
        llm_provider = build_default_llm_provider()
    except LLMProviderError as exc:
        logger.error("Không thể khởi tạo LLM provider: %s", exc)
        raise SystemExit(1)

    with StealthFetcher() as fetcher:
        probe = probe_domain(BASE_URL, fetcher, cache=ProbeCache())
        logger.info(
            "Site probing: strategy=%s reliability=%s sitemap=%s",
            probe.strategy, probe.reliability_score, probe.sitemap_url,
        )
        # product-sitemap.xml cua WooCommerce co ca trang luu tru /shop/ lan
        # san pham; loc theo dung pattern URL san pham cua TLC de khong ton
        # luot fetch + goi LLM cho trang khong phai san pham.
        product_urls = sorted(u for u in probe.product_urls if "/san-pham/" in u)
        skipped = len(probe.product_urls) - len(product_urls)
        if skipped:
            logger.info("Bỏ qua %d URL trong sitemap không phải trang sản phẩm", skipped)

    if not product_urls:
        logger.error("Probe không trả về URL sản phẩm nào - dừng.")
        raise SystemExit(1)

    if limit:
        product_urls = product_urls[:limit]
    logger.info("Sẽ crawl %d URL sản phẩm của toàn site", len(product_urls))

    existing = load_existing_records(OUTPUT_PATH)
    if existing:
        logger.info("Dataset trước đó: %d bản ghi (bản ghi OK sẽ không crawl lại)", len(existing))

    # Crawl theo lo va ghi file sau MOI lo, thay vi giu het trong RAM roi ghi 1
    # lan cuoi. Ca site ~485 SP chay hang chuc phut - neu quota Vertex can hay
    # mang dut o phut thu 30 thi cach ghi-1-lan mat sach cong da lam. Ghi tung
    # lo thi lan chay sau doc lai file, thay ban ghi da OK va bo qua (co che
    # crawl-lai-co-chon-loc san co), tiep tuc dung cho dang do.
    done: dict[str, ProductRecord] = dict(existing)
    started = time.time()
    with StealthFetcher() as fetcher:
        for batch_start in range(0, len(product_urls), BATCH_SIZE):
            batch = product_urls[batch_start : batch_start + BATCH_SIZE]
            records = crawl_product_urls(
                batch, llm_provider=llm_provider, fetcher=fetcher,
                existing=done, workers=CRAWL.workers,
            )
            for record in records:
                done[record.link_san_pham or record.product_id] = record

            crawled = min(batch_start + BATCH_SIZE, len(product_urls))
            elapsed = time.time() - started
            write_records_to_excel(_in_url_order(done, product_urls), OUTPUT_PATH)
            logger.info(
                "Tiến độ: %d/%d sản phẩm | %.1f phút đã trôi | ước tính còn %.1f phút",
                crawled, len(product_urls), elapsed / 60,
                elapsed / crawled * (len(product_urls) - crawled) / 60,
            )

    elapsed = time.time() - started
    final = _in_url_order(done, product_urls)
    write_records_to_excel(final, OUTPUT_PATH)

    ok = sum(1 for r in final if r.crawl_status == CrawlStatus.OK)
    grouped = group_records_by_type(final)
    logger.info("Đã ghi %d bản ghi vào %s (%d OK, %d cần review)",
                len(final), OUTPUT_PATH, ok, len(final) - ok)
    logger.info("Chia thành %d sheet theo loại sản phẩm:", len(grouped))
    for name, group in grouped.items():
        logger.info("  %-45s %3d sản phẩm", name, len(group))
    logger.info(
        "THỜI GIAN: %.1f phút cho %d sản phẩm (%d luồng, %.2f s/sản phẩm)",
        elapsed / 60, len(product_urls), CRAWL.workers,
        elapsed / max(1, len(product_urls)),
    )


def _in_url_order(done: dict, product_urls: list[str]) -> list:
    """Ban ghi theo dung thu tu URL cua sitemap, bo ban ghi cua lan chay truoc
    khong con trong danh sach URL hien tai."""
    return [done[url] for url in product_urls if url in done]


if __name__ == "__main__":
    main()
