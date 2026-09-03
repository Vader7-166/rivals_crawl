"""Model ban ghi san pham chuan (product-record-schema). Task 2.1.

Khuon field lay DAY DU theo `product_Metadata (1).xlsx` (sheet "2. LED
Downlight"): GIU LAI ca nhung cot ma crawler chua bao gio dien duoc
(`Gia doi chieu`, `VD HDSD`, `Ma SAP`, `Link mua hang online`...). Cac cot do
duoc ghi ra RONG chu KHONG bi bo khoi file - de file xuat ra ghep thang duoc
vao khuon tham chieu ma khong phai can chinh cot.
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
#
# Ten cot duoc chep NGUYEN VAN tu hang header cua sheet "2. LED Downlight",
# ke ca khoang trang thua o ' category 1 ' / 'Thong so ky thuat ' - de header
# file xuat ra so khop tuyet doi voi khuon tham chieu. Ben doc lai (excel_
# reader) tu strip khi so khop nen khoang trang nay khong lam gay round-trip.
COLUMNS: list[tuple[str, str]] = [
    ("STT", "stt"),
    ("Product_ID", "product_id"),
    ("Tên sản phẩm", "ten_san_pham"),
    ("Mã Sản Phẩm", "ma_san_pham"),
    ("Mã SAP", "ma_sap"),
    (" category 1 ", "category_1"),
    (" category 2", "category_2"),
    (" category 3", "category_3"),
    ("Tags", "tags"),
    ("Giá", "gia"),
    ("Giá đối chiếu", "gia_doi_chieu"),
    ("Link sản phẩm", "link_san_pham"),
    ("Link ảnh sản phẩm", "link_anh_san_pham"),
    ("Link mua hàng online", "link_mua_hang_online"),
    ("Tóm tắt TSKT", "tom_tat_tskt"),
    ("Tóm tắt ưu điểm, tính năng", "tom_tat_uu_diem_tinh_nang"),
    ("Thông số kỹ thuật ", "thong_so_ky_thuat"),
    ("Link file HDSD", "link_file_hdsd"),
    ("VD HDSD", "vd_hdsd"),
    ("Nội dung Ưu điểm SP", "noi_dung_uu_diem_sp"),
]

# Field duoc phep null ma KHONG bi coi la crawl loi/thieu sot (spec: "Field
# optional theo tung site"). `gia_doi_chieu` va `vd_hdsd` nam o day vi khuon
# tham chieu co cot do nhung site doi thu khong cong bo du lieu tuong duong -
# de trong la dung, khong phai dau hieu crawl hong.
OPTIONAL_FIELDS = frozenset(
    {"ma_sap", "link_mua_hang_online", "link_file_hdsd", "gia_doi_chieu", "vd_hdsd"}
)

# Field bat buoc de 1 ban ghi duoc coi la "day du" (dung de suy ra CrawlStatus
# va de xac dinh ban ghi nao can crawl lai - xem excel_reader).
#
# `tags` nam trong nhom nay CO CHU DICH: khi tang 2 (LLM) loi hoac tra ve output
# khong hop le, pipeline nuot loi va de `tags` rong. Vi crawl_status KHONG duoc
# ghi ra cot Excel (theo spec), `tags` rong la DAU VET DUY NHAT con lai trong
# file cho biet ban ghi do chua hoan chinh. Neu khong tinh `tags`, ban ghi loi
# LLM se duoc ghi ra voi trang thai `ok` va khong bao gio duoc crawl lai - trai
# voi spec llm-attribute-normalization ("ket qua khong hop le SHALL duoc gan co
# de review thay vi luu thang").
REQUIRED_FIELDS: tuple[str, ...] = (
    "ten_san_pham",
    "ma_san_pham",
    "category_1",
    "link_san_pham",
    "link_anh_san_pham",
    "gia",
    "tags",
)


@dataclass
class ProductRecord:
    """1 field cho MOI cot cua khuon tham chieu, theo dung thu tu COLUMNS.

    Ke ca field khong nguon nao dien duoc (`gia_doi_chieu`, `vd_hdsd`): giu lai
    de cot van xuat hien trong file .xlsx, chi la o rong.
    """

    product_id: str
    # So thu tu trong file xuat ra. De None thi excel_writer tu danh so theo
    # thu tu dong (1..N) - khong phai du lieu san pham nen sinh ra duoc.
    stt: Optional[int] = None
    ten_san_pham: Optional[str] = None
    ma_san_pham: Optional[str] = None
    ma_sap: Optional[str] = None
    category_1: Optional[str] = None
    category_2: Optional[str] = None
    category_3: Optional[str] = None
    tags: dict[str, Any] = field(default_factory=dict)
    gia: PriceValue = None
    # Khuon tham chieu dung cot nay cho gia doi chung noi bo cua rangdong (o
    # file goc la cong thuc VLOOKUP sang sheet CSDL). Site doi thu khong cong
    # bo gi tuong duong -> luon rong.
    gia_doi_chieu: PriceValue = None
    link_san_pham: Optional[str] = None
    link_anh_san_pham: Optional[str] = None
    link_mua_hang_online: Optional[str] = None
    tom_tat_tskt: Optional[str] = None
    tom_tat_uu_diem_tinh_nang: Optional[str] = None
    thong_so_ky_thuat: Optional[str] = None
    link_file_hdsd: Optional[str] = None
    # "Video huong dan su dung" - cot nay rong san trong chinh khuon tham chieu.
    vd_hdsd: Optional[str] = None
    noi_dung_uu_diem_sp: Optional[str] = None

    # Noi bo, khong xuat ra Excel.
    crawl_status: CrawlStatus = CrawlStatus.OK
    crawl_error: Optional[str] = None
    # Duong nao dinh vi duoc muc uu diem ('keyword'/'anchor'/'cluster'/'none')
    # - xem extraction/advantages.py. Di theo cung duong voi crawl_status: du
    # lieu VAN HANH, khong thuoc khuon tham chieu nen khong co cot Excel, nhung
    # duoc luu vao kho du lieu va dung lam cot "ly do" cua sheet canh bao.
    uu_diem_nguon: str = "none"
    # Dong ma tang 2 (LLM) chi ra de dinh vi muc uu diem. Luu lai de chay lai
    # trich xuat tren HTML da co ma khong phai goi LLM lan nua.
    uu_diem_la_ban: Optional[str] = None

    def missing_required_fields(self) -> list[str]:
        missing = []
        for name in REQUIRED_FIELDS:
            value = getattr(self, name)
            # So sanh bang == thay vi kiem tra truthy: gia = 0.0 la gia tri co
            # that (du falsy) nen khong duoc coi la thieu, con {} / "" thi co.
            if value is None or value == "" or value == {}:
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
