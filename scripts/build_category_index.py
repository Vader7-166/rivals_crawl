#!/usr/bin/env python
"""Dung chi muc danh muc cho 1 domain - tang 0.5, chay TRUOC khi crawl.

    python scripts/build_category_index.py https://kingled.com.vn --refresh-probe
    python scripts/build_category_index.py https://tlclighting.com.vn --limit 5

Duyet cac trang danh muc ma tang 0 tim duoc, thu canh (danh muc <-> san pham).
KHONG fetch trang san pham nao va KHONG goi LLM - day la tang re, chay truoc de
biet crawl gi.

LUU Y ve cache probe: ket qua probe luu TRUOC change `crawl-control-web` khong
co `listing_urls` (truong nay von luon rong). Voi cac domain do phai chay kem
`--refresh-probe` mot lan, neu khong script se bao "khong co trang danh muc nao".
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawler.category_index import build_category_index  # noqa: E402
from crawler.fetch import StealthFetcher  # noqa: E402
from crawler.probing import ProbeCache, probe_domain  # noqa: E402
from crawler.probing.category_crawl import DEFAULT_MAX_PAGES  # noqa: E402
from crawler.sites import get_profile  # noqa: E402
from crawler.store import CategoryStore, CrawlStore, connect  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("build_category_index")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base_url", help="URL gốc của site, vd https://kingled.com.vn")
    parser.add_argument(
        "--refresh-probe", action="store_true",
        help="Dò lại sitemap từ đầu. BẮT BUỘC cho domain đã probe trước khi có "
             "tầng 0.5 — cache cũ không mang trang danh mục.",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Chỉ duyệt N danh mục đầu — chạy thử trước khi duyệt cả site",
    )
    parser.add_argument(
        "--max-pages", type=int, default=DEFAULT_MAX_PAGES,
        help="Trần số trang con cho MỘT danh mục (mặc định %(default)s)",
    )
    parser.add_argument(
        "--rebuild", action="store_true",
        help="Xoá chỉ mục cũ của domain trước khi dựng lại",
    )
    parser.add_argument("--db", type=Path, default=None, help="Đường dẫn kho dữ liệu")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    domain = urlparse(base_url).netloc
    if not domain:
        raise SystemExit(f"base_url không hợp lệ: {args.base_url!r}")

    profile = get_profile(base_url)

    with StealthFetcher() as fetcher:
        probe = probe_domain(base_url, fetcher, cache=ProbeCache(), force=args.refresh_probe)
        logger.info(
            "Probe: strategy=%s, %d URL sản phẩm, %d trang danh mục",
            probe.strategy, len(probe.product_urls), len(probe.listing_urls),
        )

        conn = connect(args.db)
        try:
            crawl_store = CrawlStore(conn)
            crawl_store.ensure_site(base_url, base_url)
            store = CategoryStore(conn)
            if args.rebuild:
                store.clear_domain(domain)

            report = build_category_index(
                store, fetcher, domain,
                listing_urls=probe.listing_urls,
                product_urls=probe.product_urls,
                max_pages=args.max_pages,
                fetch_options=profile.listing_fetch_options,
                limit=args.limit,
            )
        finally:
            conn.close()

    print(f"\n{domain}")
    print(f"  danh mục duyệt được : {report.categories_ok}/{report.categories_total}")
    if report.categories_failed:
        print(f"  danh mục fetch hỏng : {report.categories_failed}")
    print(f"  cạnh thu được       : {report.edges}")
    print(
        f"  độ phủ sản phẩm     : {report.products_indexed}/{report.products_in_sitemap}"
        f" (còn {report.products_uncategorised} chưa xác định danh mục)"
    )
    for warning in report.warnings:
        print(f"  ⚠  {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
