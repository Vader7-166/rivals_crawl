"""Model ban ghi san pham chuan (product-record-schema). Task 2.1.

Khuon field dua theo `product_Metadata (1).xlsx` (sheet "2. LED Downlight"), da
bo cot "Gia doi chieu" va coi Ma SAP / Link mua hang online / Link file HDSD la
optional (xem specs/product-record-schema/spec.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .price import PriceValue


class CrawlStatus(str, Enum):
    """Trang thai crawl noi bo - KHONG xuat ra cot Excel (xem excel_writer)."""

    OK = "ok"
    ERROR = "error"
    PARTIAL_MISSING_FIELDS = "partial-missing-fields"


# (ten cot trong file Excel xuat ra, ten field tren ProductRecord) - dung thu tu
# nay lam thu tu cot khi ghi/doc file .xlsx.
COLUMNS: list[tuple[str, str]] = [
    ("Product_ID", "product_id"),
    ("Tên sản phẩm", "ten_san_pham"),
    ("Mã Sản Phẩm", "ma_san_pham"),
    ("Mã SAP", "ma_sap"),
    ("category 1", "category_1"),
    ("category 2", "category_2"),
    ("category 3", "category_3"),
    ("Tags", "tags"),
    ("Giá", "gia"),
    ("Link sản phẩm", "link_san_pham"),
    ("Link ảnh sản phẩm", "link_anh_san_pham"),
    ("Link mua hàng online", "link_mua_hang_online"),
    ("Tóm tắt TSKT", "tom_tat_tskt"),
    ("Tóm tắt ưu điểm, tính năng", "tom_tat_uu_diem_tinh_nang"),
    ("Thông số kỹ thuật", "thong_so_ky_thuat"),
    ("Link file HDSD", "link_file_hdsd"),
    ("Nội dung Ưu điểm SP", "noi_dung_uu_diem_sp"),
]

# Field duoc phep null ma KHONG bi coi la crawl loi/thieu sot (spec: "Field
# optional theo tung site").
OPTIONAL_FIELDS = frozenset({"ma_sap", "link_mua_hang_online", "link_file_hdsd"})

# Field bat buoc de 1 ban ghi duoc coi la "day du" (dung de suy ra CrawlStatus
# va de xac dinh ban ghi nao can crawl lai - xem excel_reader).
REQUIRED_FIELDS: tuple[str, ...] = (
    "ten_san_pham",
    "ma_san_pham",
    "category_1",
    "link_san_pham",
    "link_anh_san_pham",
    "gia",
)


@dataclass
class ProductRecord:
    product_id: str
    ten_san_pham: Optional[str] = None
    ma_san_pham: Optional[str] = None
    ma_sap: Optional[str] = None
    category_1: Optional[str] = None
    category_2: Optional[str] = None
    category_3: Optional[str] = None
    tags: dict[str, Any] = field(default_factory=dict)
    gia: PriceValue = None
    link_san_pham: Optional[str] = None
    link_anh_san_pham: Optional[str] = None
    link_mua_hang_online: Optional[str] = None
    tom_tat_tskt: Optional[str] = None
    tom_tat_uu_diem_tinh_nang: Optional[str] = None
    thong_so_ky_thuat: Optional[str] = None
    link_file_hdsd: Optional[str] = None
    noi_dung_uu_diem_sp: Optional[str] = None

    # Noi bo, khong xuat ra Excel.
    crawl_status: CrawlStatus = CrawlStatus.OK
    crawl_error: Optional[str] = None

    def missing_required_fields(self) -> list[str]:
        missing = []
        for name in REQUIRED_FIELDS:
            value = getattr(self, name)
            if value is None or value == "":
                missing.append(name)
        return missing

    def recompute_status(self) -> "ProductRecord":
        """Suy ra crawl_status tu do day du cua cac field bat buoc.

        Neu da bi danh dau ERROR (loi ky thuat cung, vd fetch that bai hoan
        toan) thi giu nguyen - khong bi ha xuong PARTIAL_MISSING_FIELDS.
        """
        if self.crawl_status != CrawlStatus.ERROR:
            missing = self.missing_required_fields()
            self.crawl_status = (
                CrawlStatus.PARTIAL_MISSING_FIELDS if missing else CrawlStatus.OK
            )
        return self

    def mark_error(self, message: str) -> "ProductRecord":
        self.crawl_status = CrawlStatus.ERROR
        self.crawl_error = message
        return self
