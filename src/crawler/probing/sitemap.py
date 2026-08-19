"""Kham pha va giai ma sitemap. Task 4.2 (+ ho tro 4.4).

Sitemap/robots.txt la tai nguyen may doc (XML/text) chu khong phai noi dung
trang can render JS hay gia lap trinh duyet - nen dung thang `requests` o day,
khac voi viec xac nhan trang/URL san pham (luon di qua StealthFetcher, xem
prober.py) vi do moi la "noi dung trang" theo dung nghia cua stealth-fetch spec.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

import requests

from ..config import FETCH
from .robots import get_sitemap_urls_from_robots

COMMON_SITEMAP_PATHS = ("/sitemap_index.xml", "/sitemap.xml", "/product-sitemap.xml")

# Sub-sitemap cua TAXONOMY san pham, khong phai cua san pham. WooCommerce dat
# ten taxonomy theo tien to `product_` (product_cat, product_tag, product_brand,
# product_shipping_class) nen chung deu lot qua bo loc "co chu product" o duoi
# neu khong loai rieng - case TLC: product_cat-sitemap.xml keo them 73 trang
# danh muc `/danh-muc/...` vao danh sach "URL san pham", lam crawler ton luot
# fetch + goi LLM cho trang khong phai san pham va sinh ra ban ghi rong.
_TAXONOMY_SITEMAP = re.compile(r"product_[a-z_]+-sitemap", re.IGNORECASE)

_REQUEST_HEADERS = {
    "User-Agent": FETCH.default_user_agent,
    "Accept-Language": FETCH.default_accept_language,
}


@dataclass
class SitemapEntry:
    loc: str
    lastmod: Optional[str] = None


def discover_sitemap_candidates(base_url: str) -> list[str]:
    """Danh sach URL sitemap ung vien: uu tien robots.txt, sau do cac path quy uoc."""
    candidates = list(get_sitemap_urls_from_robots(base_url))
    for path in COMMON_SITEMAP_PATHS:
        candidates.append(base_url.rstrip("/") + path)

    seen: set[str] = set()
    ordered: list[str] = []
    for url in candidates:
        if url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def resolve_sitemap_entries(
    sitemap_url: str, timeout: float = 15.0, _depth: int = 0
) -> list[SitemapEntry]:
    """Giai de quy 1 sitemap (hoac sitemap index) thanh danh sach URL phang.

    Neu URL khong tra ve XML hop le (vd site tra ve trang HTML 200 gia -
    case KingLED voi cac path sitemap khong ton tai), tra ve [] thay vi loi,
    de tang tren coi day la "khong tim thay sitemap tai duong dan nay".
    """
    if _depth > 3:
        return []
    try:
        resp = requests.get(sitemap_url, timeout=timeout, headers=_REQUEST_HEADERS)
    except requests.RequestException:
        return []
    if resp.status_code != 200:
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError:
        return []

    root_tag = _local_tag(root.tag)
    entries: list[SitemapEntry] = []

    if root_tag == "sitemapindex":
        child_locs = [
            el.text.strip()
            for el in root.iter()
            if _local_tag(el.tag) == "loc" and el.text
        ]
        # Uu tien cac sub-sitemap co "product" trong URL (vd product-sitemap.xml)
        # neu co - tranh gop lan bai viet blog/trang tinh (case TLC:
        # sitemap_index.xml -> post-sitemap.xml + page-sitemap.xml +
        # product-sitemap.xml, chi cai cuoi la san pham). Neu khong sub-sitemap
        # nao ghi ro "product", giu nguyen hanh vi cu (giai ma tat ca).
        product_like = [
            u for u in child_locs
            if "product" in u.lower() and not _TAXONOMY_SITEMAP.search(u)
        ]
        targets = product_like or child_locs
        for child_url in targets:
            entries.extend(resolve_sitemap_entries(child_url, timeout=timeout, _depth=_depth + 1))
        return entries

    if root_tag == "urlset":
        for url_el in root:
            if _local_tag(url_el.tag) != "url":
                continue
            loc, lastmod = None, None
            for child in url_el:
                child_tag = _local_tag(child.tag)
                if child_tag == "loc" and child.text:
                    loc = child.text.strip()
                elif child_tag == "lastmod" and child.text:
                    lastmod = child.text.strip()
            if loc:
                entries.append(SitemapEntry(loc=loc, lastmod=lastmod))
        return entries

    return []
