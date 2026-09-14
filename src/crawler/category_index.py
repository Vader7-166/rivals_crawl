"""Dung chi muc danh muc cho 1 domain - tang 0.5, chay TRUOC khi crawl.

Vi tri trong duong ong:

    tang 0    probing sitemap  ->  product_urls  +  listing_urls
                                        |              |
    tang 0.5  (file nay)                |              v
                                        |         duyet tung trang danh muc
                                        |              |
                                        v              v
                                   doi chieu   <-  canh (danh muc <-> san pham)
                                        |
    tang 1..2 crawl <-------------------+  chi crawl phan CON THIEU cua pham vi

Vong ga-trung ma tang nay pha: muon biet "san pham nao thuoc downlight ma chua
crawl" thi phai biet danh muc cua mot URL TRUOC khi fetch no - ma biet duoc thi
da crawl roi. Trang danh muc tra loi duoc cau do, va chung von da nam san trong
sitemap taxonomy ma tang 0 truoc day vut di.

Gia: 211 trang danh muc cho ca hai site da co (TLC 73 + KingLED 138), khong mot
lan goi LLM nao.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Sequence

from .probing.category_crawl import DEFAULT_MAX_PAGES, crawl_category
from .store.category_store import CategoryStore

logger = logging.getLogger(__name__)


@dataclass
class IndexReport:
    """Ket qua mot luot dung chi muc. Cac con so o day la de DOI CHIEU, khong
    phai de trang tri - xem `warnings`."""

    domain: str
    categories_total: int = 0
    categories_ok: int = 0
    categories_failed: int = 0
    edges: int = 0
    products_in_sitemap: int = 0
    products_indexed: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def products_uncategorised(self) -> int:
        return self.products_in_sitemap - self.products_indexed


def build_category_index(
    store: CategoryStore,
    fetcher,
    domain: str,
    listing_urls: Sequence[str],
    product_urls: Sequence[str],
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    fetch_options: Optional[dict] = None,
    limit: Optional[int] = None,
) -> IndexReport:
    """Duyet moi trang danh muc cua 1 domain va luu canh vao kho.

    `listing_urls` / `product_urls` lay tu ket qua probe (tang 0). Ham nay
    KHONG tu probe - de mot luot dung chi muc khong bao gio am tham keo theo
    mot luot probe lai.

    Ghi vao kho NGAY SAU khi duyet xong tung danh muc, khong doi het vong lap:
    211 trang la hang chuc phut, va mot lan ngat giua chung khong duoc phep xoa
    sach tien do.
    """
    report = IndexReport(domain=domain, products_in_sitemap=len(product_urls))
    targets = list(listing_urls)[:limit] if limit else list(listing_urls)
    report.categories_total = len(targets)

    if not targets:
        report.warnings.append(
            "Không có trang danh mục nào từ probe — site này có thể không có "
            "sitemap taxonomy, hoặc kết quả probe được cache từ trước khi có "
            "tầng 0.5 (chạy lại probe với --refresh-probe)."
        )
        return report

    for order, category_url in enumerate(targets, start=1):
        result = crawl_category(
            fetcher, category_url, product_urls,
            max_pages=max_pages, fetch_options=fetch_options,
        )
        store.save_category(domain, result)

        if result.ok:
            report.categories_ok += 1
            report.edges += len(result.product_urls)
        else:
            report.categories_failed += 1

        if order % 25 == 0:
            logger.info("... %d/%d danh mục", order, len(targets))

    total, indexed = store.coverage_gap(domain, product_urls)
    report.products_indexed = indexed

    # Ba canh bao duoi day deu la thu PHAI NOI RA. Nuot chung di thi pham vi
    # tim kiem thieu am tham, va "am tham" moi la kieu hong dat nhat cua ca du
    # an nay (xem docs/pipeline.md, bay sitemap sai chuan).
    if report.categories_failed:
        report.warnings.append(
            f"{report.categories_failed}/{report.categories_total} danh mục fetch "
            f"không thành công — chưa có dữ liệu, KHÁC với danh mục rỗng. "
            f"Chạy lại để bù."
        )
    # `limit` -> do phu THEO DINH NGHIA la mot phan, nen canh bao do phu o day
    # chi la tieng on: chay 5/138 danh muc thi 93% san pham "khong thuoc danh
    # muc nao" la dung, khong phai dau hieu hong. Canh bao nao cung keu thi
    # khong canh bao nao duoc doc.
    if report.products_uncategorised and limit is None:
        share = report.products_uncategorised / max(1, total)
        message = (
            f"{report.products_uncategorised}/{total} sản phẩm không thuộc trang "
            f"danh mục nào ({share:.0%})"
        )
        # Nguong 20%: duoi muc nay la chuyen binh thuong (san pham moi, san pham
        # chi vao duoc tu tim kiem). Tren muc nay thi nhieu kha nang trang danh
        # muc liet ke thieu - site chi hien hang con ban, hoac nap them bang JS.
        if share > 0.2:
            message += " — kiểm tra xem trang danh mục có nạp sản phẩm bằng JS không"
        report.warnings.append(message)
    if report.categories_ok and not report.edges:
        report.warnings.append(
            "Duyệt được danh mục nhưng không thu được cạnh nào — nhiều khả năng "
            "danh sách URL sản phẩm truyền vào không khớp với link trên trang."
        )

    return report


__all__ = ["IndexReport", "build_category_index"]
