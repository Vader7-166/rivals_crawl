#!/usr/bin/env python
"""Nhap cac file .xlsx da xuat truoc day vao kho du lieu (chay mot lan).

    python scripts/import_legacy.py output/*.xlsx

Ban ghi nhap vao khong co HTML kem theo nen khong chay lai trich xuat duoc -
xem store/legacy.py.
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawler.store import CrawlStore, connect, import_xlsx_into_store  # noqa: E402


def main(paths: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    conn = connect()
    store = CrawlStore(conn)
    total = 0
    try:
        for path in paths:
            total += import_xlsx_into_store(path, store)
    finally:
        conn.close()
    print(f"Tổng: {total} bản ghi đã nhập vào kho.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1:]))
