"""Tang 0 nhanh du phong - tim URL san pham khi site khong co sitemap.

Ba dieu duoc chot o day, deu lay tu do that tren trang that (xem docstring cua
`probing/product_discovery.py`):
  1. Trang landing KHONG phai luoi van duoc di tiep mot chang - menu cua Roman
     tro toi landing, chinh landing moi tro toi luoi san pham.
  2. Ung vien lay tu THE ANH tren luoi, khong phai moi link - neu khong thi
     menu/footer/chinh sach lan vao dataset.
  3. Nhom URL LAN LON (site de URL phang nhu Roman) phai duoc kiem tung URL,
     khong duoc doan bua theo mau cho ca nhom.
"""
from crawler.probing.product_discovery import (
    MAX_LISTING_DEPTH,
    discover_product_urls,
    url_shape,
)


class _Result:
    def __init__(self, html=None):
        self.html = html or ""
        self.ok = html is not None
        self.error = None if html is not None else "404"


class _Fetcher:
    def __init__(self, pages: dict[str, str]):
        self._pages = pages
        self.fetched: list[str] = []

    def fetch(self, url, **kwargs):
        self.fetched.append(url)
        html = self._pages.get(url)
        return _Result(html)


BASE = "https://roman.vn"


def _cards(hrefs: str | list, extra: str = "") -> str:
    """Trang co N the <a> boc <img> - dung khuon ma detection.py dem."""
    hrefs = list(hrefs)
    body = "".join(f'<a href="{h}"><img src="/i.png"></a>' for h in hrefs)
    return f"<html><body>{body}{extra}</body></html>"


def _grid(hrefs, extra: str = "") -> str:
    """Luoi san pham that: du the anh de vuot CARD_LINK_THRESHOLD (30)."""
    filler = [f"{BASE}/filler-{i}.html" for i in range(31 - len(list(hrefs)))]
    return _cards(list(hrefs) + filler, extra)


def _product(price: str = "199.000đ") -> str:
    """Trang san pham that: co gia VA co bang thong so du nhieu truong."""
    return (
        f"<html><body><h1>Đèn</h1><p>Giá: {price}</p><table>"
        "<tr><td>Công suất</td><td>9W</td></tr>"
        "<tr><td>Quang thông</td><td>800lm</td></tr>"
        "<tr><td>Điện áp</td><td>220V</td></tr>"
        "<tr><td>Nhiệt độ màu</td><td>3000K</td></tr>"
        "<tr><td>Tuổi thọ</td><td>30.000h</td></tr>"
        "<tr><td>Bảo hành</td><td>24 tháng</td></tr>"
        "</table></body></html>"
    )


def _plain(text: str = "Nội dung tĩnh") -> str:
    return f"<html><body><p>{text}</p></body></html>"


def _category(price: str = "199.000đ") -> str:
    """Trang danh muc kieu Roman: CO gia tren the hang, KHONG co muc thong so."""
    return f"<html><body><h1>Aptomat</h1><p>Giá: {price}</p></body></html>"


def test_di_tiep_mot_chang_qua_trang_landing():
    """Menu -> landing -> luoi: do sau 2 chang, dung ca Roman."""
    products = [f"{BASE}/den-{i}.html" for i in range(3)]
    pages = {
        BASE: _cards([f"{BASE}/den-noi-that.html"]),
        f"{BASE}/den-noi-that.html": _cards([f"{BASE}/den-downlight-led.html"]),
        f"{BASE}/den-downlight-led.html": _grid(products),
    }
    pages.update({u: _product() for u in products})
    pages.update({f"{BASE}/filler-{i}.html": _product() for i in range(31)})

    report = discover_product_urls(BASE, _Fetcher(pages))

    assert set(products) <= set(report.product_urls)
    assert f"{BASE}/den-downlight-led.html" in report.listing_urls


