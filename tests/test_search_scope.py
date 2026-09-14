"""O tim kiem tu phan loai tu khoa (tasks 3.1-3.7).

Cac cap tu khoa duoi day lay tu DU LIEU THAT trong kho, khong phai vi du dat ra:
KingLED goi downlight la `ĐÈN DOWNLIGHT ÂM TRẦN`, TLC goi la `Đèn LED âm trần`
va con 9 bien the nua. Neu bat nguoi dung go dung dau va dung kieu hoa thuong
thi la bat ho doan xem doi thu go the nao.
"""
import pytest

from crawler.record.schema import CrawlStatus, ProductRecord
from crawler.scope import SuggestionIndex, resolve, suggestions
from crawler.search import (
    ScopeKind,
    classify,
    match_brands,
    match_categories,
    normalise,
    suggest,
)
from crawler.sites.registry import SITE_PROFILES
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


# -- 3.8 goi y khi dang go ---------------------------------------------------
#
# `classify()` tra loi "bam Enter thi crawl gi" - khop chat, tat dinh. Goi y tra
# loi cau khac: "go hai chu roi thi co the y nguoi dung la gi" - khop long hon,
# vi no khong cam ket gi ca, nguoi dung van phai bam.

# (domain, ten danh muc, so san pham da co) - dang ma `suggest()` nhan
CATEGORY_ROWS = [
    (KINGLED, "ĐÈN DOWNLIGHT ÂM TRẦN", 50),
    (KINGLED, "ĐÈN LED ÂM TRẦN", 40),
    (TLC, "Đèn LED âm trần", 30),
    (TLC, "Đèn LED dây", 12),
    # Cung mot ten o hai site khac nhau - phai gop lai thanh MOT dong
    (KINGLED, "Đèn đường", 7),
    (TLC, "Đèn đường", 3),
]


def test_led_is_not_a_brand_anymore():
    """Lo hong do duoc tren kho that: `led` la chuoi con cua `kingled` va
    `denvinaled`, nen khop chuoi con cho ra NHAN HIEU - va vi nhan hieu duoc uu
    tien truoc danh muc, tu pho bien nhat cua ca nganh nuot mat nhanh danh muc.
    """
    assert match_brands("led") == []

    scope = classify("led", CATEGORIES)

    assert scope.kind is not ScopeKind.BRAND


def test_word_boundary_does_not_break_spaced_aliases():
    """Doi sang khop theo ranh gioi tu KHONG duoc lam hong duong cu: `king led`
    van phai ra KingLED (nho bi danh "King LED"), va `den philips` van phai ra
    Philips (tu khoa CHUA khoa)."""
    assert match_brands("king led") == [KINGLED]
    assert match_brands("den philips") == [
        "philipsvietnam.com",
        "www.lighting.philips.com.vn",
    ]


@pytest.mark.parametrize("keyword, brand", [("mpe", "MPE"), ("vne", "VNE")])
def test_every_crawled_domain_is_reachable_by_brand(keyword, brand):
    """Hai site nay crawl duoc bang hanh vi mac dinh nen truoc day khong co
    `SiteProfile` nao - va vi the go ten nhan cua chung khong ra nhan hieu:
    `mpe` roi xuong nhanh ten san pham, con `vne` khop trung danh muc `Đèn VNE`
    cua chinh no."""
    domains = match_brands(keyword)

    assert len(domains) == 1
    assert SITE_PROFILES[domains[0]].brand_name == brand


def test_led_suggests_both_kinds_side_by_side():
    """Chinh vi du cua nguoi dung: go `led` thi duoi o tim kiem hien ca hai
    nhom - nhan hieu KingLED/VinaLED, va danh muc led am tran/led day."""
    result = suggest("led", categories=CATEGORY_ROWS, limit=10)

    assert "KingLED" in [s.label for s in result.brands]
    assert "TLC Lighting" not in [s.label for s in result.brands]
    # `ĐÈN DOWNLIGHT ÂM TRẦN` KHONG co trong danh sach du no cung la downlight:
    # ten do khong chua chu "led". Dung nhu vay - goi y bam theo chu nguoi dung
    # dang go, con viec "downlight cung la den led" la mot anh xa nganh hang,
    # thu ma ca change nay co chu dich khong dung (xem docstring search.py).
    # Hai site viet cung mot danh muc hai kieu (`ĐÈN LED ÂM TRẦN` cua KingLED
    # va `Đèn LED âm trần` cua TLC) - gop thanh MOT dong, ten hien thi lay theo
    # site nhieu san pham hon.
    assert [(s.label, s.products) for s in result.categories] == [
        ("ĐÈN LED ÂM TRẦN", 70),
        ("Đèn LED dây", 12),
    ]


