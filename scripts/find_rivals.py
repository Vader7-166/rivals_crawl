#!/usr/bin/env python
"""Tìm site LED của đối thủ bằng bộ máy tìm kiếm.

    python scripts/find_rivals.py                       # tìm đối thủ mới
    python scripts/find_rivals.py --top 5
    python scripts/find_rivals.py --tu-khoa "đèn led panel" "đèn pha led"
    python scripts/find_rivals.py --tim-lai Duhal       # site cũ chết/đổi?

Trả về top N ứng viên kèm ĐIỂM và LÝ DO từng tín hiệu. Không tự thêm domain nào
vào registry: người đọc quyết định, y như màn xác nhận phạm vi — khớp trượt thì
bỏ qua, giá sửa bằng một lần đọc.

Từ khoá mặc định dựng từ chính tên danh mục trong kho (từ vựng thật của ngành,
do đối thủ viết). Nếu kho rỗng thì dùng danh sách mặc định trong
`crawler/discovery/queries.py`.
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawler.config import STORE  # noqa: E402
from crawler.discovery import tim_doi_thu, tim_lai_site, tu_danh_muc  # noqa: E402
from crawler.store import CrawlStore  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def _ten_danh_muc_trong_kho() -> list[str]:
    """Tên danh mục đã crawl — từ vựng để dựng truy vấn.

    Kho chưa có gì thì trả rỗng và tầng dưới tự dùng danh sách mặc định. Đây là
    trạng thái BÌNH THƯỜNG ở lần chạy đầu, không phải lỗi.
    """
    if not STORE.db_path.exists():
        return []
    conn = sqlite3.connect(f"file:{STORE.db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [ten for _, ten, _ in CrawlStore(conn).category_counts()]
    finally:
        conn.close()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--top", type=int, default=3, help="Số ứng viên trả về (mặc định 3)")
    p.add_argument("--tu-khoa", nargs="*", default=None,
                   help="Tự chỉ định truy vấn, thay cho việc dựng từ danh mục trong kho")
    p.add_argument("--tim-lai", metavar="NHÃN", default=None,
                   help="Tìm lại địa chỉ mới của một nhãn đã biết (domain cũ chết/đổi)")
    p.add_argument("--khong-tai-trang", action="store_true",
                   help="Không tải trang chủ để chấm điểm — nhanh hơn, kém chính xác hơn")
    args = p.parse_args()

    tai_trang = not args.khong_tai_trang
    if args.tim_lai:
        kq = tim_lai_site(args.tim_lai, top=args.top, tai_trang=tai_trang)
        print(f"Tìm lại site của nhãn “{args.tim_lai}”")
    else:
        tu_khoa = args.tu_khoa or tu_danh_muc(_ten_danh_muc_trong_kho())
        kq = tim_doi_thu(truy_van=list(tu_khoa), top=args.top, tai_trang=tai_trang)
        print("Tìm đối thủ LED mới")

    print("Truy vấn đã dùng:")
    for q in kq.truy_van:
        print(f"  · {q}")

    if not kq.ung_vien:
        print("\nKhông có ứng viên nào. Nếu điều này lặp lại, nhiều khả năng bộ máy "
              "tìm kiếm đang chặn — xem log cảnh báo ở trên.")
        return 1

    print(f"\n=== TOP {len(kq.ung_vien)} ===")
    for i, uv in enumerate(kq.ung_vien, start=1):
        dau = "   ← ĐÃ CÓ trong registry" if uv.da_dang_ky else ""
        print(f"\n{i}. {uv.domain}  ({uv.diem} điểm){dau}")
        if uv.title:
            print(f"   {uv.title[:78]}")
        for t in uv.tin_hieu:
            print(f"     {t.diem:+d}  {t.ly_do}")

    if kq.da_loai:
        print(f"\nĐã loại thẳng ({len(kq.da_loai)}):")
        for domain, ly_do in kq.da_loai:
            print(f"  {domain:<28} {ly_do}")

    print(
        "\nKhông domain nào được thêm tự động. Muốn crawl thử một ứng viên:\n"
        "  .venv/bin/python scripts/crawl_site.py https://<domain> --limit 15\n"
        "rồi soi bằng scripts/report_crawl.py TRƯỚC khi chạy cả site."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
