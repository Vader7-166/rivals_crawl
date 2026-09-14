"""Hang rao chong tai hien bug 559-thay-vi-486 (tasks 1.1, 1.2).

Bo loc taxonomy o `sitemap.py` tung de 73 trang danh muc `/danh-muc/...` cua TLC
lot vao danh sach "URL san pham" (559 thay vi 486). Trang danh muc khong co
structured data san pham nen moi trang lot vao la mot luot fetch + mot luot goi
LLM de sinh ra ban ghi rong.

Change `crawl-control-web` GIU LAI cac URL do (de dung chi muc danh muc) thay vi
vut di. Viec giu lai KHONG duoc phep lam danh sach san pham to ra du mot URL -
day la bo test chot dieu do.

Hai kieu dat ten taxonomy, moi site mot kieu (xem docs/pipeline.md):

    TLC      WooCommerce, tien to:  product_cat-sitemap.xml        73 trang
    KingLED  sinh dong, hau to:     sitemap.xml?page=ProductGroup  138 trang

So luong trong fixture lay theo so DO THAT tren hai site (KingLED 557 URL san
pham / 138 danh muc, TLC 486 / 73), de con so trong assert doi chieu duoc voi
so ghi trong docs/pipeline.md chu khong phai mot con so tu dat.
"""
import pytest

from crawler.probing import sitemap as sitemap_module
from crawler.probing.sitemap import resolve_sitemap_entries, resolve_sitemap_sources

# -- so do that tren site that, xem docs/pipeline.md -------------------------

KINGLED_PRODUCTS = 557
KINGLED_CATEGORIES = 138
TLC_PRODUCTS = 486
TLC_CATEGORIES = 73


def _urlset(locs) -> bytes:
    body = "".join(f"<url><loc>{loc}</loc></url>" for loc in locs)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{body}</urlset>"
    ).encode("utf-8")


def _sitemapindex(locs) -> bytes:
    body = "".join(f"<sitemap><loc>{loc}</loc></sitemap>" for loc in locs)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{body}</sitemapindex>"
    ).encode("utf-8")


def _kingled_site() -> dict[str, bytes]:
    """Sitemap sinh dong theo content-type: san pham va danh muc nam CANH NHAU
    trong cung 1 index, phan biet chi bang query `?page=`. URL cua ca hai loai
    deu phang (`/<slug>`) nen khong loc lai duoc o buoc sau."""
    base = "https://kingled.com.vn"
    return {
        f"{base}/sitemap.xml": _sitemapindex(
            [f"{base}/sitemap.xml?page=Product", f"{base}/sitemap.xml?page=ProductGroup"]
        ),
        f"{base}/sitemap.xml?page=Product": _urlset(
            f"{base}/san-pham-{i}" for i in range(KINGLED_PRODUCTS)
        ),
        f"{base}/sitemap.xml?page=ProductGroup": _urlset(
            f"{base}/danh-muc-{i}" for i in range(KINGLED_CATEGORIES)
        ),
    }


def _tlc_site() -> dict[str, bytes]:
    """WooCommerce: index gom ca blog va trang tinh, nen bo loc "co chu product"
    la can thiet - nhung mot minh no chua du vi `product_cat-sitemap.xml` cung
    chua chu do."""
    base = "https://tlclighting.com.vn"
    return {
        f"{base}/sitemap_index.xml": _sitemapindex(
            [
                f"{base}/post-sitemap.xml",
                f"{base}/page-sitemap.xml",
                f"{base}/product-sitemap.xml",
                f"{base}/product_cat-sitemap.xml",
            ]
        ),
        f"{base}/post-sitemap.xml": _urlset(f"{base}/blog/bai-{i}" for i in range(40)),
        f"{base}/page-sitemap.xml": _urlset([f"{base}/lien-he", f"{base}/gioi-thieu"]),
        f"{base}/product-sitemap.xml": _urlset(
            f"{base}/san-pham/sp-{i}/" for i in range(TLC_PRODUCTS)
        ),
        f"{base}/product_cat-sitemap.xml": _urlset(
            f"{base}/danh-muc/dm-{i}/" for i in range(TLC_CATEGORIES)
        ),
    }


class _FakeResponse:
    def __init__(self, content: bytes | None):
        self.content = content or b""
        self.status_code = 200 if content is not None else 404


@pytest.fixture
def serve(monkeypatch):
    """Thay `requests.get` trong sitemap.py bang mot site gia trong bo nho."""

    def _install(pages: dict[str, bytes]):
        def fake_get(url, timeout=None, headers=None):
            return _FakeResponse(pages.get(url))

        monkeypatch.setattr(sitemap_module.requests, "get", fake_get)
        return pages

    return _install


# -- 1.1 chot so URL san pham -----------------------------------------------


