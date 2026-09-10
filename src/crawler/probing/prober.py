"""Site probing orchestrator: chon nguon URL san pham dang tin cay cho 1 domain.

Task 4.4 (+ noi 4.1, 4.2, 4.3, 4.5, 4.6 lai voi nhau).
"""
from __future__ import annotations

import logging
import random
from urllib.parse import urlparse

from ..config import PROBING
from ..fetch import StealthFetcher
from ..sites import get_profile
from .cache import ProbeCache, ProbeResult
from .detection import analyze_page
from .menu_crawl import find_candidate_listing_urls
from .product_discovery import discover_product_urls
from .sitemap import discover_sitemap_candidates, resolve_sitemap_sources

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
        sources = resolve_sitemap_sources(sitemap_url)
        entries = sources.product
        if not entries:
            continue
        score = _score_sitemap_reliability(entries, fetcher)
        logger.info(
            "Sitemap %s: %d URL san pham + %d trang danh muc, do tin cay = %.0f%%",
            sitemap_url, len(entries), len(sources.listing), score * 100,
        )
        if score >= PROBING.sitemap_reliability_threshold:
            result = ProbeResult(
                domain=domain,
                strategy="sitemap",
                probed_at=ProbeCache.now_iso(),
                sitemap_url=sitemap_url,
                reliability_score=score,
                product_urls=[e.loc for e in entries],
                # Do tin cay CHI cham diem tren URL san pham. Trang danh muc di
                # kem khong duoc tinh vao diem: no khong phai trang san pham nen
                # bo phat hien se truot, va truot thi keo diem xuong duoi nguong
                # -> site tut xuong nhanh menu-crawl du sitemap hoan toan du.
                listing_urls=[e.loc for e in sources.listing],
            )
            cache.save(result)
            return result

    logger.info("Khong tim thay sitemap dang tin cay cho %s, fallback menu crawl", domain)
    profile = get_profile(base_url)
    # Site da khai `listing_seed_urls` thi CHI di tu do, khong bo them ung vien
    # doc tu menu trang chu. Khai seed la mot cau khang dinh da do duoc: san
    # pham cua site nay nam duoi day, cho khac thi khong.
    #
    # Do tren roman.vn: menu trang chu la carousel ANH, khong the <nav> nao,
    # nen `find_candidate_listing_urls` tut ve "lay ca trang lam menu" va nem
    # vao 122 link - trong do co ca bai blog, va bai blog ky thuat ("10 thong
    # so den LED can biet") thi vuot moi nguong noi dung nen di thang vao ket
    # qua. Them seed ma van gop menu thi chi THEM URL chu khong bot rac: do
    # duoc 94/94 san pham nhung cung giu nguyen 45/45 rac.
    if profile.listing_seed_urls:
        candidates = list(profile.listing_seed_urls)
    else:
        candidates = find_candidate_listing_urls(base_url, fetcher)[:_MAX_MENU_CANDIDATES]

    # Menu chi cho ra UNG VIEN trang danh muc. Viec bien chung thanh URL san
    # pham la cua product_discovery.py - truoc no, nhanh nay tra ve
    # product_urls=[] va crawl_site.py dung ngay tai do.
    discovery = discover_product_urls(
        base_url,
        fetcher,
        seed_urls=candidates,
        listing_fetch_options=profile.listing_fetch_options,
        product_fetch_options=profile.fetch_options,
        product_url_pattern=profile.product_url_pattern,
    )
    logger.info(
        "Do khong-sitemap %s: %d trang danh muc, %d URL san pham, %d trang da fetch%s",
        domain, len(discovery.listing_urls), len(discovery.product_urls),
        discovery.pages_fetched, " (CHAM TRAN)" if discovery.budget_exhausted else "",
    )

    probe_result = ProbeResult(
        domain=domain,
        strategy="menu_crawl",
        probed_at=ProbeCache.now_iso(),
        product_urls=discovery.product_urls,
        listing_urls=discovery.listing_urls,
        flagged_landing_urls=discovery.flagged_urls,
    )
    cache.save(probe_result)
    return probe_result