def test_same_category_across_competitors_is_one_row():
    """"Đèn đường" co o ca hai site. Gop thanh mot dong dung voi cau hoi that
    ("lay hang den duong cua cac doi thu"); de rieng hai dong la bat nguoi dung
    bam hai lan cho cung mot y."""
    result = suggest("đèn đường", categories=CATEGORY_ROWS)

    assert len(result.categories) == 1
    assert result.categories[0].domains == (KINGLED, TLC)
    assert result.categories[0].products == 10


def test_two_sites_of_one_brand_are_one_row():
    """Philips co hai site (philipsvietnam.com va lighting.philips.com.vn).
    Voi nguoi dung do la MOT nhan - hien hai dong chi bat ho chon giua hai thu
    ho khong phan biet duoc."""
    result = suggest("philips", product_counts={"philipsvietnam.com": 847})

    assert [s.label for s in result.brands] == ["Philips"]
    assert result.brands[0].domains == (
        "philipsvietnam.com",
        "www.lighting.philips.com.vn",
    )
    assert result.brands[0].products == 847


def test_suggestions_rank_prefix_match_first():
    """Go `am` thi `ÂM TRẦN` sat y hon mot ten chi chua chuoi `am` o giua."""
    rows = CATEGORY_ROWS + [(TLC, "Đèn nam châm", 99)]

    result = suggest("am", categories=rows)

    assert result.categories[0].label.lower().startswith("đèn")
    assert [s.label for s in result.categories][-1] == "Đèn nam châm"


@pytest.mark.parametrize("keyword", ["led", "đèn đường", "philips"])
def test_clicking_a_suggestion_lands_on_its_own_kind(keyword):
    """HOP DONG cua `query`: no phai di kem `prefer`, khong duoc goi classify
    tran. Ca that: goi y danh muc `Đèn LED Âm Trần VinaLED` neu classify tran
    se ra NHAN HIEU VinaLED - bam mot danh muc 166 san pham lai duoc pham vi
    668 san pham cua ca nhan."""
    rows = CATEGORY_ROWS + [("denvinaled.vn", "Đèn LED Âm Trần VinaLED", 166)]
    cats = [(d, f"https://{d}/{normalise(n).replace(' ', '-')}", n) for d, n, _ in rows]

    for item in suggest(keyword, categories=rows).brands + suggest(
        keyword, categories=rows
    ).categories:
        assert classify(item.query, cats, prefer=item.kind).kind is item.kind


def test_empty_keyword_suggests_nothing():
    assert suggest("   ", categories=CATEGORY_ROWS).is_empty


def test_suggestion_index_reads_the_store_once_then_refreshes(stores):
    """Cache ton tai vi o tim kiem goi sau MOI phim: doc thang kho mat
    0,6-0,95s tren kho that. Doi lai, no phai lam moi duoc sau khi crawl xong -
    neu khong, san pham vua crawl khong bao gio hien ra trong goi y."""
    cat_store, crawl = stores
    index = SuggestionIndex(crawl, cat_store)

    assert index.suggest("am tran").categories == []

    _index(cat_store, KINGLED, CATEGORIES[0][1], CATEGORIES[0][2],
           [f"https://{KINGLED}/sp-1"])

    assert index.suggest("am tran").categories == []  # cache chua lam moi
    index.refresh()
    assert [s.label for s in index.suggest("am tran").categories] == [
        "ĐÈN DOWNLIGHT ÂM TRẦN"
    ]


def test_uncrawled_category_still_suggested_with_zero(stores):
    """Danh muc chi co trong chi muc (chua crawl) van phai hien ra - do chinh
    la dong nguoi dung can bam de tao job. Hien so 0 la dung su that, an di moi
    la sai."""
    cat_store, crawl = stores
    _index(cat_store, KINGLED, CATEGORIES[2][1], CATEGORIES[2][2],
           [f"https://{KINGLED}/panel-1"])

    result = suggestions("panel", crawl, cat_store)

    assert [(s.label, s.products) for s in result.categories] == [("ĐÈN LED PANEL", 0)]
