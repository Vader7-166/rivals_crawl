"""Bo phat hien "trang/URL san pham that" dung chung. Task 4.3.

Dung o 2 cho (theo specs/site-probing/spec.md):
(a) xac nhan trang danh muc ung vien khi crawl menu/breadcrumb du phong
(b) lay mau xac nhan URL khi cham diem do tin cay sitemap

Nguong CARD_LINK_THRESHOLD duoc chon dua tren du lieu thuc te da khao sat tren
Roman.vn (xem design.md): trang landing "bay" den-led-am-tran.html chi co 17
the <a> boc <img> (anh banner), trong khi trang luoi that den-downlight-led.html
co 52 - ca hai deu co pagination/structured-data gan giong nhau nen KHONG dung
duoc lam tin hieu phan biet chinh (Roman gan nham 1 JSON-LD kieu "Product" len
ca trang landing, va trang luoi that lai khong co structured data nao ca).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

# Nguong thuc nghiem: xem docstring o tren. Da thu ha nguong xuong ket hop voi
# has_pagination nhung ca 2 trang deu co pagination control nen khong tach
# duoc - phai dung rieng card_link_count lam tieu chi chinh.
CARD_LINK_THRESHOLD = 30

_PRICE_WORD_RE = re.compile(r"giá\b", re.I)  # "giá" (co dau), khong khop "gia" tran
_PRODUCT_JSONLD_RE = re.compile(r'"@type"\s*:\s*"Product"')
_PRODUCT_MICRODATA_RE = re.compile(r'itemtype=["\']https?://schema\.org/Product["\']', re.I)
_PAGINATION_RE = re.compile(
    r'(class=["\'][^"\']*pag(e|ination)[^"\']*["\']|rel=["\']next["\']|[?&]page=\d+|/page/\d+|/paged/\d+)',
    re.I,
)


@dataclass
class PageSignals:
    price_mentions: int
    product_structured_data_count: int
    card_link_count: int
    has_pagination: bool

    @property
    def looks_like_single_product_page(self) -> bool:
        """Dung khi xac nhan 1 URL rieng le (vd mau tu sitemap) co phai trang
        san pham that hay khong."""
        return self.product_structured_data_count >= 1 or self.price_mentions >= 1

    @property
    def looks_like_product_listing(self) -> bool:
        """Dung khi phan loai 1 trang danh muc ung vien la luoi san pham that
        hay landing/noi dung rong (case Roman: trang landing co rat it the
        anh+link lap lai so voi trang luoi that). has_pagination/structured-data
        KHONG dung de ha nguong vi thuc te ca trang landing lan trang luoi that
        deu co the co ca 2 tin hieu nay (Roman gan nham JSON-LD Product len
        trang landing, va ca 2 deu co control phan trang trong menu chung)."""
        return self.card_link_count >= CARD_LINK_THRESHOLD


def analyze_page(html: str) -> PageSignals:
    soup = BeautifulSoup(html, "lxml")
    card_hrefs = {a["href"] for a in soup.find_all("a", href=True) if a.find("img")}

    return PageSignals(
        price_mentions=len(_PRICE_WORD_RE.findall(html)),
        product_structured_data_count=(
            len(_PRODUCT_JSONLD_RE.findall(html)) + len(_PRODUCT_MICRODATA_RE.findall(html))
        ),
        card_link_count=len(card_hrefs),
        has_pagination=bool(_PAGINATION_RE.search(html)),
    )


def is_real_product_page(html: str) -> bool:
    return analyze_page(html).looks_like_single_product_page


def is_real_product_listing(html: str) -> bool:
    return analyze_page(html).looks_like_product_listing
