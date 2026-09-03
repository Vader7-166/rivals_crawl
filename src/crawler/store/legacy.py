"""Nhap cac file .xlsx da xuat truoc day vao kho du lieu.

Duong DI MOT CHIEU, chay mot lan cho moi file cu. Ban ghi nhap vao mang
`snapshot_id = NULL` va `extractor_version = 'imported-xlsx'`:

  - `snapshot_id = NULL` vi khong co HTML kem theo. Truoc khi co kho du lieu,
    HTML bi vut ngay sau khi trich xuat - 1034 ban ghi da crawl (549 KingLED +
    485 TLC) vi the KHONG chay lai trich xuat duoc. Kho HTML chi bat dau tich
    luy tu lan crawl ke tiep.
  - Nhan phien ban rieng de khong bi nham la ket qua cua mot lan trich xuat
    that trong moi thong ke ve sau.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Optional

from ..record.excel_reader import import_legacy_xlsx as read_xlsx
from .crawl_store import IMPORTED_VERSION, CrawlStore

logger = logging.getLogger(__name__)


def import_xlsx_into_store(
    path: str | Path,
    store: CrawlStore,
    *,
    skip_sheets: Optional[Iterable[str]] = None,
) -> int:
    """Nhap 1 file .xlsx vao kho. Tra ve so ban ghi da nhap.

    `skip_sheets` de bo qua cac sheet khong phai san pham (vd sheet canh bao
    "Cần xử lý tay" do chinh buoc ket xuat sinh ra) - xem excel_reader.
    """
    records = read_xlsx(path, skip_sheets=skip_sheets)
    for record in records.values():
        if not record.link_san_pham:
            continue
        store.save_extraction(
            record, snapshot_id=None, extractor_version=IMPORTED_VERSION
        )
    logger.info("Đã nhập %d bản ghi từ %s", len(records), path)
    return len(records)


__all__ = ["import_xlsx_into_store"]
