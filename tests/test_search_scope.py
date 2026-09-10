"""O tim kiem tu phan loai tu khoa (tasks 3.1-3.7).

Cac cap tu khoa duoi day lay tu DU LIEU THAT trong kho, khong phai vi du dat ra:
KingLED goi downlight la `ĐÈN DOWNLIGHT ÂM TRẦN`, TLC goi la `Đèn LED âm trần`
va con 9 bien the nua. Neu bat nguoi dung go dung dau va dung kieu hoa thuong
thi la bat ho doan xem doi thu go the nao.
"""
import pytest

from crawler.record.schema import CrawlStatus, ProductRecord
from crawler.scope import resolve
from crawler.search import ScopeKind, classify, match_brands, match_categories, normalise
from crawler.probing.category_crawl import CategoryCrawlResult
from crawler.store import CategoryStore, CrawlStore, connect

KINGLED = "kingled.com.vn"
TLC = "tlclighting.com.vn"

# (domain, url danh muc, ten) - dung dang ma CategoryStore.category_names() tra ve
CATEGORIES = [
    (KINGLED, f"https://{KINGLED}/am-tran-downlight", "ĐÈN DOWNLIGHT ÂM TRẦN"),
    (KINGLED, f"https://{KINGLED}/den-led-am-tran", "ĐÈN LED ÂM TRẦN"),
    (KINGLED, f"https://{KINGLED}/den-led-panel", "ĐÈN LED PANEL"),
    (TLC, f"https://{TLC}/danh-muc/den-led-am-tran/", "Đèn LED âm trần"),
    (TLC, f"https://{TLC}/danh-muc/khoi-duc/", "Đèn LED âm trần khối đúc"),
    (TLC, f"https://{TLC}/danh-muc/eyecare-pro/", "Đèn LED âm trần thế hệ mới Eyecare Pro"),
]


# -- 3.2 chuan hoa chuoi -----------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Đèn LED âm trần", "den led am tran"),
        ("ĐÈN DOWNLIGHT ÂM TRẦN", "den downlight am tran"),
        ("  Đèn   LED  ", "den led"),
        (None, ""),
    ],
)
def test_normalise(raw, expected):
    assert normalise(raw) == expected


def test_d_with_stroke_is_handled():
    """`đ` khong tach ra bang NFD - no la mot ky tu rieng chu khong phai `d` +
    dau. Thieu buoc thay tay thi `den` khong bao gio khop `đèn`."""
    assert normalise("Đèn") == "den"


def test_typing_without_diacritics_matches():
    matches = match_categories("den am tran", CATEGORIES)

    # KE CA "ĐÈN DOWNLIGHT ÂM TRẦN": no dung la den am tran, chi la KingLED
    # dat ten kem chu "downlight". Danh muc panel duy nhat bi loai.
    assert {m.category_name for m in matches} == {
        "ĐÈN DOWNLIGHT ÂM TRẦN",
        "ĐÈN LED ÂM TRẦN",
        "Đèn LED âm trần",
        "Đèn LED âm trần khối đúc",
        "Đèn LED âm trần thế hệ mới Eyecare Pro",
    }


def test_case_insensitive_match():
    matches = match_categories("downlight", CATEGORIES)

    assert [m.category_name for m in matches] == ["ĐÈN DOWNLIGHT ÂM TRẦN"]


# -- 3.1/3.3 nhan hieu -------------------------------------------------------


@pytest.mark.parametrize(
    "keyword, domain",
    [
        ("kingled", KINGLED),
        ("KingLED", KINGLED),
        ("King LED", KINGLED),
        ("ilike", KINGLED),
        ("kingled.com.vn", KINGLED),
        ("tlc", TLC),
        ("TLC Lighting", TLC),
    ],
)
def test_brand_aliases_all_resolve(keyword, domain):
    assert match_brands(keyword) == [domain]


def test_brand_wins_over_category():
    scope = classify("tlc", CATEGORIES)

    assert scope.kind is ScopeKind.BRAND
    assert scope.domains == [TLC]


def test_unknown_keyword_falls_back_to_product_name():
    scope = classify("AT04 110/12W", CATEGORIES)

    assert scope.kind is ScopeKind.PRODUCT_NAME


def test_empty_keyword_says_why():
    scope = classify("   ", CATEGORIES)

    assert scope.kind is ScopeKind.NONE
    assert scope.reason


# -- 3.4 tu khoa khop nhieu loai ---------------------------------------------


def test_ambiguous_keyword_offers_the_other_kind():
    """`den` khop danh muc; neu no cung khop mot nhan hieu thi nguoi dung phai
    chuyen duoc loai ma khong go lai."""
    categories = CATEGORIES + [(TLC, f"https://{TLC}/danh-muc/tlc-moi/", "Dòng TLC mới")]

    scope = classify("tlc", categories)

    assert scope.kind is ScopeKind.BRAND
    assert ScopeKind.CATEGORY in scope.alternatives


def test_prefer_switches_kind_without_retyping():
    categories = CATEGORIES + [(TLC, f"https://{TLC}/danh-muc/tlc-moi/", "Dòng TLC mới")]

    scope = classify("tlc", categories, prefer=ScopeKind.CATEGORY)

    assert scope.kind is ScopeKind.CATEGORY
    assert [m.category_name for m in scope.categories] == ["Dòng TLC mới"]
    assert ScopeKind.BRAND in scope.alternatives


