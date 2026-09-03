"""Ket xuat tu kho du lieu ra file .xlsx - buoc cuoi cua pipeline.

Khuon 20 cot giu NGUYEN: dung ten (ke ca khoang trang thua cua khuon tham
chieu), dung thu tu, moi loai san pham 1 sheet. `record/schema.py::COLUMNS` van
la lop anh xa duy nhat giua ten sach trong kho va ten cot trong file.

San pham can nguoi xu ly tay xuat hien o CA HAI cho:
  - sheet danh muc: 2 o uu diem DE TRONG (de trong moi dung - khong bia du
    lieu), file van la ban giao nop hoan chinh ghep thang duoc vao khuon.
  - sheet canh bao: kem toan van text trang + duong dan file .html nguyen ban.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path
from typing import Optional

from ..llm.html_cleaner import page_text
from ..record import ProductRecord, write_records_to_excel
from .crawl_store import IMPORTED_VERSION, CrawlStore

logger = logging.getLogger(__name__)

# Text toan trang duoc cat o day truoc khi vao o. Do that: text da don cua mot
# trang la 6.244-16.582 ky tu nen hau het lot thoai mai, nhung co ngoai le -
# `kingled_product.html` (ban CHUA render) cho ra 691.236 ky tu vi mang mot khoi
# du lieu lon khong nam trong <script>. Nguong nay vi the la bat buoc, khong
# phai phong xa.
_MAX_PAGE_TEXT = 30_000
_CUT_MARK = "\n[… đã cắt — mở file .html đính kèm để xem đầy đủ]"

_LY_DO_KHONG_TIM_THAY = "Không tìm thấy mục ưu điểm nào trên trang"
_LY_DO_CHUA_CO_HTML = "Chưa có HTML lưu lại (bản ghi nhập từ file .xlsx cũ)"
_LY_DO_DO_TIN_THAP = (
    "Lấy bằng nhánh cụm đề mục — đúng hình dạng nhưng không có tín hiệu nào "
    "xác nhận đây là mục ưu điểm, cần soi lại"
)


def _slug(url: str) -> str:
    """Ten file .html tu URL. Giu duoi cung cua duong dan vi do la phan phan
    biet san pham; ca URL thi qua dai cho ten file."""
    tail = url.rstrip("/").rsplit("/", 1)[-1] or "index"
    tail = unicodedata.normalize("NFKD", tail).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9._-]+", "-", tail)[:100] or "trang"


def _needs_review(record: ProductRecord) -> Optional[str]:
    """Ly do can xu ly tay, None neu khong can."""
    empty = not record.tom_tat_uu_diem_tinh_nang and not record.noi_dung_uu_diem_sp
    if empty:
        return _LY_DO_KHONG_TIM_THAY
    if record.uu_diem_nguon == "cluster":
        return _LY_DO_DO_TIN_THAP
    return None


def export_domain(
    store: CrawlStore,
    domain: str,
    output_path: str | Path,
    *,
    html_dir: Optional[Path] = None,
) -> tuple[Path, int]:
    """Ghi file .xlsx cho 1 domain. Tra ve (duong dan file, so dong canh bao).

    `html_dir` mac dinh la `<ten file>_html/` canh chinh file .xlsx.
    """
    output_path = Path(output_path)
    html_dir = html_dir or output_path.with_name(output_path.stem + "_html")

    # `current_records` tra ve theo thu tu chen (= thu tu crawl); giu nguyen
    # thay vi sap xep lai, de file sinh ra khop tung o voi duong ghi cu.
    ordered = list(store.current_records(domain).values())

    review_rows = []
    for record in ordered:
        reason = _needs_review(record)
        if reason is None:
            continue
        url = record.link_san_pham or ""
        snapshot_id = store.snapshot_id_for(url)
        if snapshot_id is None:
            # Nhap tu file cu: khong co HTML nen khong co text lan file dinh
            # kem. Van len sheet canh bao - viec van can lam, chi la chua co
            # nguyen lieu (se co sau luot crawl ke tiep).
            review_rows.append([url, _LY_DO_CHUA_CO_HTML, None, None])
            continue

        html = store.snapshot_html(snapshot_id) or ""
        text = page_text(html)
        if len(text) > _MAX_PAGE_TEXT:
            text = text[:_MAX_PAGE_TEXT] + _CUT_MARK

        html_dir.mkdir(parents=True, exist_ok=True)
        html_file = html_dir / f"{_slug(url)}.html"
        html_file.write_text(html, encoding="utf-8")
        review_rows.append([url, reason, text, str(html_file.relative_to(output_path.parent))])

    write_records_to_excel(ordered, output_path, review_rows=review_rows)
    logger.info(
        "Đã ghi %d sản phẩm ra %s (%d dòng cần xử lý tay)",
        len(ordered), output_path, len(review_rows),
    )
    return output_path, len(review_rows)


__all__ = ["export_domain", "IMPORTED_VERSION"]
