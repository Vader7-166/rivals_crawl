"""Chi muc danh muc: luu tru va tra cuu pham vi (tasks 2.4-2.8, 2.10)."""
import pytest

from crawler.category_index import build_category_index
from crawler.probing.category_crawl import CategoryCrawlResult
from crawler.record.schema import CrawlStatus, ProductRecord
from crawler.store import CategoryStore, CrawlStore, connect

BASE = "https://kingled.com.vn"
DOMAIN = "kingled.com.vn"
CAT_A = f"{BASE}/am-tran-downlight"
CAT_B = f"{BASE}/den-panel"
PRODUCTS = [f"{BASE}/sp-{i}" for i in range(6)]


@pytest.fixture
def stores(tmp_path):
    conn = connect(tmp_path / "t.db")
    crawl = CrawlStore(conn)
    crawl.ensure_site(BASE, BASE)
    yield CategoryStore(conn), crawl
    conn.close()


def _result(url, name, products, ok=True, error=None, pages=1):
    return CategoryCrawlResult(
        category_url=url, category_name=name, product_urls=list(products),
        pages_fetched=pages, ok=ok, error=error,
    )


def _save_ok_record(crawl: CrawlStore, url: str) -> None:
    """Mot ban ghi trang thai OK - tuc URL nay KHONG con la ung vien crawl."""
    record = ProductRecord(
        product_id="1", ten_san_pham="x", ma_san_pham="m", category_1="c",
        link_san_pham=url, link_anh_san_pham="i", gia=1.0, tags={"a": "b"},
    )
    record.recompute_status()
    assert record.crawl_status == CrawlStatus.OK
    crawl.save_extraction(record, snapshot_id=None, extractor_version="v1")


# -- 2.4/2.5 luu canh --------------------------------------------------------


def test_edges_are_saved_and_read_back(stores):
    cat_store, _ = stores

    cat_store.save_category(DOMAIN, _result(CAT_A, "Âm trần", PRODUCTS[:3]))

    assert cat_store.product_urls_in(DOMAIN, [CAT_A]) == sorted(PRODUCTS[:3])
    assert cat_store.category_names(DOMAIN) == [(DOMAIN, CAT_A, "Âm trần")]


def test_a_product_can_belong_to_two_categories(stores):
    cat_store, _ = stores
    cat_store.save_category(DOMAIN, _result(CAT_A, "A", PRODUCTS[:3]))
    cat_store.save_category(DOMAIN, _result(CAT_B, "B", PRODUCTS[2:5]))

    assert PRODUCTS[2] in cat_store.product_urls_in(DOMAIN, [CAT_A])
    assert PRODUCTS[2] in cat_store.product_urls_in(DOMAIN, [CAT_B])
    # Hop cua hai danh muc: khong trung lap
    assert cat_store.product_urls_in(DOMAIN, [CAT_A, CAT_B]) == sorted(set(PRODUCTS[:5]))


def test_reindexing_replaces_edges_instead_of_piling_up(stores):
    """Cache dan xuat: trang thai moi nhat cua site la trang thai dung."""
    cat_store, _ = stores
    cat_store.save_category(DOMAIN, _result(CAT_A, "A", PRODUCTS[:3]))

    cat_store.save_category(DOMAIN, _result(CAT_A, "A", PRODUCTS[:1]))

    assert cat_store.product_urls_in(DOMAIN, [CAT_A]) == PRODUCTS[:1]


def test_clear_and_rebuild_gives_the_same_result(stores):
    cat_store, _ = stores
    cat_store.save_category(DOMAIN, _result(CAT_A, "A", PRODUCTS[:3]))
    before = cat_store.product_urls_in(DOMAIN, [CAT_A])

    cat_store.clear_domain(DOMAIN)
    assert cat_store.has_index(DOMAIN) is False
    cat_store.save_category(DOMAIN, _result(CAT_A, "A", PRODUCTS[:3]))

    assert cat_store.product_urls_in(DOMAIN, [CAT_A]) == before


# -- 2.6 fetch hong khac danh muc rong ---------------------------------------


def test_failed_category_is_distinguishable_from_empty_one(stores):
    cat_store, crawl = stores
    cat_store.save_category(DOMAIN, _result(CAT_A, None, [], ok=False, error="timeout", pages=0))
    cat_store.save_category(DOMAIN, _result(CAT_B, "Rỗng thật", []))

    by_url = {s.url: s for s in cat_store.summarise(crawl, DOMAIN)}

    assert by_url[CAT_A].ok is False and by_url[CAT_A].error == "timeout"
    assert by_url[CAT_B].ok is True and by_url[CAT_B].error is None
    assert by_url[CAT_A].total == by_url[CAT_B].total == 0


# -- 2.7 tra cuu pham vi -----------------------------------------------------


def test_scope_counts_split_have_and_missing(stores):
    cat_store, crawl = stores
    cat_store.save_category(DOMAIN, _result(CAT_A, "A", PRODUCTS[:4]))
    _save_ok_record(crawl, PRODUCTS[0])
    _save_ok_record(crawl, PRODUCTS[1])

    summary = cat_store.summarise(crawl, DOMAIN)[0]

    assert (summary.total, summary.have, summary.missing) == (4, 2, 2)