def test_khong_di_qua_gioi_han_chang():
    """Chang thu 3 duoc KIEM nhu ung vien, nhung khong duoc DI TIEP tu no.

    Gioi han chang la thu giu tang 0 khoi bien thanh crawler bo toan site: mot
    trang o ngoai gioi han van duoc do xem co phai san pham khong (mot luot
    fetch), nhung link tren no thi khong duoc lan theo nua.
    """
    ngoai_gioi_han = f"{BASE}/qua-sau.html"
    pages = {
        BASE: _cards([f"{BASE}/a.html"]),
        f"{BASE}/a.html": _cards([f"{BASE}/b.html"]),
        f"{BASE}/b.html": _cards([f"{BASE}/c.html"]),
        f"{BASE}/c.html": _cards([ngoai_gioi_han]),
        ngoai_gioi_han: _product(),
    }
    fetcher = _Fetcher(pages)

    report = discover_product_urls(BASE, fetcher)

    assert MAX_LISTING_DEPTH == 2
    assert f"{BASE}/c.html" in fetcher.fetched  # ung vien -> duoc kiem
    assert ngoai_gioi_han not in fetcher.fetched  # nhung khong di tiep tu c
    assert ngoai_gioi_han not in report.product_urls


def test_chi_lay_link_boc_anh_tren_luoi():
    """Link chinh sach/menu tren cung trang luoi khong duoc thanh ung vien."""
    product = f"{BASE}/den-op-tran.html"
    policy = f"{BASE}/chinh-sach-doi-tra.html"
    pages = {
        BASE: _grid([product], extra=f'<a href="{policy}">Chính sách</a>'),
        product: _product(),
        policy: _product(),  # co ca gia o footer, van khong duoc lot vao
    }
    pages.update({f"{BASE}/filler-{i}.html": _product() for i in range(31)})
    fetcher = _Fetcher(pages)

    report = discover_product_urls(BASE, fetcher)

    assert product in report.product_urls
    assert policy not in report.product_urls
    assert policy not in fetcher.fetched


def test_nhom_lan_lon_duoc_kiem_tung_url():
    """URL phang: san pham va trang tinh cung hinh dang `/*.html`.

    Dung ti le do duoc tren Roman - nhom `/*.html` gom 94 ung vien vua san pham
    vua danh muc. Mau roi vao khoang giua thi phai kiem NOT nhung URL ngoai
    mau, khong duoc nhan/loai ca nhom.
    """
    products = [f"{BASE}/den-{i}.html" for i in range(20)]
    junk = [f"{BASE}/muc-{i}.html" for i in range(16)]
    pages = {BASE: _cards(products + junk)}
    pages.update({u: _product() for u in products})
    pages.update({u: _plain() for u in junk})
    fetcher = _Fetcher(pages)

    report = discover_product_urls(BASE, fetcher)

    assert sorted(report.product_urls) == sorted(products)
    verdict = next(v for v in report.shapes if v.shape == "/*.html")
    assert verdict.decision == "kiem-tung-url"
    # Kiem tung URL nghia la MOI ung vien deu duoc fetch dung mot lan.
    assert sorted(set(fetcher.fetched)) == sorted({BASE} | set(products) | set(junk))


def test_nhom_thuan_duoc_nhan_ca_nhom_khong_fetch_het():
    """Site sach (VNE: `/index.php/product/*`): 5 mau la du cho ca 40 URL."""
    urls = [f"{BASE}/index.php/product/den-{i}/" for i in range(40)]
    pages = {BASE: _grid(urls)}
    pages.update({u: _product() for u in urls})
    pages.update({f"{BASE}/filler-{i}.html": _plain() for i in range(31)})
    fetcher = _Fetcher(pages)

    report = discover_product_urls(BASE, fetcher)

    assert set(urls) <= set(report.product_urls)
    assert sum(1 for u in fetcher.fetched if "/product/" in u) == 5


def test_tran_so_trang_duoc_ton_trong():
    """Nhom lan lon phai kiem tung URL - tran cat luot kiem va bao ra bao cao."""
    urls = [f"{BASE}/muc-{i}.html" for i in range(50)]
    pages = {BASE: _grid(urls)}
    for i, u in enumerate(urls):
        pages[u] = _product() if i % 2 == 0 else _plain()
    fetcher = _Fetcher(pages)

    report = discover_product_urls(BASE, fetcher, page_budget=3)

    assert len(fetcher.fetched) <= 3
    assert report.budget_exhausted
    assert len(report.product_urls) < 25  # 25 = so san pham that trong site gia


