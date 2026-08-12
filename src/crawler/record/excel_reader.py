"""Doc lai file .xlsx da co cua 1 site de phuc vu crawl lai co chon loc. Task 2.4.

Vi field trang thai crawl khong duoc luu trong file Excel (xem excel_writer),
trang thai duoc SUY RA LAI khi doc: ban ghi thieu 1 trong cac field bat buoc
(REQUIRED_FIELDS) duoc coi la ung vien crawl lai, bat ke ly do ban dau la loi
fetch hay thieu field khi trich xuat.
"""
from __future__ import annotations

import json
from pathlib import Path

from openpyxl import load_workbook

from .price import normalize_price
from .schema import COLUMNS, ProductRecord


def load_existing_records(input_path: str | Path) -> dict[str, ProductRecord]:
    """Doc file .xlsx da co, tra ve map link_san_pham -> ProductRecord (da
    recompute_status()). Tra ve dict rong neu file chua ton tai.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        return {}

    wb = load_workbook(input_path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]

    rows = ws.iter_rows(values_only=True)
    header = next(rows, None)
    if header is None:
        return {}

    expected_headers = [h for h, _ in COLUMNS]
    if list(header) != expected_headers:
        raise ValueError(
            "Header cua file .xlsx hien co khong khop khuon cot mong doi - "
            "co the file thuoc phien ban schema cu hon."
        )

    field_names = [f for _, f in COLUMNS]
    records: dict[str, ProductRecord] = {}
    for row in rows:
        if row is None or all(v is None for v in row):
            continue
        values = dict(zip(field_names, row))
        values["tags"] = json.loads(values["tags"]) if values.get("tags") else {}
        values["gia"] = normalize_price(values.get("gia"))
        record = ProductRecord(**values)
        record.recompute_status()
        key = record.link_san_pham or record.product_id
        records[key] = record

    return records


def records_needing_recrawl(records: dict[str, ProductRecord]) -> list[ProductRecord]:
    """Cac ban ghi co trang thai khac OK - ung vien cho lan crawl lai tiep theo."""
    from .schema import CrawlStatus

    return [r for r in records.values() if r.crawl_status != CrawlStatus.OK]


__all__ = ["load_existing_records", "records_needing_recrawl"]
