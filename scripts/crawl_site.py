"""Crawl TOÀN BỘ sản phẩm của MỘT đối thủ bất kỳ - dùng chung cho mọi site.

    .venv/bin/python scripts/crawl_site.py https://kingled.com.vn
    .venv/bin/python scripts/crawl_site.py https://kingled.com.vn --limit 15
    .venv/bin/python scripts/crawl_site.py https://x.vn --output output/x.xlsx

Thêm một đối thủ mới KHÔNG cần thêm file .py nào: site probing tự tìm nguồn URL
sản phẩm, tầng 1 đọc structured data, tầng 2 chuẩn hoá thông số. Nếu đo trên
trang thật mà thấy thiếu thì thêm MỘT DÒNG dữ liệu vào registry theo domain
(`crawler/sites/registry.py` cho khâu tìm/tải trang, `crawler/extraction/
css_fallback.py` cho khâu đọc nội dung) - vẫn không phải viết module mới.

Kết quả ghi vào 1 file .xlsx, MỖI LOẠI SẢN PHẨM 1 SHEET (chia theo `category 1`
của chính site nguồn - xem record/excel_writer.py). Chạy lại lần sau chỉ crawl
những bản ghi lỗi/thiếu field, không fetch lại và không gọi lại LLM cho bản ghi
đã OK.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawler.config import CRAWL, OUTPUT  # noqa: E402
from crawler.fetch import StealthFetcher  # noqa: E402
from crawler.llm import LLMProviderError, build_default_llm_provider  # noqa: E402
from crawler.pipeline import crawl_product_urls  # noqa: E402
from crawler.probing import ProbeCache, probe_domain  # noqa: E402
from crawler.record import (  # noqa: E402
    CrawlStatus,
    group_records_by_type,
    import_legacy_xlsx,
    write_records_to_excel,
)
from crawler.sites import get_profile, select_product_urls  # noqa: E402
from crawler.store import CrawlStore, connect  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("crawl_site")

# Cả site vài trăm sản phẩm chạy hàng chục phút; ghi tạm theo mốc để mất điện /
# cạn quota giữa chừng không xoá sạch tiến độ (xem pipeline.crawl_product_urls).
CHECKPOINT_EVERY = 40


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base_url", help="URL gốc của site đối thủ, vd https://kingled.com.vn")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Chỉ crawl N sản phẩm đầu - dùng để chạy thử trước khi chạy cả site",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Đường dẫn file .xlsx (mặc định output/<domain>.xlsx)",
    )
    parser.add_argument(
        "--refresh-probe", action="store_true",
        help="Bỏ qua cache site-probing và dò lại từ đầu",
    )
    parser.add_argument(
        "--db", type=Path, default=None,
        help="Đường dẫn kho dữ liệu (mặc định theo CRAWL_DB_PATH). HTML và kết "
             "quả trích xuất được ghi vào đây SONG SONG với file .xlsx.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Crawl lại CẢ bản ghi đã OK. Dùng khi thứ cần là HTML chứ không "
             "phải bản ghi - vd 549 bản ghi KingLED nhập từ .xlsx cũ đều OK "
             "nên không bao giờ được crawl lại, mà thiếu HTML thì mỗi lần sửa "
             "bộ trích xuất về sau KingLED đều đứng ngoài.",
    )
    parser.add_argument(
        "--no-store", action="store_true",
        help="Không ghi kho dữ liệu, chỉ ghi .xlsx như trước khi có kho",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    domain = urlparse(base_url).netloc
    if not domain:
        raise SystemExit(f"base_url không hợp lệ: {args.base_url!r}")

    output_path = args.output or OUTPUT.output_dir / f"{domain}.xlsx"
    profile = get_profile(base_url)

    try:
        llm_provider = build_default_llm_provider()
    except LLMProviderError as exc:
        logger.error("Không thể khởi tạo LLM provider: %s", exc)
        raise SystemExit(1)

    with StealthFetcher() as fetcher:
        probe = probe_domain(base_url, fetcher, cache=ProbeCache(), force=args.refresh_probe)
        logger.info(
            "Site probing: strategy=%s reliability=%s sitemap=%s",
            probe.strategy, probe.reliability_score, probe.sitemap_url,
        )
        product_urls = select_product_urls(probe.product_urls, base_url)
        skipped = len(probe.product_urls) - len(product_urls)
        if skipped:
            logger.info("Bỏ %d mục trong sitemap (trùng lặp / không phải trang sản phẩm)", skipped)

    if not product_urls:
        logger.error(
            "Probe không trả về URL sản phẩm nào cho %s - dừng. "
            "Kiểm tra site có sitemap không, hoặc chạy lại với --refresh-probe.", domain,
        )
        raise SystemExit(1)

    if args.limit:
        product_urls = product_urls[: args.limit]
    logger.info("Sẽ crawl %d URL sản phẩm của %s", len(product_urls), domain)
    if profile.fetch_options:
        logger.info("Tuỳ chọn fetch riêng của domain: %s", profile.fetch_options)

    # GHI HAI ĐƯỜNG trong giai đoạn chuyển tiếp: kho dữ liệu (mới) và file
    # .xlsx (cũ). Chủ đích là để đối chiếu - file sinh từ kho phải khớp từng ô
    # với file sinh theo đường cũ trước khi bỏ đường cũ đi (design.md,
    # Migration Plan bước 3).
    conn = None if args.no_store else connect(args.db)
    store = CrawlStore(conn) if conn is not None else None
    if store is not None:
        store.ensure_site(base_url, base_url)
        da_co = store.current_records(domain)
        if da_co:
            logger.info(
                "Kho dữ liệu đã có %d bản ghi của %s (bản ghi OK sẽ không crawl lại)",
                len(da_co), domain,
            )

    # Co kho -> pipeline tu lay trang thai tu do. Khong co kho (--no-store) thi
    # van doc nguoc .xlsx nhu duong cu, de co che crawl-lai-co-chon-loc khong
    # bien mat am tham cung voi cai co.
    existing = None if store is not None else import_legacy_xlsx(output_path)
    if existing:
        logger.info("Dataset trước đó: %d bản ghi (bản ghi OK sẽ không crawl lại)", len(existing))

    started = time.time()
    try:
        records = crawl_product_urls(
            product_urls,
            llm_provider=llm_provider,
            existing=existing,
            workers=CRAWL.workers,
            checkpoint_path=output_path,
            checkpoint_every=CHECKPOINT_EVERY,
            force=args.force,
            fetch_options=profile.fetch_options,
            store=store,
        )
    finally:
        if conn is not None:
            conn.close()
    elapsed = time.time() - started

    write_records_to_excel(records, output_path)

    ok = sum(1 for r in records if r.crawl_status == CrawlStatus.OK)
    grouped = group_records_by_type(records)
    logger.info("Đã ghi %d bản ghi vào %s (%d OK, %d cần review)",
                len(records), output_path, ok, len(records) - ok)
    logger.info("Chia thành %d sheet theo loại sản phẩm:", len(grouped))
    for name, group in grouped.items():
        logger.info("  %-45s %3d sản phẩm", name, len(group))
    logger.info(
        "THỜI GIAN: %.1f phút cho %d sản phẩm (%d luồng, %.2f s/sản phẩm)",
        elapsed / 60, len(records), CRAWL.workers, elapsed / max(1, len(records)),
    )


if __name__ == "__main__":
    main()
