"""Tang 0.5 - duyet mot trang danh muc (tasks 2.3, 2.5, 2.6).

Hai bat bien duoc chot o day, deu la ly do ton tai cua tang nay:
  1. KHONG fetch trang san pham nao (dem so lan fetch, doi chieu voi so trang
     danh muc). Tang 0.5 phai re: no chay TRUOC khi biet crawl gi.
  2. "fetch hong" khac "danh muc rong" - gop lam mot thi mot danh muc chet mang
     bi doc thanh mot danh muc khong co hang.
"""
import pytest

from crawler.probing.category_crawl import crawl_category


class _Result:
    def __init__(self, html=None, error=None):
        self.html = html or ""
        self.ok = html is not None
        self.status = 200 if html is not None else None
        self.error = error


class _Fetcher:
    """Site gia trong bo nho, dem MOI lan fetch va URL da fetch."""

    def __init__(self, pages: dict[str, str]):
        self._pages = pages
        self.fetched: list[str] = []

    def fetch(self, url, **kwargs):
        self.fetched.append(url)
        html = self._pages.get(url)
        return _Result(html) if html is not None else _Result(error="404")


def _grid(links, extra=""):
    body = "".join(f'<a href="{href}">sp</a>' for href in links)
    return f"<html><head><title>t</title></head><body><h1>Đèn LED âm trần</h1>{body}{extra}</body></html>"


BASE = "https://tlclighting.com.vn"
CAT = f"{BASE}/danh-muc/den-led-am-tran/"
PRODUCTS = [f"{BASE}/san-pham/sp-{i}/" for i in range(5)]


def test_collects_products_across_pagination():
    pages = {
        CAT: _grid(PRODUCTS[:2], f'<a href="{CAT}page/2/">2</a>'),
        f"{CAT}page/2/": _grid(PRODUCTS[2:4], f'<a href="{CAT}page/3/">3</a>'),
        f"{CAT}page/3/": _grid(PRODUCTS[4:]),
    }
    fetcher = _Fetcher(pages)

    result = crawl_category(fetcher, CAT, PRODUCTS)

    assert result.ok
    assert sorted(result.product_urls) == sorted(PRODUCTS)
    assert result.pages_fetched == 3


def test_never_fetches_a_product_page():
    """Bat bien 1: chi trang danh muc duoc fetch, dung bang so trang con."""
    pages = {CAT: _grid(PRODUCTS, f'<a href="{CAT}page/2/">2</a>'), f"{CAT}page/2/": _grid([])}
    fetcher = _Fetcher(pages)

    crawl_category(fetcher, CAT, PRODUCTS)

    assert fetcher.fetched == [CAT, f"{CAT}page/2/"]
    assert not [u for u in fetcher.fetched if "/san-pham/" in u]


def test_flat_product_urls_are_matched_without_any_selector():
    """Case KingLED: URL san pham va URL danh muc deu phang, khong pattern nao
    phan biet duoc. Tap URL tu sitemap moi la can cu."""
    base = "https://kingled.com.vn"
    cat = f"{base}/am-tran-downlight"
    products = [f"{base}/den-panel-hop-onyx-48w", f"{base}/den-san-vuon-gr"]
    pages = {cat: _grid(products + [f"{base}/mot-danh-muc-khac"])}

    result = crawl_category(_Fetcher(pages), cat, products)

    assert sorted(result.product_urls) == sorted(products)


def test_trailing_slash_of_source_site_is_preserved():
    """URL tra ve phai la ban NGUYEN VAN cua sitemap, khong phai ban tu href.
    Dau `/` cuoi la mot phan danh tinh ban ghi - doi no la co che
    crawl-lai-co-chon-loc mat khop."""
    pages = {CAT: _grid([f"{BASE}/san-pham/sp-0"])}  # href KHONG co dau `/` cuoi

    result = crawl_category(_Fetcher(pages), CAT, [f"{BASE}/san-pham/sp-0/"])

    assert result.product_urls == [f"{BASE}/san-pham/sp-0/"]


def test_pagination_of_another_category_is_not_followed():
    other = f"{BASE}/danh-muc/den-led-panel/"
    pages = {
        CAT: _grid(PRODUCTS[:1], f'<a href="{other}page/2/">panel 2</a>'),
        f"{other}page/2/": _grid(PRODUCTS[1:]),
    }
    fetcher = _Fetcher(pages)

    result = crawl_category(fetcher, CAT, PRODUCTS)

    assert fetcher.fetched == [CAT]
    assert result.product_urls == PRODUCTS[:1]


@pytest.mark.parametrize(
    "next_href",
    [f"{CAT}page/2/", f"{CAT}?page=2", f"{CAT}?paged=2", f"{CAT}trang-2"],
)
def test_four_pagination_conventions_go_through_one_path(next_href):
    pages = {CAT: _grid(PRODUCTS[:1], f'<a href="{next_href}">2</a>'), next_href: _grid(PRODUCTS[1:2])}

    result = crawl_category(_Fetcher(pages), CAT, PRODUCTS)

    assert sorted(result.product_urls) == sorted(PRODUCTS[:2])


def test_failed_fetch_is_not_an_empty_category():
    """Bat bien 2."""
    result = crawl_category(_Fetcher({}), CAT, PRODUCTS)

    assert result.ok is False
    assert result.error
    assert result.product_urls == []


def test_genuinely_empty_category_is_ok():
    result = crawl_category(_Fetcher({CAT: _grid([])}), CAT, PRODUCTS)

    assert result.ok is True
    assert result.product_urls == []


def test_broken_sub_page_keeps_what_was_collected():
    pages = {CAT: _grid(PRODUCTS[:2], f'<a href="{CAT}page/2/">2</a>')}  # page/2 hong

    result = crawl_category(_Fetcher(pages), CAT, PRODUCTS)

    assert result.ok is True
    assert sorted(result.product_urls) == sorted(PRODUCTS[:2])


def test_category_name_comes_from_the_page():
    result = crawl_category(_Fetcher({CAT: _grid(PRODUCTS)}), CAT, PRODUCTS)

    assert result.category_name == "Đèn LED âm trần"


def test_max_pages_bounds_the_walk():
    """Phan trang hong (trang N tro ve trang N+1 mai) khong duoc keo vo han."""
    pages = {CAT: _grid(PRODUCTS[:1], f'<a href="{CAT}page/2/">2</a>')}
    for i in range(2, 60):
        pages[f"{CAT}page/{i}/"] = _grid([], f'<a href="{CAT}page/{i + 1}/">next</a>')

    result = crawl_category(_Fetcher(pages), CAT, PRODUCTS, max_pages=5)

    assert result.pages_fetched == 5
