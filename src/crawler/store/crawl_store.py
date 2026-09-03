"""Doc/ghi nghiep vu tren kho du lieu crawl.

Ranh gioi voi db.py: db.py lo ket noi va nen du lieu, file nay lo viec dich
qua lai giua `ProductRecord` va cac bang.

AN TOAN LUONG: moi ham ghi o day phai duoc goi tu DUY NHAT MOT luong. Trong
`pipeline._crawl_pipelined`, do la main thread - noi fetch tung trang va noi
ham `harvest()` thu hoach ket qua. Worker trong ThreadPoolExecutor chi tinh
toan roi tra ban ghi ve, KHONG cham vao kho du lieu.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Iterable, Optional
from urllib.parse import urlparse

from ..record.price import normalize_price
from ..record.schema import CrawlStatus, ProductRecord
from .db import compress_html, decompress_html

# Cac field cua ProductRecord anh xa 1-1 sang cot cung ten trong `extractions`.
#
# Vang mat co chu dich:
#   - `stt`            : thuoc tinh cua DONG trong file xuat ra, khong phai du
#                        lieu san pham (excel_writer tu danh lai moi lan ghi).
#   - `tags`           : sang bang rieng `product_tags`.
#   - `link_san_pham`  : chinh la cot `url`, khoa dinh danh.
_RECORD_COLUMNS = (
    "product_id",
    "ten_san_pham",
    "ma_san_pham",
    "ma_sap",
    "category_1",
    "category_2",
    "category_3",
    "gia",
    "gia_doi_chieu",
    "link_anh_san_pham",
    "link_mua_hang_online",
    "link_file_hdsd",
    "tom_tat_tskt",
    "thong_so_ky_thuat",
    "vd_hdsd",
    "tom_tat_uu_diem_tinh_nang",
    "noi_dung_uu_diem_sp",
    "uu_diem_nguon",
    "uu_diem_la_ban",
)

# Nhan cua ban ghi nhap tu file .xlsx cu: khong co snapshot nen khong chay lai
# trich xuat duoc.
IMPORTED_VERSION = "imported-xlsx"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _domain_of(url: str) -> str:
    return urlparse(url).netloc


class CrawlStore:
    """Bao mot ket noi SQLite. Khong tu mo/dong ket noi - ben goi quyet dinh
    vong doi (thuong la mot lan crawl / mot lan xuat file)."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    # -- ghi ---------------------------------------------------------------

    def ensure_site(self, url_or_domain: str, base_url: Optional[str] = None) -> str:
        domain = _domain_of(url_or_domain) or url_or_domain
        self._conn.execute(
            "INSERT INTO sites (domain, base_url) VALUES (?, ?) "
            "ON CONFLICT(domain) DO UPDATE SET base_url = COALESCE(?, base_url)",
            (domain, base_url, base_url),
        )
        return domain

    def save_snapshot(self, url: str, fetch_result) -> Optional[int]:
        """Luu HTML cua 1 lan fetch. Tra ve id, hoac None neu khong co gi de luu.

        Duoc goi NGAY SAU khi fetch, TRUOC khi trich xuat: neu tien trinh chet
        giua chung hoac tang 2 no loi, HTML van con de chay lai sau. Do cung la
        ly do luu MOI trang chu khong chi trang trich xuat hong - o sai ma
        tuong dung khong tu khai bao, nen neu chi luu khi hong thi dung ca can
        soi nhat lai la ca khong co du lieu de soi.
        """
        if not getattr(fetch_result, "ok", False) or not getattr(fetch_result, "html", ""):
            return None

        domain = self.ensure_site(url)
        blob, length = compress_html(fetch_result.html)
        cur = self._conn.execute(
            "INSERT INTO page_snapshots "
            "(url, domain, fetched_at, http_status, final_url, html_gz, html_len) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (url, domain, _now(), fetch_result.status,
             getattr(fetch_result, "final_url", None), blob, length),
        )
        self._conn.commit()
        return cur.lastrowid

    def save_extraction(
        self,
        record: ProductRecord,
        *,
        snapshot_id: Optional[int],
        extractor_version: str,
    ) -> int:
        """Luu ket qua 1 lan trich xuat. KHONG ghi de ban truoc do - moi lan
        chay sinh mot dong moi, do la ca diem cua thiet ke (xem design.md muc 2).
        """
        url = record.link_san_pham or ""
        domain = self.ensure_site(url)
        columns = ", ".join(_RECORD_COLUMNS)
        holders = ", ".join("?" for _ in _RECORD_COLUMNS)
        cur = self._conn.execute(
            f"INSERT INTO extractions (url, domain, snapshot_id, extractor_version, "
            f"extracted_at, crawl_status, crawl_error, {columns}) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?, {holders})",
            (url, domain, snapshot_id, extractor_version, _now(),
             record.crawl_status.value, record.crawl_error,
             *(getattr(record, name) for name in _RECORD_COLUMNS)),
        )
        extraction_id = cur.lastrowid
        if record.tags:
            self._conn.executemany(
                "INSERT INTO product_tags (extraction_id, key, value) VALUES (?, ?, ?)",
                [(extraction_id, k, str(v)) for k, v in record.tags.items()],
            )
        self._conn.commit()
        return extraction_id

    # -- doc ---------------------------------------------------------------

    def current_records(self, domain: str) -> dict[str, ProductRecord]:
        """Trang thai hien tai cua 1 domain: url -> ProductRecord.

        Thay the vai tro cua `excel_reader.import_legacy_xlsx` trong co che
        crawl-lai-co-chon-loc. Khac biet quan trong: khong con phu thuoc vao su
        ton tai cua file .xlsx nao ca.
        """
        # ORDER BY id: giu THU TU CHEN, tuc thu tu crawl ban dau. Bo di thi
        # thu tu dong trong file xuat ra khong xac dinh, va cot STT (danh lai
        # theo vi tri dong) doi theo - file moi khong con khop tung o voi file
        # sinh theo duong cu. Vua deterministic vua tai lap duoc ban goc.
        rows = self._conn.execute(
            "SELECT * FROM products WHERE domain = ? ORDER BY id", (domain,)
        ).fetchall()
        tags = self._tags_for({row["id"] for row in rows})
        return {row["url"]: self._to_record(row, tags.get(row["id"], {})) for row in rows}

    def urls_needing_crawl(self, urls: Iterable[str]) -> list[str]:
        """Cac URL chua co ban trich xuat day du - ung vien crawl (lai)."""
        current = {}
        for domain in {_domain_of(u) for u in urls}:
            current.update(self.current_records(domain))
        return [
            url for url in urls
            if not (url in current and current[url].crawl_status == CrawlStatus.OK)
        ]

    def latest_snapshots(self, domain: str) -> list[tuple[int, str, str]]:
        """(snapshot_id, url, html) cua snapshot moi nhat moi URL - dau vao cho
        viec chay lai trich xuat ma khong fetch."""
        rows = self._conn.execute(
            "SELECT id, url, html_gz FROM page_snapshots s WHERE domain = ? "
            "AND id = (SELECT MAX(id) FROM page_snapshots WHERE url = s.url) "
            "ORDER BY url",
            (domain,),
        ).fetchall()
        return [(r["id"], r["url"], decompress_html(r["html_gz"])) for r in rows]

    def snapshot_id_for(self, url: str) -> Optional[int]:
        """Snapshot moi nhat cua 1 URL, None neu chua co (vd ban ghi nhap tu
        file .xlsx cu)."""
        row = self._conn.execute(
            "SELECT MAX(id) AS id FROM page_snapshots WHERE url = ?", (url,)
        ).fetchone()
        return row["id"] if row else None

    def snapshot_html(self, snapshot_id: int) -> Optional[str]:
        row = self._conn.execute(
            "SELECT html_gz FROM page_snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
        return decompress_html(row["html_gz"]) if row else None

    def domains(self) -> list[str]:
        return [r["domain"] for r in self._conn.execute("SELECT domain FROM sites ORDER BY domain")]

    # -- noi bo ------------------------------------------------------------

    def _tags_for(self, extraction_ids: set[int]) -> dict[int, dict[str, str]]:
        if not extraction_ids:
            return {}
        holders = ", ".join("?" for _ in extraction_ids)
        out: dict[int, dict[str, str]] = {}
        # ORDER BY rowid: giu THU TU CHEN, tuc thu tu thuoc tinh xuat hien tren
        # trang nguon. Bo di thi SQLite tra ve theo index (extraction_id, key)
        # tuc theo alphabet, va o `Tags` trong file xuat ra doi noi dung so voi
        # duong ghi cu - du lieu khong sai nhung phep doi chieu "khop tung o"
        # (task 9.1) hong, va thu tu von la thong tin co that (xem quy tac 2 cua
        # prompt: gia tri nhieu muc phai giu nguyen thu tu nguon).
        for row in self._conn.execute(
            f"SELECT extraction_id, key, value FROM product_tags "
            f"WHERE extraction_id IN ({holders}) ORDER BY rowid",
            tuple(extraction_ids),
        ):
            out.setdefault(row["extraction_id"], {})[row["key"]] = row["value"]
        return out

    @staticmethod
    def _to_record(row: sqlite3.Row, tags: dict[str, str]) -> ProductRecord:
        values = {name: row[name] for name in _RECORD_COLUMNS}
        # Gia di qua normalize_price khi doc ra: SQLite tra ve dung kieu da luu
        # (REAL hoac TEXT), nhung ban ghi nhap tu .xlsx cu co the mang chuoi
        # tho - chuan hoa mot lan o day de moi ben nhan duoc dung 3 trang thai.
        values["gia"] = normalize_price(values["gia"])
        values["gia_doi_chieu"] = normalize_price(values["gia_doi_chieu"])
        record = ProductRecord(
            **values,
            link_san_pham=row["url"],
            tags=dict(tags),
            crawl_error=row["crawl_error"],
        )
        record.crawl_status = CrawlStatus(row["crawl_status"])
        return record


__all__ = ["CrawlStore", "IMPORTED_VERSION"]
