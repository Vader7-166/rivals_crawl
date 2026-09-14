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
import os
import re
import unicodedata
from pathlib import Path
from typing import Optional

from ..config import OUTPUT
from ..llm.html_cleaner import page_text
from ..record import ProductRecord, write_records_to_excel
from ..record.excel_writer import group_records_by_type
from ..sites.registry import brand_of
from ..record.schema import CrawlStatus
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

    `html_dir` mac dinh la `<OUTPUT.html_dir>/<ten file>_html/` - THU MUC RIENG,
    khong nam canh file .xlsx. Do tren 12 site: dong HTML nay nang 244 MB, gap
    hon 100 lan tong so file .xlsx; de chung mot cho thi thu muc ket qua khong
    con mo ra doc duoc.
    """
    output_path = Path(output_path)
    html_dir = html_dir or (OUTPUT.html_dir / (output_path.stem + "_html"))

    # `current_records` tra ve theo thu tu chen (= thu tu crawl); giu nguyen
    # thay vi sap xep lai, de file sinh ra khop tung o voi duong ghi cu.
    everything = list(store.current_records(domain).values())

    # Trang khong phai san pham (bai viet, trang giai phap - site tu khai qua
    # breadcrumb) KHONG di vao file ket qua. Chung van nam nguyen trong kho:
    # ban ghi va snapshot deu con, nen doi y thi chi phai xuat lai, khong phai
    # crawl lai.
    ordered = [r for r in everything if r.crawl_status != CrawlStatus.NOT_A_PRODUCT]
    bo_qua = len(everything) - len(ordered)

    review_rows = []
    for record in ordered:
        reason = _needs_review(record)
        if reason is not None:
            review_rows.append(_review_row(store, record, reason, html_dir, output_path))

    write_records_to_excel(ordered, output_path, review_rows=review_rows)
    logger.info(
        "Đã ghi %d sản phẩm ra %s (%d dòng cần xử lý tay%s)",
        len(ordered), output_path, len(review_rows),
        f", bỏ {bo_qua} trang không phải sản phẩm" if bo_qua else "",
    )
    return output_path, len(review_rows)


def _review_row(
    store: CrawlStore,
    record: ProductRecord,
    reason: str,
    html_dir: Path,
    output_path: Path,
) -> list:
    """Mot dong cua sheet canh bao, kem text trang va file .html dinh kem.

    Tach ra khoi `export_domain` de duong xuat theo tap chon dung LAI dung logic
    nay qua nhieu domain (task 6.4), thay vi chep mot ban co the lech.
    """
    url = record.link_san_pham or ""
    snapshot_id = store.snapshot_id_for(url)
    if snapshot_id is None:
        # Nhap tu file cu: khong co HTML nen khong co text lan file dinh kem.
        # Van len sheet canh bao - viec van can lam, chi la chua co nguyen lieu.
        return [url, _LY_DO_CHUA_CO_HTML, None, None]

    html = store.snapshot_html(snapshot_id) or ""
    text = page_text(html)
    if len(text) > _MAX_PAGE_TEXT:
        text = text[:_MAX_PAGE_TEXT] + _CUT_MARK

    html_dir.mkdir(parents=True, exist_ok=True)
    html_file = html_dir / f"{_slug(url)}.html"
    html_file.write_text(html, encoding="utf-8")
    # `os.path.relpath` chu khong phai `Path.relative_to`: thu muc HTML nam
    # NGOAI thu muc .xlsx, va `relative_to` nem loi khi duong dan khong phai con
    # chau. Ket qua la duong dan kieu `../html/<domain>_html/x.html` - van mo
    # duoc bang cach bam tu chinh file .xlsx.
    return [
        url, reason, text,
        os.path.relpath(html_file.resolve(), output_path.parent.resolve()),
    ]


def export_selection(
    store: CrawlStore,
    urls_by_domain: dict[str, list[str]],
    output_path: str | Path,
    *,
    keyword: Optional[str] = None,
    sheet_by_brand: bool = True,
    brand_order: Optional[list[str]] = None,
    html_dir: Optional[Path] = None,
) -> tuple[Path, int]:
    """Ghi .xlsx cho mot tap chon CAT NGANG nhieu domain. Tra ve (file, so dong
    canh bao).

    Khac `export_domain()` o dung mot chieu: tap ban ghi den tu nhieu doi thu.
    Khuon 20 cot GIU NGUYEN TUYET DOI; chieu phan loai moi chi duoc phep nam o
    ten file va ten sheet (spec `excel-export-selection`).

    `sheet_by_brand`:
        True  - moi doi thu mot sheet. Dung cho pham vi DANH MUC ("đèn âm trần
                của các đối thủ"): nguoi doc dang so hang cua minh voi hang cua
                tung doi thu, nen ranh gioi ho can la doi thu.
        False - chia theo loai san pham nhu duong xuat theo domain. Dung cho
                pham vi MOT NHAN HIEU: moi ban ghi cung mot doi thu thi chia
                theo doi thu ra dung mot sheet khong loi ich gi.

    `brand_order` la thu hang do nguoi dung chi dinh. De trong thi xep theo SO
    SAN PHAM giam dan - mot so do that, khong phai mot phan doan. Thu tu sheet
    chinh la thu hang, doc duoc bang cach mo file, va khong ton cot nao trong
    khuon 20 cot (design.md muc 3).
    """
    output_path = Path(output_path)
    html_dir = html_dir or (OUTPUT.html_dir / (output_path.stem + "_html"))

    # Gom ban ghi theo domain, giu dung thu tu chen cua kho (= thu tu crawl).
    theo_domain: dict[str, list[ProductRecord]] = {}
    for domain, urls in urls_by_domain.items():
        muon = set(urls)
        theo_domain[domain] = [
            r for url, r in store.current_records(domain).items()
            if url in muon and r.crawl_status != CrawlStatus.NOT_A_PRODUCT
        ]

    xep = brand_order or sorted(
        theo_domain, key=lambda d: len(theo_domain[d]), reverse=True
    )
    # Domain co du lieu nhung khong duoc goi ten trong `brand_order` van phai ra
    # file - bo im lang thi nguoi dung mat du lieu vi mot thu tu hien thi.
    xep = xep + [d for d in theo_domain if d not in xep]

    nhom: dict[str, list[ProductRecord]] = {}
    for domain in xep:
        ban_ghi = theo_domain.get(domain, [])
        if not ban_ghi:
            continue
        if sheet_by_brand:
            nhom[brand_of(domain)] = ban_ghi
        else:
            for ten, cua_nhom in group_records_by_type(ban_ghi).items():
                nhom.setdefault(ten, []).extend(cua_nhom)

    tat_ca = [r for ban_ghi in nhom.values() for r in ban_ghi]
    review_rows = []
    for record in tat_ca:
        reason = _needs_review(record)
        if reason is not None:
            review_rows.append(_review_row(store, record, reason, html_dir, output_path))

    write_records_to_excel(tat_ca, output_path, review_rows=review_rows, grouped=nhom)
    logger.info(
        "Đã ghi %d sản phẩm của %d đối thủ ra %s (%d dòng cần xử lý tay)%s",
        len(tat_ca), len(nhom), output_path, len(review_rows),
        f" — từ khoá “{keyword}”" if keyword else "",
    )
    return output_path, len(review_rows)


__all__ = ["export_domain", "export_selection", "IMPORTED_VERSION"]
