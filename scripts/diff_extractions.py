#!/usr/bin/env python
"""So hai lan chay bo trich xuat TREN CUNG tap snapshot.

    python scripts/diff_extractions.py kingled.com.vn v1 v2

Tra loi dung mot cau hoi, cau hoi ma truoc khi co kho du lieu khong tra loi
duoc: mot chinh sua VA DUOC may o va LAM HONG may o. Chi so sanh cac o cung
snapshot - khac snapshot thi khac biet den tu SITE chu khong phai tu code, va
gop chung vao lam phep so mat nghia.
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawler.store import connect  # noqa: E402
from crawler.store.diff import (  # noqa: E402
    DOI,
    FIELDS,
    HONG,
    VA,
    changes,
    diff,
    versions,
)

# Phan TINH TOAN da chuyen sang `crawler/store/diff.py` de API dung chung mot
# duong (task 7.1). Script nay giu nguyen dau ra nhu truoc - no van la duong
# lui khi tang web khong chay.
_FIELDS = FIELDS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain")
    parser.add_argument("truoc", help="nhãn phiên bản của lần chạy CŨ")
    parser.add_argument("sau", help="nhãn phiên bản của lần chạy MỚI")
    parser.add_argument(
        "--liet-ke", metavar="CỘT", default=None,
        help="In ĐẦY ĐỦ các sản phẩm đổi ở một cột, thay vì vài URL lấy mẫu",
    )
    args = parser.parse_args()

    conn = connect()
    try:
        ket_qua = diff(conn, args.domain, args.truoc, args.sau)
        if ket_qua.message:
            print(ket_qua.message)
            print("\nCác phiên bản đang có:")
            for v in versions(conn, args.domain):
                print(f"  {v.version:12} {v.snapshots} snapshot")
            return 1

        if args.liet_ke:
            for o in changes(conn, args.domain, args.truoc, args.sau,
                             field_name=args.liet_ke):
                print(f"[{o.group}] {o.url}\n    trước: {o.before!r}\n    sau  : {o.after!r}")
            return 0

        print(f"{args.domain}: so sánh trên {ket_qua.shared_snapshots} snapshot chung\n")
        if ket_qua.skipped_without_snapshot:
            # Bao ro chu khong nuot: nguoi doc phai biet phep so nay bo qua bao
            # nhieu ban ghi (task 7.5).
            print(f"(bỏ qua {ket_qua.skipped_without_snapshot} bản ghi không có "
                  f"snapshot — nhập từ .xlsx cũ)\n")
        print(f"{'cột':28} {'vá được':>9} {'làm hỏng':>9} {'đổi khác':>9}")
        print("-" * 58)
        for field_name in _FIELDS:
            c = ket_qua.counts.get(field_name)
            if c:
                print(f"{field_name:28} {c[VA]:>9} {c[HONG]:>9} {c[DOI]:>9}")

        if ket_qua.is_empty:
            print("\nKhông có ô nào đổi.")
            return 0

        print("\nVài URL để soi tay:")
        for field_name in ket_qua.counts:
            for o in changes(conn, args.domain, args.truoc, args.sau,
                             field_name=field_name, limit=3):
                print(f"  [{field_name}] {o.url}")
        print("\nXem đầy đủ một cột: --liet-ke <tên cột>")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
