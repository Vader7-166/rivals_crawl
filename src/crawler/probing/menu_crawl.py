"""Crawl menu/breadcrumb du phong khi khong co sitemap dang tin cay. Task 4.5."""
from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..fetch import StealthFetcher


def find_candidate_listing_urls(base_url: str, fetcher: StealthFetcher) -> list[str]:
    """Fetch trang chu va tra ve danh sach URL noi bo ung vien trong menu dieu
    huong (chua duoc xac nhan la luoi san pham that - viec do thuoc ve
    detection.is_real_product_listing, goi boi prober.py cho tung ung vien).
    """
    result = fetcher.fetch(base_url)
    if not result.ok or not result.html:
        return []

    soup = BeautifulSoup(result.html, "lxml")
    domain = urlparse(base_url).netloc

    candidates: list[str] = []
    seen: set[str] = set()

    nav_containers = soup.select("nav, header, .menu, .nav, #menu, #nav") or [soup]
    for container in nav_containers:
        for a in container.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            absolute = urljoin(base_url, href)
            if urlparse(absolute).netloc != domain:
                continue
            if absolute not in seen:
                seen.add(absolute)
                candidates.append(absolute)

    return candidates