# -- 3.6/3.7 pham vi co so lieu ----------------------------------------------


@pytest.fixture
def stores(tmp_path):
    conn = connect(tmp_path / "t.db")
    crawl = CrawlStore(conn)
    for domain in (KINGLED, TLC):
        crawl.ensure_site(f"https://{domain}", f"https://{domain}")
    yield CategoryStore(conn), crawl
    conn.close()


def _index(cat_store, domain, url, name, products):
    cat_store.save_category(
        domain,
        CategoryCrawlResult(
            category_url=url, category_name=name, product_urls=list(products),
            pages_fetched=1, ok=True,
        ),
    )


def _crawled(crawl, url):
    record = ProductRecord(
        product_id="1", ten_san_pham="Đèn LED âm trần 9W", ma_san_pham="m",
        category_1="c", link_san_pham=url, link_anh_san_pham="i", gia=1.0,
        tags={"a": "b"},
    )
    record.recompute_status()
    assert record.crawl_status == CrawlStatus.OK
    crawl.save_extraction(record, snapshot_id=None, extractor_version="v1")


def test_category_scope_spans_two_competitors(stores):
    cat_store, crawl = stores
    _index(cat_store, KINGLED, CATEGORIES[0][1], CATEGORIES[0][2],
           [f"https://{KINGLED}/sp-{i}" for i in range(3)])
    _index(cat_store, TLC, CATEGORIES[3][1], CATEGORIES[3][2],
           [f"https://{TLC}/san-pham/sp-{i}/" for i in range(2)])

    # "am tran" chu khong phai "downlight am tran": TLC khong dat chu
    # "downlight" trong ten danh muc nao, nen tu khoa do chi ra KingLED.
    resolved = resolve("am tran", crawl, cat_store)

    assert resolved.scope.kind is ScopeKind.CATEGORY
    assert [d.domain for d in resolved.domains] == [KINGLED, TLC]
    assert resolved.total == 5
    assert resolved.missing == 5


def test_scope_splits_have_and_missing(stores):
    cat_store, crawl = stores
    urls = [f"https://{KINGLED}/sp-{i}" for i in range(4)]
    _index(cat_store, KINGLED, CATEGORIES[0][1], CATEGORIES[0][2], urls)
    _crawled(crawl, urls[0])
    _crawled(crawl, urls[1])

    resolved = resolve("downlight", crawl, cat_store)

    assert (resolved.total, resolved.have, resolved.missing) == (4, 2, 2)
    assert resolved.is_fully_crawled is False


def test_fully_crawled_scope_needs_no_crawl(stores):
    cat_store, crawl = stores
    urls = [f"https://{KINGLED}/sp-{i}" for i in range(2)]
    _index(cat_store, KINGLED, CATEGORIES[0][1], CATEGORIES[0][2], urls)
    for url in urls:
        _crawled(crawl, url)

    resolved = resolve("downlight", crawl, cat_store)

    assert resolved.is_fully_crawled is True


def test_unticking_a_category_removes_it_from_scope(stores):
    cat_store, crawl = stores
    _index(cat_store, KINGLED, CATEGORIES[0][1], CATEGORIES[0][2], [f"https://{KINGLED}/a"])
    _index(cat_store, KINGLED, CATEGORIES[1][1], CATEGORIES[1][2], [f"https://{KINGLED}/b"])

    full = resolve("am tran", crawl, cat_store)
    trimmed = resolve(
        "am tran", crawl, cat_store, exclude_categories=frozenset({CATEGORIES[1][1]})
    )

    assert full.total == 2
    assert trimmed.total == 1


def test_domain_without_index_says_so_instead_of_zero(stores):
    """3.7: "chưa dựng chỉ mục" khac han "khong co san pham nao"."""
    cat_store, crawl = stores

    resolved = resolve("kingled", crawl, cat_store)

    assert resolved.scope.kind is ScopeKind.BRAND
    assert resolved.domains[0].needs_index is True


def test_indexed_domain_does_not_ask_for_index(stores):
    cat_store, crawl = stores
    _index(cat_store, KINGLED, CATEGORIES[0][1], CATEGORIES[0][2], [f"https://{KINGLED}/a"])

    resolved = resolve("kingled", crawl, cat_store)

    assert resolved.domains[0].needs_index is False
    assert resolved.domains[0].brand == "KingLED"


def test_product_name_search_finds_crawled_records(stores):
    cat_store, crawl = stores
    _crawled(crawl, f"https://{KINGLED}/den-am-tran-9w")

    resolved = resolve("am tran 9w", crawl, cat_store)

    assert resolved.scope.kind is ScopeKind.PRODUCT_NAME
    assert resolved.total == 1


def test_nothing_matches_anywhere_gives_a_reason(stores):
    cat_store, crawl = stores

    resolved = resolve("máy giặt", crawl, cat_store)

    assert resolved.scope.kind is ScopeKind.NONE
    assert "máy giặt" in resolved.scope.reason
    assert resolved.domains == []
