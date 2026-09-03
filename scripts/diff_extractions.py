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

# Cac cot dang quan tam. Hai cot uu diem dat truoc vi do la ly do chinh cua
# viec so sanh nay.
_FIELDS = (
    "tom_tat_uu_diem_tinh_nang",
    "noi_dung_uu_diem_sp",
    "uu_diem_nguon",
    "gia",
    "ma_san_pham",
    "thong_so_ky_thuat",
)


def _rows(conn, domain, version):
    return {
        (r["snapshot_id"], r["url"]): r
        for r in conn.execute(
            "SELECT * FROM extractions e WHERE domain = ? AND extractor_version = ? "
            "AND snapshot_id IS NOT NULL "
            "AND id = (SELECT MAX(id) FROM extractions WHERE snapshot_id = e.snapshot_id "
            "          AND extractor_version = e.extractor_version)",
            (domain, version),
        )
    }


def tally(old: dict, new: dict, fields=_FIELDS) -> dict[str, Counter]:
    """Dem thay doi tren cac khoa CO MAT O CA HAI ben.

    Ba nhom tach rieng vi y nghia khac han nhau:
      va    : truoc trong, sau co    -> chinh sua lay them duoc du lieu
      hong  : truoc co, sau trong    -> chinh sua LAM MAT du lieu dang dung
      doi   : ca hai deu co, gia tri khac -> can mo tay xem ben nao dung
    """
    out: dict[str, Counter] = {}
    for key in set(old) & set(new):
        for field in fields:
            before, after = old[key][field], new[key][field]
            if before == after:
                continue
            bucket = out.setdefault(field, Counter())
            if before is None:
                bucket["va"] += 1
            elif after is None:
                bucket["hong"] += 1
            else:
                bucket["doi"] += 1
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain")
    parser.add_argument("truoc", help="nhãn phiên bản của lần chạy CŨ")
    parser.add_argument("sau", help="nhãn phiên bản của lần chạy MỚI")
    args = parser.parse_args()

    conn = connect()
    try:
        old = _rows(conn, args.domain, args.truoc)
        new = _rows(conn, args.domain, args.sau)
    finally:
        conn.close()

    shared = sorted(set(old) & set(new))
    if not shared:
        print(
            f"Không có snapshot nào chạy bằng CẢ '{args.truoc}' lẫn '{args.sau}'.\n"
            "Chạy scripts/reextract.py với --version khác nhau cho hai lượt."
        )
        return 1

    print(f"{args.domain}: so sánh trên {len(shared)} snapshot chung\n")
    print(f"{'cột':28} {'vá được':>9} {'làm hỏng':>9} {'đổi khác':>9}")
    print("-" * 58)

    counts = tally({k: old[k] for k in shared}, {k: new[k] for k in shared})
    changed_examples: dict[str, list[str]] = {}
    for key in shared:
        for field in counts:
            if old[key][field] != new[key][field] and old[key][field] is not None:
                changed_examples.setdefault(field, []).append(key[1])
    for field in _FIELDS:
        if field in counts:
            c = counts[field]
            print(f"{field:28} {c['va']:>9} {c['hong']:>9} {c['doi']:>9}")

    if not changed_examples:
        print("\nKhông có ô nào đổi.")
        return 0

    print("\nVài URL để soi tay:")
    for field, urls in changed_examples.items():
        for url in urls[:3]:
            print(f"  [{field}] {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
