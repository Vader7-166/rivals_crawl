"""Site probing orchestrator: chon nguon URL san pham dang tin cay cho 1 domain.

Task 4.4 (+ noi 4.1, 4.2, 4.3, 4.5, 4.6 lai voi nhau).
"""
from __future__ import annotations

import logging
import random
from urllib.parse import urlparse

from ..config import PROBING
from ..fetch import StealthFetcher
from .cache import ProbeCache, ProbeResult
from .detection import analyze_page
from .menu_crawl import find_candidate_listing_urls
from .sitemap import discover_sitemap_candidates, resolve_sitemap_entries

logger = logging.getLogger(__name__)

_MAX_MENU_CANDIDATES = 40


def _score_sitemap_reliability(entries, fetcher: StealthFetcher) -> float:
    if not entries:
        return 0.0
    sample_size = min(PROBING.sitemap_sample_size, len(entries))
    sample = random.sample(entries, sample_size)
    hits = 0
    for entry in sample:
        result = fetcher.fetch(entry.loc)
        if result.ok and result.html and analyze_page(result.html).looks_like_single_product_page:
            hits += 1
    return hits / sample_size


def probe_domain(
    base_url: str,
    fetcher: StealthFetcher,
    cache: ProbeCache | None = None,
    force: bool = False,
) -> ProbeResult:
    domain = urlparse(base_url).netloc
    cache = cache or ProbeCache()

    if not force:
        cached = cache.get(domain)
        if cached is not None:
            logger.info("Dung ket qua probe da cache cho %s", domain)
            return cached

    for sitemap_url in discover_sitemap_candidates(base_url):
        entries = resolve_sitemap_entries(sitemap_url)
        if not entries:
            continue
        score = _score_sitemap_reliability(entries, fetcher)
        logger.info(
            "Sitemap %s: %d URL, do tin cay = %.0f%%", sitemap_url, len(entries), score * 100
        )
        if score >= PROBING.sitemap_reliability_threshold:
            result = ProbeResult(
                domain=domain,
                strategy="sitemap",
                probed_at=ProbeCache.now_iso(),
                sitemap_url=sitemap_url,
                reliability_score=score,
                product_urls=[e.loc for e in entries],
            )
            cache.save(result)
            return result

    logger.info("Khong tim thay sitemap dang tin cay cho %s, fallback menu crawl", domain)
    candidates = find_candidate_listing_urls(base_url, fetcher)[:_MAX_MENU_CANDIDATES]

    listing_urls: list[str] = []
    flagged: list[str] = []
    for url in candidates:
        result = fetcher.fetch(url)
        if not result.ok or not result.html:
            continue
        if analyze_page(result.html).looks_like_product_listing:
            listing_urls.append(url)
        else:
            flagged.append(url)

    probe_result = ProbeResult(
        domain=domain,
        strategy="menu_crawl",
        probed_at=ProbeCache.now_iso(),
        listing_urls=listing_urls,
        flagged_landing_urls=flagged,
    )
    cache.save(probe_result)
    return probe_result