def test_url_shape():
    assert url_shape("https://x.vn/index.php/product/den-led-9w/") == "/index.php/product/*"
    assert url_shape("https://x.vn/den-op-tran-elt7128.html") == "/*.html"
    assert url_shape("https://x.vn/a/b/plist.php?lay3=AL30&x=1") == "/a/b/*.php?lay3,x"


def _with_nav(nav_hrefs, body_html: str) -> str:
    """Trang co menu dieu huong that (the <nav>), giong site that."""
    menu = "".join(f'<a href="{h}">m</a>' for h in nav_hrefs)
    return f"<html><body><nav>{menu}</nav>{body_html}</body></html>"


def test_danh_muc_trong_menu_khong_thanh_san_pham():
    """Case Roman: `aptomat.html` la danh muc nhung cham diem y het san pham.

    Menu la thu duy nhat tach duoc hai loai - danh muc nam trong menu, san pham
    thi khong.
    """
    category = f"{BASE}/aptomat.html"
    products = [f"{BASE}/den-{i}.html" for i in range(35)]
    pages = {
        BASE: _with_nav([category], _cards(products + [category])),
        category: _category(),  # co gia, cham dung nhu mot trang san pham
    }
    pages.update({u: _product() for u in products})

    report = discover_product_urls(BASE, _Fetcher(pages))

    assert category not in report.product_urls
    assert set(products) <= set(report.product_urls)


def test_trang_khong_co_the_menu_van_giu_duoc_san_pham():
    """Khong co <nav>: khong duoc lay CA TRANG lam menu roi vut sach ung vien."""
    products = [f"{BASE}/den-{i}.html" for i in range(35)]
    pages = {BASE: _cards(products)}
    pages.update({u: _product() for u in products})

    report = discover_product_urls(BASE, _Fetcher(pages))

    assert set(products) <= set(report.product_urls)


def test_quy_tac_san_pham_do_tren_fixture_that():
    """Chot quy tac tren HTML that cua 4 site, khong phai tren site gia.

    Day la phep do da quyet dinh cong thuc `_is_product_page`: so truong thong
    so tach dung cac trang "rac" cua Roman khoi trang san pham that, ke ca
    `tlc_product.html` - trang san pham co 30+ the anh nen bi cham la trang
    luoi, va `denvinaled_product.html` - trang san pham khong co gia lan
    structured data.
    """
    from pathlib import Path

    from crawler.probing.detection import analyze_page
    from crawler.probing.product_discovery import _is_product_page

    fixtures = Path(__file__).parent / "fixtures"
    expected = {
        "roman_product.html": True,
        "tlc_product.html": True,
        "kingled_product.html": True,
        "dienquang_product.html": True,
        "denvinaled_product.html": True,
        "roman_landing_page.html": False,
        "roman_listing_page.html": False,
    }
    for name, is_product in expected.items():
        html = (fixtures / name).read_text(encoding="utf-8", errors="ignore")
        assert _is_product_page(analyze_page(html)) is is_product, name


def test_theme_khong_boc_anh_van_ra_san_pham():
    """Case VNE: trang danh muc 100 link san pham ma chi 1 the anh.

    Loc theo the anh thi ca site cho ra 0 ung vien; dau hieu thay the la link
    lap lai cung mot hinh dang.
    """
    products = [f"{BASE}/index.php/product/den-{i}/" for i in range(12)]
    links = "".join(f'<a href="{u}">Đèn {u}</a>' for u in products)
    pages = {
        BASE: _with_nav([f"{BASE}/index.php/san-pham/"], "<p>trang chủ</p>"),
        f"{BASE}/index.php/san-pham/": f"<html><body>{links}</body></html>",
    }
    pages.update({u: _product() for u in products})

    report = discover_product_urls(BASE, _Fetcher(pages))

    assert sorted(report.product_urls) == sorted(products)


def test_nhom_bi_loai_thi_vut_ca_mau_trung():
    """Case VNE: 1 bai blog trong nhom bai blog cham dat vi liet ke du thong so.

    Nhom bi loai thi vut ca no - ket luan cua ca nhom manh hon mot lan cham le.
    """
    blogs = [f"{BASE}/tin-tuc/bai-{i}/" for i in range(12)]
    pages = {BASE: _cards(blogs)}
    # Chi bai dau tien "giong" trang san pham; 11 bai con lai la van xuoi.
    pages[blogs[0]] = _product()
    pages.update({u: _plain() for u in blogs[1:]})

    report = discover_product_urls(BASE, _Fetcher(pages))

    assert report.product_urls == []
    assert next(v for v in report.shapes if v.candidates == 12).decision == "loai-ca-nhom"


