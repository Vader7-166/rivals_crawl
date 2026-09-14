"""Mo ket noi toi kho du lieu crawl + nen/giai nen HTML.

Chi lo phan HA TANG (ket noi, PRAGMA, dung schema, nen du lieu). Phan doc/ghi
nghiep vu nam o store/crawl_store.py.
"""
from __future__ import annotations

import sqlite3
import zlib
from pathlib import Path
from typing import Optional

from ..config import STORE

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# Muc nen 6 la mac dinh cua zlib. Do that tren fixture: muc 9 chi nho hon ~3%
# nhung cham hon nhieu lan - khong dang khi phai nen ~1500 trang moi lan crawl.
_COMPRESS_LEVEL = 6


def compress_html(html: str) -> tuple[bytes, int]:
    """(bytes da nen, do dai ky tu goc). Do dai goc duoc tra ve kem de luu vao
    `page_snapshots.html_len` - biet duoc kich thuoc that ma khong phai giai
    nen ca blob chi de dem."""
    return zlib.compress(html.encode("utf-8"), _COMPRESS_LEVEL), len(html)


def decompress_html(blob: bytes) -> str:
    return zlib.decompress(blob).decode("utf-8")


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Mo ket noi va dam bao schema da ton tai.

    `journal_mode=WAL` la BAT BUOC chu khong phai toi uu: pipeline chay nhieu
    worker song song, va o che do journal mac dinh (DELETE) mot lan ghi khoa ca
    file khien cac ket noi khac nhan `database is locked`. WAL cho phep doc
    song song voi ghi. Kem theo `busy_timeout` de lan ghi nao roi vao dung luc
    ban thi CHO thay vi that bai ngay.

    Luu y: WAL la thuoc tinh cua CHINH FILE database, giu nguyen giua cac lan
    mo - dat lai moi lan connect() chi de dam bao file moi tao cung co.
    """
    path = Path(db_path) if db_path is not None else STORE.db_path
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, timeout=STORE.busy_timeout_seconds)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={int(STORE.busy_timeout_seconds * 1000)}")
    conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
    # executescript() tu commit va dong transaction dang mo; bat lai foreign_keys
    # vi PRAGMA trong file schema chay trong pham vi script do.
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


__all__ = ["connect", "compress_html", "decompress_html"]
