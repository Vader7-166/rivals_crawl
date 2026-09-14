#!/usr/bin/env python
"""Chay lai bo trich xuat tren HTML da luu - KHONG fetch, KHONG goi LLM.

    python scripts/reextract.py kingled.com.vn --version v2

Day la thu ma ca kho du lieu sinh ra de phuc vu: sua tang 1.6 xong, chay lai
tren toan bo snapshot roi `scripts/diff_extractions.py` cho biet chinh sua do
va duoc may o va lam hong may o.

Do that: 549 trang KingLED trong 203 giay (370 ms/trang) - nhanh hon mot luot
crawl lai (~35 phut) 10 lan, va ton 0 request mang, 0 quota LLM.
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawler.pipeline import EXTRACTOR_VERSION, rebuild_record_from_html  # noqa: E402
from crawler.store import CrawlStore, connect  # noqa: E402

logger = logging.getLogger("reextract")


def reextract(store: CrawlStore, domain: str, version: str) -> tuple[int, int]:
    """Tra ve (so ban da chay lai, so ban bo qua vi khong co snapshot)."""
    current = store.current_records(domain)
    snapshots = store.latest_snapshots(domain)
    have_html = {url for _, url, _ in snapshots}

    # Ban ghi nhap tu .xlsx cu khong co HTML -> khong chay lai duoc. Bao ro so
    # luong thay vi bao loi: day la trang thai BINH THUONG cho toi khi lan crawl
    # ke tiep lap day kho snapshot.
    skipped = [url for url in current if url not in have_html]

    for order, (snapshot_id, url, html) in enumerate(snapshots, start=1):
        prior = current.get(url)
        record = rebuild_record_from_html(
            url, html, str(order),
            tags=prior.tags if prior else None,
            ma_san_pham_llm=prior.ma_san_pham if prior else None,
            anchor=prior.uu_diem_la_ban if prior else None,
        )
        store.save_extraction(
            record, snapshot_id=snapshot_id, extractor_version=version
        )
        if order % 100 == 0:
            logger.info("... %d/%d", order, len(snapshots))

    return len(snapshots), len(skipped)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain")
    parser.add_argument(
        "--version", default=EXTRACTOR_VERSION,
        help="Nhan phien ban ghi kem ket qua (mac dinh: %(default)s). Dat khac "
             "nhau giua hai lan chay thi moi so sanh duoc.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    conn = connect()
    try:
        done, skipped = reextract(CrawlStore(conn), args.domain, args.version)
    finally:
        conn.close()

    print(f"Đã chạy lại {done} bản ghi với nhãn '{args.version}'.")
    if skipped:
        print(
            f"Bỏ qua {skipped} bản ghi không có HTML lưu lại "
            "(nhập từ .xlsx cũ) — chúng sẽ có snapshot sau lượt crawl kế tiếp."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
