"""Ghi danh sach ProductRecord ra 1 file .xlsx rieng cho 1 site. Task 2.3.

Cot mo phong sat sheet "2. LED Downlight" cua product_Metadata (1).xlsx (da bo
"Gia doi chieu"). Field trang thai crawl noi bo (crawl_status/crawl_error)
KHONG duoc xuat ra cot Excel nao - dung de dam bao khong lam lech khuon cot
tham chieu (xem specs/product-record-schema/spec.md).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook

from .price import LIEN_HE
from .schema import COLUMNS, ProductRecord

SHEET_NAME = "Products"


def _cell_value_for(record: ProductRecord, field_name: str):
    if field_name == "tags":
        return json.dumps(record.tags, ensure_ascii=False) if record.tags else None
    if field_name == "gia":
        value = record.gia
        return value  # float, LIEN_HE (str), hoac None deu ghi thang duoc
    return getattr(record, field_name)


def write_records_to_excel(records: Iterable[ProductRecord], output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME

    headers = [header for header, _ in COLUMNS]
    ws.append(headers)

    row_count = 0
    for record in records:
        row = [_cell_value_for(record, field_name) for _, field_name in COLUMNS]
        ws.append(row)
        row_count += 1

    for col_idx, header in enumerate(headers, start=1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = max(
            12, min(60, len(header) + 4)
        )

    wb.save(output_path)
    return output_path


__all__ = ["write_records_to_excel", "LIEN_HE"]