def test_kingled_product_count_unchanged(serve):
    serve(_kingled_site())

    entries = resolve_sitemap_entries("https://kingled.com.vn/sitemap.xml")

    assert len(entries) == KINGLED_PRODUCTS


def test_tlc_product_count_unchanged(serve):
    serve(_tlc_site())

    entries = resolve_sitemap_entries("https://tlclighting.com.vn/sitemap_index.xml")

    assert len(entries) == TLC_PRODUCTS


def test_no_category_url_leaks_into_products(serve):
    """Dung kiem tra cua bug goc: dem dung nhung nhin nham cung hong. Khong URL
    danh muc nao duoc co mat trong danh sach san pham."""
    serve(_tlc_site())

    locs = [e.loc for e in resolve_sitemap_entries("https://tlclighting.com.vn/sitemap_index.xml")]

    assert not [loc for loc in locs if "/danh-muc/" in loc]
    assert not [loc for loc in locs if "/blog/" in loc]


def test_index_without_any_product_sitemap_keeps_old_behaviour(serve):
    """Khong sub-sitemap nao ghi ro "product" -> giai ma tat ca, y nhu truoc.
    Hanh vi nay khong duoc doi khi them kenh danh muc."""
    base = "https://example.vn"
    serve(
        {
            f"{base}/sitemap.xml": _sitemapindex(
                [f"{base}/a-sitemap.xml", f"{base}/b-sitemap.xml"]
            ),
            f"{base}/a-sitemap.xml": _urlset([f"{base}/x", f"{base}/y"]),
            f"{base}/b-sitemap.xml": _urlset([f"{base}/z"]),
        }
    )

    entries = resolve_sitemap_entries(f"{base}/sitemap.xml")

    assert len(entries) == 3


# -- 2.1/2.2 kenh danh muc ---------------------------------------------------


def test_kingled_listing_urls_are_kept(serve):
    serve(_kingled_site())

    sources = resolve_sitemap_sources("https://kingled.com.vn/sitemap.xml")

    assert len(sources.product) == KINGLED_PRODUCTS
    assert len(sources.listing) == KINGLED_CATEGORIES


def test_tlc_listing_urls_are_kept(serve):
    serve(_tlc_site())

    sources = resolve_sitemap_sources("https://tlclighting.com.vn/sitemap_index.xml")

    assert len(sources.product) == TLC_PRODUCTS
    assert len(sources.listing) == TLC_CATEGORIES
    assert all("/danh-muc/" in e.loc for e in sources.listing)


def test_product_and_listing_never_overlap(serve):
    """Bat bien cua SitemapSources. Giao nhau la bug 559-thay-vi-486 quay lai."""
    for pages in (_kingled_site(), _tlc_site()):
        serve(pages)
        root = next(u for u in pages if u.endswith(("sitemap.xml", "sitemap_index.xml")))

        sources = resolve_sitemap_sources(root)

        assert not {e.loc for e in sources.product} & {e.loc for e in sources.listing}


def test_index_without_product_sitemap_yields_no_listing(serve):
    """Khong loc duoc sitemap san pham -> khong co can cu goi cai nao la danh
    muc. Doan bua se lam danh sach san pham ngan di, tuc doi hanh vi cu."""
    base = "https://example.vn"
    serve(
        {
            f"{base}/sitemap.xml": _sitemapindex([f"{base}/a-sitemap.xml"]),
            f"{base}/a-sitemap.xml": _urlset([f"{base}/x", f"{base}/y"]),
        }
    )

    sources = resolve_sitemap_sources(f"{base}/sitemap.xml")

    assert len(sources.product) == 2
    assert sources.listing == []


def test_probe_result_carries_listing_urls(serve, tmp_path, monkeypatch):
    """2.2: listing_urls di duoc toi ProbeResult va vao cache probe."""
    from crawler.probing.cache import ProbeCache
    from crawler.probing.prober import probe_domain

    serve(_tlc_site())

    class _OkFetch:
        ok, html, status = True, "<html></html>", 200

    class _Fetcher:
        def fetch(self, url, **kw):
            return _OkFetch()

    monkeypatch.setattr(
        "crawler.probing.prober.analyze_page",
        lambda html: type("S", (), {"looks_like_single_product_page": True})(),
    )
    monkeypatch.setattr(
        "crawler.probing.prober.discover_sitemap_candidates",
        lambda base: ["https://tlclighting.com.vn/sitemap_index.xml"],
    )

    cache = ProbeCache(cache_dir=tmp_path)
    result = probe_domain("https://tlclighting.com.vn", _Fetcher(), cache=cache)

    assert len(result.product_urls) == TLC_PRODUCTS
    assert len(result.listing_urls) == TLC_CATEGORIES
    assert len(cache.get("tlclighting.com.vn").listing_urls) == TLC_CATEGORIES
