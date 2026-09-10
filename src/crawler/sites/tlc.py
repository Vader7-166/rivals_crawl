"""Pilot crawler cho TLC (tlclighting.com.vn), category "Đèn LED âm trần". Tasks 8.1-8.2.

ĐƯỜNG TỔNG QUÁT NAY O `probing/category_crawl.py`, khong phai o day. File nay
giu nguyen lam ban pilot da chay that; no KHONG phai khuon mau de nhan ban.

Khac biet ban chat giua hai duong, la ly do khong gop lam mot:
  - o day  : san pham = link khop `a[href*='/san-pham/']`, tuc mot CSS selector
             rieng cua TLC. KingLED de URL phang nen cach nay bat kha.
  - tang 0.5: san pham = link co mat trong TAP URL SAN PHAM tu sitemap. Khong
             selector, dung cho moi site, nhung DOI HOI da probe xong domain.
Ban pilot chay doc lap khong co ket qua probe nen khong bac len duong kia duoc.

`product-sitemap.xml` cua TLC la nguon URL san pham dang tin cay CHO CA SITE
(486 URL - da xac nhan o site-probing), nhung khong mang thong tin category -
nen de biet chinh xac URL nao thuoc category "Đèn LED âm trần" (129 SP), phai
phan trang qua chinh trang danh muc do. Ket qua site-probing duoc dung de
DOI CHIEU (moi URL lay tu category co nam trong tap URL da probe hay khong)
thay vi la nguon liet ke truc tiep - xem design.md muc "Site probing" va
docstring cua ham nay.
"""
from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from ..fetch import StealthFetcher

logger = logging.getLogger(__name__)

BASE_URL = "https://tlclighting.com.vn"
CATEGORY_URL = "https://tlclighting.com.vn/danh-muc/den-led-am-tran/"
_MAX_PAGES = 20


def discover_category_product_urls(
    fetcher: StealthFetcher, category_url: str = CATEGORY_URL
) -> list[str]:
    """Phan trang qua toan bo danh muc (WooCommerce: /page/N/), thu thap toan
    bo URL san pham (`/san-pham/...`) xuat hien trong luoi."""
    urls: set[str] = set()
    page = 1
    while page <= _MAX_PAGES:
        page_url = category_url if page == 1 else f"{category_url.rstrip('/')}/page/{page}/"
        result = fetcher.fetch(page_url)
        if not result.ok or not result.html:
            logger.info("Dừng phân trang tại page=%s (fetch không thành công)", page)
            break

        soup = BeautifulSoup(result.html, "lxml")
        page_links = {a["href"] for a in soup.select("a[href*='/san-pham/']") if a.get("href")}

        if not page_links or page_links <= urls:
            logger.info("Dừng phân trang tại page=%s (hết trang / không có sản phẩm mới)", page)
            break

        urls |= page_links
        page += 1

    return sorted(urls)