def test_never_crawled_category_is_all_missing(stores):
    cat_store, crawl = stores
    cat_store.save_category(DOMAIN, _result(CAT_A, "A", PRODUCTS[:4]))

    summary = cat_store.summarise(crawl, DOMAIN)[0]

    assert (summary.total, summary.have, summary.missing) == (4, 0, 4)


def test_fully_crawled_category_needs_nothing(stores):
    cat_store, crawl = stores
    cat_store.save_category(DOMAIN, _result(CAT_A, "A", PRODUCTS[:2]))
    for url in PRODUCTS[:2]:
        _save_ok_record(crawl, url)

    summary = cat_store.summarise(crawl, DOMAIN)[0]

    assert summary.missing == 0


# -- 2.8 san pham khong thuoc danh muc nao -----------------------------------


def test_uncategorised_products_are_still_reachable(stores):
    cat_store, _ = stores
    cat_store.save_category(DOMAIN, _result(CAT_A, "A", PRODUCTS[:2]))

    orphans = cat_store.uncategorised_urls(DOMAIN, PRODUCTS)

    assert orphans == PRODUCTS[2:]


def test_has_index_separates_unknown_from_empty(stores):
    cat_store, _ = stores

    assert cat_store.has_index(DOMAIN) is False
    cat_store.save_category(DOMAIN, _result(CAT_A, "A", []))
    assert cat_store.has_index(DOMAIN) is True


# -- 2.5/2.10 hàm dựng + đối chiếu độ phủ ------------------------------------


class _Fetcher:
    def __init__(self, pages):
        self._pages = pages
        self.fetched = []

    def fetch(self, url, **kw):
        self.fetched.append(url)
        html = self._pages.get(url)
        return type(
            "R", (), {"ok": html is not None, "html": html or "", "error": None, "status": 200}
        )()


def _grid(name, links):
    body = "".join(f'<a href="{h}">x</a>' for h in links)
    return f"<html><body><h1>{name}</h1>{body}</body></html>"


def test_build_reports_coverage_gap(stores):
    """2.10: chênh lệch sitemap vs chỉ mục phải được BÁO RA."""
    cat_store, _ = stores
    fetcher = _Fetcher({CAT_A: _grid("A", PRODUCTS[:4]), CAT_B: _grid("B", PRODUCTS[4:5])})

    report = build_category_index(cat_store, fetcher, DOMAIN, [CAT_A, CAT_B], PRODUCTS)

    assert report.products_in_sitemap == 6
    assert report.products_indexed == 5
    assert report.products_uncategorised == 1
    assert any("không thuộc trang danh mục nào" in w for w in report.warnings)


def test_build_reports_failed_categories(stores):
    cat_store, _ = stores
    fetcher = _Fetcher({CAT_A: _grid("A", PRODUCTS)})  # CAT_B hong

    report = build_category_index(cat_store, fetcher, DOMAIN, [CAT_A, CAT_B], PRODUCTS)

    assert (report.categories_ok, report.categories_failed) == (1, 1)
    assert any("fetch không thành công" in w for w in report.warnings)


def test_build_never_fetches_a_product_page(stores):
    cat_store, _ = stores
    fetcher = _Fetcher({CAT_A: _grid("A", PRODUCTS)})

    build_category_index(cat_store, fetcher, DOMAIN, [CAT_A], PRODUCTS)

    assert fetcher.fetched == [CAT_A]


def test_build_warns_when_probe_has_no_listing_urls(stores):
    """Probe cache cu (dung truoc khi co tang 0.5) khong co listing_urls - phai
    noi ro la chay lai probe, khong phai im lang tra ve 0."""
    cat_store, _ = stores

    report = build_category_index(cat_store, _Fetcher({}), DOMAIN, [], PRODUCTS)

    assert report.categories_total == 0
    assert any("--refresh-probe" in w for w in report.warnings)


def test_limit_suppresses_the_coverage_warning(stores):
    """Chay 5/138 danh muc thi "93% khong thuoc danh muc nao" la DUNG theo dinh
    nghia, khong phai dau hieu hong. Canh bao nao cung keu thi khong canh bao
    nao duoc doc."""
    cat_store, _ = stores
    fetcher = _Fetcher({CAT_A: _grid("A", PRODUCTS[:1]), CAT_B: _grid("B", PRODUCTS[1:2])})

    limited = build_category_index(cat_store, fetcher, DOMAIN, [CAT_A, CAT_B], PRODUCTS, limit=1)
    assert not any("không thuộc trang danh mục nào" in w for w in limited.warnings)

    cat_store.clear_domain(DOMAIN)
    full = build_category_index(cat_store, fetcher, DOMAIN, [CAT_A, CAT_B], PRODUCTS)
    assert any("không thuộc trang danh mục nào" in w for w in full.warnings)
