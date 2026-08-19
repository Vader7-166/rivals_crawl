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
    group_records_by_type,
    load_existing_records,
    write_records_to_excel,
)
from crawler.sites.tlc import BASE_URL  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("crawl_tlc_all")

OUTPUT_PATH = OUTPUT.output_dir / "tlclighting_all.xlsx"

# So san pham crawl moi xong thi ghi tam ra file 1 lan (xem chu thich o main()).
CHECKPOINT_EVERY = 40


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

    # checkpoint_every=40: ca site ~485 SP chay ~35 phut - neu quota Vertex can
    # hay mang dut o phut thu 30 thi cach ghi-1-lan-o-cuoi mat sach cong da lam.
    # Ghi tam theo moc thi lan chay sau doc lai file, thay ban ghi da OK va bo
    # qua (co che crawl-lai-co-chon-loc san co), tiep tuc dung cho dang do.
    started = time.time()
    records = crawl_product_urls(
        product_urls,
        llm_provider=llm_provider,
        existing=existing,
        workers=CRAWL.workers,
        checkpoint_path=OUTPUT_PATH,
        checkpoint_every=CHECKPOINT_EVERY,
    )
    elapsed = time.time() - started

    write_records_to_excel(records, OUTPUT_PATH)

    ok = sum(1 for r in records if r.crawl_status == CrawlStatus.OK)
    grouped = group_records_by_type(records)
    logger.info("Đã ghi %d bản ghi vào %s (%d OK, %d cần review)",
                len(records), OUTPUT_PATH, ok, len(records) - ok)
    logger.info("Chia thành %d sheet theo loại sản phẩm:", len(grouped))
    for name, group in grouped.items():
        logger.info("  %-45s %3d sản phẩm", name, len(group))
    logger.info(
        "THỜI GIAN: %.1f phút cho %d sản phẩm (%d luồng, %.2f s/sản phẩm)",
        elapsed / 60, len(records), CRAWL.workers, elapsed / max(1, len(records)),
    )


if __name__ == "__main__":
    main()
