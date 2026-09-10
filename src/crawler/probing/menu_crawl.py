"""Crawl menu/breadcrumb du phong khi khong co sitemap dang tin cay. Task 4.5."""
from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..fetch import StealthFetcher


def nav_links(html: str, page_url: str, *, require_container: bool = False) -> list[str]:
    """URL noi bo trong menu dieu huong cua MOT trang da tai.

    Tach rieng khoi `find_candidate_listing_urls` de dung lai duoc cho trang
    KHONG PHAI trang chu: nhanh du phong (product_discovery.py) di tiep mot
    chang tu trang landing xuong trang luoi, va trang landing cung mang menu.

    `require_container=False` (mac dinh, hanh vi cu): trang khong co the menu
    nao thi coi CA TRANG la menu - rong rai, dung cho viec DI TIEP, cung lam
    thi thua vai ung vien.
    `require_container=True`: khong co the menu thi tra ve rong. Bat buoc khi
    ket qua duoc dung de LOAI - lay ca trang lam menu roi dem di loai thi moi
    link tren trang deu bi vut, tuc khong con san pham nao.
    """
    soup = BeautifulSoup(html, "lxml")
    domain = urlparse(page_url).netloc

    candidates: list[str] = []
    seen: set[str] = set()

    nav_containers = soup.select("nav, header, .menu, .nav, #menu, #nav")
    if not nav_containers:
        if require_container:
            return []
        nav_containers = [soup]
    for container in nav_containers:
        for a in container.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            absolute = urljoin(page_url, href)
            if urlparse(absolute).netloc != domain:
                continue
            if absolute not in seen:
                seen.add(absolute)
                candidates.append(absolute)

    return candidates


def find_candidate_listing_urls(base_url: str, fetcher: StealthFetcher) -> list[str]:
    """Fetch trang chu va tra ve danh sach URL noi bo ung vien trong menu dieu
    huong (chua duoc xac nhan la luoi san pham that - viec do thuoc ve
    detection.is_real_product_listing, goi boi prober.py cho tung ung vien).
    """
    result = fetcher.fetch(base_url)
    if not result.ok or not result.html:
        return []
    return nav_links(result.html, base_url)
