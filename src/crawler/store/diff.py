"""So hai lan chay bo trich xuat TREN CUNG tap snapshot (capability
`extraction-diff-view`).

Tra loi dung mot cau hoi, cau hoi ma truoc khi co kho du lieu khong tra loi
duoc: mot chinh sua VA DUOC may o va LAM HONG may o.

Chi so cac o CUNG SNAPSHOT. Khac snapshot thi khac biet den tu SITE chu khong
phai tu code cua minh, va gop chung vao lam phep so mat het nghia - do cung la
ly do kho du lieu tach `page_snapshots` khoi `extractions` ngay tu dau.

File nay la phan TINH TOAN, dung chung cho CLI (`scripts/diff_extractions.py`)
lan API. Truoc day no nam trong chinh script, nen tang web muon dung lai thi
phai chep - va hai ban chep se lech nhau.
"""
from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

# Cac cot dang quan tam. Hai cot uu diem dat truoc vi do la ly do chinh cua
# viec so sanh nay.
FIELDS: tuple[str, ...] = (
    "tom_tat_uu_diem_tinh_nang",
    "noi_dung_uu_diem_sp",
    "uu_diem_nguon",
    "gia",
    "ma_san_pham",
    "thong_so_ky_thuat",
    "category_1",
    "ten_san_pham",
)

# Ba nhom thay doi. Tach rieng vi y nghia khac han nhau, va chinh su tach nay
# la cai tra loi duoc "sua vua roi lai hay hai".
VA = "va"      # truoc trong, sau co    -> lay them duoc du lieu
HONG = "hong"  # truoc co, sau trong    -> LAM MAT du lieu dang dung
DOI = "doi"    # ca hai deu co, khac nhau -> phai mo tay xem ben nao dung


@dataclass
class VersionInfo:
    version: str
    snapshots: int


@dataclass
class CellChange:
    url: str
    field: str
    group: str
    before: Optional[str]
    after: Optional[str]


@dataclass
class DiffResult:
    domain: str
    before: str
    after: str
    shared_snapshots: int
    counts: dict[str, Counter] = field(default_factory=dict)
    # Ban ghi khong co snapshot (nhap tu .xlsx cu) KHONG so duoc. Bao ro so
    # luong chu khong nuot: nguoi doc phai biet phep so nay bo qua bao nhieu.
    skipped_without_snapshot: int = 0
    message: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        return not self.counts


def versions(conn: sqlite3.Connection, domain: str) -> list[VersionInfo]:
    """Cac nhan phien ban da co cua mot domain, kem so snapshot moi ban."""
    return [
        VersionInfo(version=r["extractor_version"], snapshots=r["n"])
        for r in conn.execute(
            "SELECT extractor_version, COUNT(DISTINCT snapshot_id) AS n "
            "FROM extractions WHERE domain = ? AND snapshot_id IS NOT NULL "
            "GROUP BY extractor_version ORDER BY extractor_version",
            (domain,),
        )
    ]


def _rows(conn: sqlite3.Connection, domain: str, version: str) -> dict[tuple, sqlite3.Row]:
    """Ban trich xuat MOI NHAT cua tung snapshot o mot phien ban.

    Moi nhat chu khong phai dau tien: chay lai cung mot phien ban (vd sua xong
    chay lai `v7`) thi ban sau moi la ban dang dung.
    """
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


def _group(before, after) -> Optional[str]:
    if before == after:
        return None
    if before is None or before == "":
        return VA
    if after is None or after == "":
        return HONG
    return DOI


def tally(old: dict, new: dict, fields: tuple[str, ...] = FIELDS) -> dict[str, Counter]:
    """Dem thay doi tren cac khoa CO MAT O CA HAI ben."""
    out: dict[str, Counter] = {}
    for key in set(old) & set(new):
        for name in fields:
            nhom = _group(old[key][name], new[key][name])
            if nhom is not None:
                out.setdefault(name, Counter())[nhom] += 1
    return out


def diff(
    conn: sqlite3.Connection,
    domain: str,
    before: str,
    after: str,
    *,
    fields: tuple[str, ...] = FIELDS,
) -> DiffResult:
    """Bang dem ba nhom theo tung cot, kem so snapshot chung."""
    old, new = _rows(conn, domain, before), _rows(conn, domain, after)
    chung = set(old) & set(new)

    bo_qua = conn.execute(
        "SELECT COUNT(*) AS n FROM extractions WHERE domain = ? AND snapshot_id IS NULL",
        (domain,),
    ).fetchone()["n"]

    if not chung:
        # KHONG tra bang rong: bang rong doc thanh "khong co gi doi", trong khi
        # su that la "phep so nay khong hop le". Chi ro cach tao mot phep so
        # hop le thay vi de nguoi dung tu doan (task 7.4).
        return DiffResult(
            domain=domain, before=before, after=after, shared_snapshots=0,
            skipped_without_snapshot=bo_qua,
            message=(
                f"Không có snapshot nào chạy bằng cả “{before}” lẫn “{after}”. "
                f"Hai phiên bản chỉ so được khi cùng chạy trên một snapshot — "
                f"chạy lại trích xuất cho “{after}” trên chính tập snapshot của "
                f"“{before}” (scripts/reextract.py {domain} --version {after})."
            ),
        )

    return DiffResult(
        domain=domain, before=before, after=after, shared_snapshots=len(chung),
        counts=tally({k: old[k] for k in chung}, {k: new[k] for k in chung}, fields),
        skipped_without_snapshot=bo_qua,
    )


def changes(
    conn: sqlite3.Connection,
    domain: str,
    before: str,
    after: str,
    *,
    field_name: str,
    group: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[CellChange]:
    """DANH SACH DAY DU san pham cua mot nhom thay doi.

    CLI in vai URL lam mau; o day khong gioi han mac dinh (task 7.6) - "vá được
    47 ô" ma chi xem duoc 3 thi con 44 o kia van phai mo SQLite ra tra tay,
    dung cai ma ca man so sanh sinh ra de khoi phai lam.
    """
    old, new = _rows(conn, domain, before), _rows(conn, domain, after)
    ra: list[CellChange] = []
    for key in sorted(set(old) & set(new), key=lambda k: k[1]):
        truoc, sau = old[key][field_name], new[key][field_name]
        nhom = _group(truoc, sau)
        if nhom is None or (group is not None and nhom != group):
            continue
        ra.append(CellChange(url=key[1], field=field_name, group=nhom,
                             before=truoc, after=sau))
        if limit is not None and len(ra) >= limit:
            break
    return ra


__all__ = [
    "DOI", "FIELDS", "HONG", "VA",
    "CellChange", "DiffResult", "VersionInfo",
    "changes", "diff", "tally", "versions",
]
