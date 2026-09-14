#!/usr/bin/env python
"""Ket xuat file .xlsx cho 1 domain tu kho du lieu - buoc cuoi cua pipeline.

    python scripts/export_excel.py kingled.com.vn

Chay doc lap voi viec crawl: khong co request nao toi site doi thu.
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawler.config import OUTPUT  # noqa: E402
from crawler.store import CrawlStore, connect, export_domain  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain")
    parser.add_argument(
        "-o", "--output",
        help="Đường dẫn file .xlsx (mặc định: <OUTPUT_DIR>/<domain>.xlsx)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    output = Path(args.output) if args.output else OUTPUT.output_dir / f"{args.domain}.xlsx"
    conn = connect()
    try:
        path, review = export_domain(CrawlStore(conn), args.domain, output)
    finally:
        conn.close()

    print(f"Đã ghi {path}")
    if review:
        print(f"{review} sản phẩm cần xử lý tay — xem sheet '⚠ Cần xử lý tay'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