def test_bai_viet_co_ngay_trong_duong_dan_bi_loai():
    """Permalink WordPress `/2022/08/05/<slug>/` la bai viet, khong phai san pham."""
    posts = [f"{BASE}/index.php/2022/08/05/bai-{i}/" for i in range(8)]
    products = [f"{BASE}/index.php/product/den-{i}/" for i in range(8)]
    pages = {BASE: _cards(posts + products)}
    pages.update({u: _product() for u in posts + products})  # ca hai deu "giong" san pham

    report = discover_product_urls(BASE, _Fetcher(pages))

    assert sorted(report.product_urls) == sorted(products)


def test_khong_ton_luot_fetch_cho_file_anh():
    """The anh tro thang toi file .jpg (lightbox) - biet truoc tu duoi file.

    Do tren Roman: 122 ung vien kieu nay lam luot do cham tran 400 trang.
    """
    images = [f"{BASE}/pic/Product/anh-{i}.jpg" for i in range(10)]
    products = [f"{BASE}/den-{i}.html" for i in range(10)]
    pages = {BASE: _cards(products + images)}
    pages.update({u: _product() for u in products})
    fetcher = _Fetcher(pages)

    report = discover_product_urls(BASE, fetcher)

    assert sorted(report.product_urls) == sorted(products)
    assert not [u for u in fetcher.fetched if u.endswith(".jpg")]


def test_di_tiep_xuong_danh_muc_con():
    """Cây danh mục 2 tầng: trang lưới phải mở được danh mục con của nó.

    Case Nanoco: từ một cửa vào chỉ ra 17 sản phẩm vì danh mục con không bao
    giờ được mở. Chỉ đi theo link có hình dạng KHÁC hình dạng chiếm đa số —
    hình dạng đa số là thẻ sản phẩm, đi theo chúng thì tầng 0 fetch hết mọi
    sản phẩm.
    """
    tren = [f"{BASE}/san-pham/den-{i}/" for i in range(10)]
    duoi = [f"{BASE}/san-pham/den-con-{i}/" for i in range(10)]
    danh_muc_con = f"{BASE}/danh-muc/den-op-tran/"
    pages = {
        BASE: _cards(tren + [danh_muc_con]),
        danh_muc_con: _cards(duoi),
    }
    pages.update({u: _product() for u in tren + duoi})
    fetcher = _Fetcher(pages)

    report = discover_product_urls(BASE, fetcher)

    assert set(tren + duoi) <= set(report.product_urls)
    assert danh_muc_con in fetcher.fetched


def test_product_url_pattern_chan_trang_danh_muc_bi_cham_nham():
    """panasonic.net: trang danh muc `plist.php?lay3=` liet ke san pham kem
    thong so nen dat nguong 5 truong va bi cham la SAN PHAM - tang do dung
    ngay tai do, khong bao gio xuong toi `pspec.php?id=`.

    Site DA khai `product_url_pattern="pspec.php"`. Dung no ngay trong luc do
    thi trang danh muc khong the la san pham nua."""
    from crawler.probing.product_discovery import _co_the_la_san_pham

    plist = "https://panasonic.net/electricworks/lighting/vn/products/plist.php?lay3=AL300040"
    pspec = "https://panasonic.net/electricworks/lighting/vn/products/pspec.php?id=G00025989"

    assert _co_the_la_san_pham(pspec, "pspec.php") is True
    assert _co_the_la_san_pham(plist, "pspec.php") is False


def test_khong_khai_pattern_thi_khong_loai_gi():
    """Site chua khao sat khong bi ap luat cua site khac - giu nguyen nguyen
    tac cua registry."""
    from crawler.probing.product_discovery import _co_the_la_san_pham

    assert _co_the_la_san_pham("https://x.vn/bat-ky-url-nao", None) is True
    assert _co_the_la_san_pham("https://x.vn/bat-ky-url-nao", "") is True
