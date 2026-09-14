"""Duyet MOT trang danh muc (co phan trang) -> danh sach URL san pham thuoc no.

Tang 0.5. Tong quat cho moi site: phan rieng cua site KHONG nam o day va cung
khong nam o mot registry moi nao ca - xem hai quyet dinh duoi.

QUYET DINH 1 - nhan dien san pham bang TAP URL DA BIET, khong bang CSS selector.

    Ban pilot cho TLC (`sites/tlc.py`) tim san pham bang `a[href*='/san-pham/']`.
    Cach do khong nhan ban duoc: KingLED de URL phang, san pham
    `den-panel-hop-onyx-48w-60x60cm` nam canh danh muc `am-tran-downlight` -
    khong co dau hieu nao trong URL de phan biet, nen moi site se phai mot
    selector rieng.

    O day thay bang: san pham la link co mat trong TAP URL SAN PHAM tu sitemap.
    Tap do la thu tang 0 DA CO SAN va da duoc cham diem do tin cay. Khong
    selector, khong cau hinh theo domain, va dung ca voi site URL phang.

QUYET DINH 2 - phan trang bam theo LINK CO THAT tren trang, khong doan URL.

    `/page/2/` la quy uoc cua WooCommerce; site khac dung `?page=2`, `?paged=2`,
    `/trang-2`. Doan URL thi moi kieu la mot nhanh code. Duyet link phan trang
    co san trong DOM thi 4 kieu tren deu di qua cung mot duong.

Bat bien: KHONG fetch trang san pham nao, KHONG goi LLM. Chi mot lan fetch cho
moi trang danh muc (ke ca trang con cua phan trang).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Tran so trang con cho MOT danh muc. Ban pilot TLC dat 20 cho mot category duy
# nhat; giu nguyen muc do vi day la tran an toan chu khong phai tran do duoc -
# no chi can du lon de khong cat mat danh muc that va du nho de mot trang phan
# trang hong khong keo ca luot duyet di vo han.
DEFAULT_MAX_PAGES = 20

# Dau hieu phan trang trong URL. Bon quy uoc da gap gop chung mot regex thay vi
# bon nhanh code: /page/2/, ?page=2, ?paged=2, /trang-2.
_PAGE_MARKER = re.compile(r"[/?&](?:page|paged|trang)[=/-]?\d+", re.IGNORECASE)


@dataclass
class CategoryCrawlResult:
    """Ket qua duyet 1 danh muc.

    `ok=False` va `product_urls=[]` la "CHUA CO DU LIEU" (fetch hong), khac han
    `ok=True` va `product_urls=[]` la "danh muc that su rong". Gop hai cai lam
    mot thi mot danh muc chet mang lai bi doc thanh mot danh muc khong co hang.
    """

    category_url: str
    category_name: Optional[str] = None
    product_urls: list[str] = field(default_factory=list)
    pages_fetched: int = 0
    ok: bool = True
    error: Optional[str] = None


def _canonical_lookup(known_product_urls: Iterable[str]) -> dict[str, str]:
    """khoa so trung (bo dau `/` cuoi) -> URL NGUYEN VAN cua sitemap.

    Dau `/` cuoi la quy uoc rieng cua tung site (ca 486 URL cua TLC co, KingLED
    khong URL nao co) va la mot phan DANH TINH ban ghi - xem docstring cua
    `sites/registry.select_product_urls`. Nen no chi duoc dung de SO TRUNG voi
    href tren trang, con thu tra ve luon la ban goc tu sitemap.
    """
    return {url.rstrip("/"): url for url in known_product_urls}


def page_links(html: str, page_url: str) -> list[str]:
    """Moi href tren trang, da chuyen ve URL tuyet doi va bo fragment."""
    soup = BeautifulSoup(html, "lxml")
    links = []
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        links.append(urljoin(page_url, href).split("#", 1)[0])
    return links


def _category_name(html: str) -> Optional[str]:
    """Ten danh muc lay tu chinh trang: <h1> truoc, roi <title>."""
    soup = BeautifulSoup(html, "lxml")
    for selector in ("h1", "title"):
        el = soup.select_one(selector)
        if el:
            name = " ".join(el.get_text(" ", strip=True).split())
            if name:
                return name
    return None


def pagination_candidates(links: Iterable[str], category_url: str) -> set[str]:
    """Link tren trang tro toi trang con KHAC cua CHINH danh muc nay.

    Hai rang buoc phai co ca hai: mang dau hieu phan trang, VA nam cung nhanh
    duong dan voi danh muc. Thieu rang buoc thu hai thi link "trang 2" cua mot
    danh muc khac trong menu se keo luot duyet sang danh muc do.
    """
    cat = urlparse(category_url)
    cat_path = cat.path.rstrip("/")
    out: set[str] = set()
    for link in links:
        parsed = urlparse(link)
        if parsed.netloc != cat.netloc:
            continue
        if not _PAGE_MARKER.search(link):
            continue
        if not parsed.path.rstrip("/").startswith(cat_path):
            continue
        out.add(link)
    return out


def crawl_category(
    fetcher,
    category_url: str,
    known_product_urls: Iterable[str],
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    fetch_options: Optional[dict] = None,
) -> CategoryCrawlResult:
    """Duyet 1 danh muc va moi trang con cua no, tra ve URL san pham thuoc no."""
    lookup = _canonical_lookup(known_product_urls)
    fetch_options = fetch_options or {}

    result = CategoryCrawlResult(category_url=category_url)
    found: dict[str, None] = {}  # dict thay set: giu thu tu xuat hien tren trang
    queue = [category_url]
    visited: set[str] = set()

    while queue and result.pages_fetched < max_pages:
        page_url = queue.pop(0)
        if page_url in visited:
            continue
        visited.add(page_url)

        fetch_result = fetcher.fetch(page_url, **fetch_options)
        if not getattr(fetch_result, "ok", False) or not getattr(fetch_result, "html", ""):
            if page_url == category_url:
                # Trang DAU hong -> chua biet gi ve danh muc nay ca.
                result.ok = False
                result.error = getattr(fetch_result, "error", None) or "fetch that bai"
                return result
            # Mot trang con hong: giu phan da thu duoc, ghi lai de doi chieu.
            logger.info("Trang con %s fetch không thành công, bỏ qua", page_url)
            continue

        result.pages_fetched += 1
        html = fetch_result.html
        if result.category_name is None:
            result.category_name = _category_name(html)

        links = page_links(html, page_url)
        for link in links:
            canonical = lookup.get(link.rstrip("/"))
            if canonical is not None:
                found.setdefault(canonical, None)

        for candidate in sorted(pagination_candidates(links, category_url)):
            if candidate not in visited:
                queue.append(candidate)

    if result.pages_fetched >= max_pages and queue:
        logger.warning(
            "Danh mục %s chạm trần %d trang, có thể còn sản phẩm chưa thu",
            category_url, max_pages,
        )

    result.product_urls = list(found)
    return result


__all__ = [
    "CategoryCrawlResult",
    "crawl_category",
    "DEFAULT_MAX_PAGES",
    "page_links",
    "pagination_candidates",
]
