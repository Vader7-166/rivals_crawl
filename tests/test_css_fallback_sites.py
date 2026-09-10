"""Tang 1.5 cho 2 site ma tang 1 (structured data) khong du.

Ca hai deu la ca "structured data CO NHUNG SAI/THIEU", khac han ca Roman (khong
co structured data nao) da co truoc day - nen cung phai co test rieng:

- dienquang.com (Haravan): co microdata Product, nhung `price` la 0 cho san
  pham khong niem yet gia, va nhanh "hang cong trinh" thi KHONG co itemscope
  Product nao ca (mat luon anh). Khong co BreadcrumbList o bat ky nhanh nao.
- denvinaled.vn (WooCommerce + Flatsome): khong co Product o ca JSON-LD lan
  microdata - tang 1 tut xuong OpenGraph. BreadcrumbList thi CO nhung cap giua
  luon la trang "Cửa hàng", tuc mot gia tri sai chu khong phai mot o trong.
"""
from crawler.extraction import apply_css_fallback, extract_categories
from crawler.extraction.structured_data import extract_structured_data

DQ_URL = (
    "https://dienquang.com/products/den-led-bulb-dien-quang-chuyen-dung-"
    "thanh-long-dq-ledbutl-04rb-nn-4w-do-xanh-chup-trong"
)
DQ_CONG_TRINH_URL = "https://dienquang.com/products/den-duong-led-alley-2-100dl-v02-100w"
DV_URL = "https://denvinaled.vn/san-pham/den-led-am-tran-9w-vinaled-v11dlf-9/"


def _fallback(html: str, domain: str, structured) -> dict:
    return apply_css_fallback(
        html,
        {
            "gia": structured.gia,
            "gia_doi_chieu": None,
            "ma_san_pham": structured.ma_san_pham,
            "link_anh_san_pham": structured.link_anh_san_pham,
        },
        domain,
    )


def test_denvinaled_tier1_falls_all_the_way_to_opengraph(fixture_html):
    """Tien de cua moi test denvinaled con lai: khong co Product o cu phap nao,
    nen gia va ma san pham deu KHONG the den tu tang 1."""
    structured = extract_structured_data(fixture_html("denvinaled_product.html"), DV_URL)

    assert structured.source == "opengraph"
    assert structured.gia is None
    assert structured.ma_san_pham is None


def test_denvinaled_sale_price_takes_ins_not_the_first_amount(fixture_html):
    """`p.price` cua san pham dang giam gia co HAI con so: gia goc trong <del>
    dung TRUOC, gia ban trong <ins> dung sau. Lay con so dau tien la ghi nham
    gia goc vao cot Gia."""
    html = fixture_html("denvinaled_product.html")

    patched = _fallback(html, "denvinaled.vn", extract_structured_data(html, DV_URL))

    assert patched["gia"] == 283187.0
    assert patched["gia_doi_chieu"] == 435672.0


def test_denvinaled_sku_comes_from_product_meta(fixture_html):
    html = fixture_html("denvinaled_product.html")

    patched = _fallback(html, "denvinaled.vn", extract_structured_data(html, DV_URL))

    assert patched["ma_san_pham"] == "V11DLF-9"


def test_denvinaled_breadcrumb_says_shop_but_real_category_is_elsewhere(fixture_html):
    """Day la ly do denvinaled.vn duoc dang ky trong DOMAIN_CATEGORY_SELECTORS:
    tang 1 KHONG tra ve o trong ma tra ve mot gia tri SAI ("Cửa hàng"). Neu tin
    no thi ca 668 san pham roi vao dung mot sheet."""
    html = fixture_html("denvinaled_product.html")

    assert extract_structured_data(html, DV_URL).category_1 == "Cửa hàng"
    assert extract_categories(html, "denvinaled.vn") == (
        "Đèn LED Âm Trần VinaLED", None, None,
    )


def test_dienquang_zero_price_is_replaced_by_displayed_price(fixture_html):
    """dienquang.com khai `price=0` ke ca cho san pham dang hien gia that tren
    trang - `0` la gia tri mac dinh cua template, khong phai gia."""
    html = fixture_html("dienquang_product.html")
    structured = extract_structured_data(html, DQ_URL)
    assert structured.gia == 61200.0  # trang nay khai gia that

    patched = _fallback(html, "dienquang.com", structured)

    assert patched["gia"] == 61200.0
    assert patched["gia_doi_chieu"] == 68000.0


def test_dienquang_cong_trinh_page_has_no_product_microdata_at_all(fixture_html):
    """Nhanh "hang cong trinh" dung template khac: khong itemscope Product,
    khong og:image. Tang 1 chi con ten tu OpenGraph - anh va ma san pham phai
    do tang 1.5 vay lai."""
    html = fixture_html("dienquang_product_cong_trinh.html")
    structured = extract_structured_data(html, DQ_CONG_TRINH_URL)
    assert structured.source == "opengraph"
    assert structured.link_anh_san_pham is None

    patched = _fallback(html, "dienquang.com", structured)

    assert patched["ma_san_pham"] == "ALLEY 3 - 150"
    assert patched["link_anh_san_pham"].endswith(".png")
    assert patched["gia"] == "Liên hệ"


def test_dienquang_product_code_label_is_stripped(fixture_html):
    """Site gop nhan vao chinh o gia tri ("Mã sản phẩm: ALLEY 3 - 150") - khong
    co the rieng cho con so nen selector nao cung dinh ca nhan."""
    html = fixture_html("dienquang_product_cong_trinh.html")

    patched = _fallback(html, "dienquang.com", extract_structured_data(html, DQ_CONG_TRINH_URL))

    assert not patched["ma_san_pham"].startswith("Mã sản phẩm")


def test_dienquang_category_comes_from_the_breadcrumb_collection_link(fixture_html):
    """Microdata cua dienquang.com khong kem BreadcrumbList nao, nen tang 1 tra
    ve rong o ca ba cap category."""
    html = fixture_html("dienquang_product.html")
    structured = extract_structured_data(html, DQ_URL)
    assert structured.category_1 is None

    cat_1, cat_2, cat_3 = extract_categories(html, "dienquang.com")

    assert cat_1 == "ĐÈN LED - SIÊU SÁNG, BỀN & TIẾT KIỆM ĐIỆN NĂNG"
    assert (cat_2, cat_3) == (None, None)


def test_unregistered_domain_gets_no_categories_from_tier_1_5():
    """Giu nguyen nguyen tac cua registry: domain chua khao sat khong bi ap
    selector cua site khac, tang tren cu dung ket qua tang 1."""
    html = '<ol class="breadcrumb"><a href="/collections/x">X</a></ol>'

    assert extract_categories(html, "mot-doi-thu-moi.vn") == (None, None, None)


# --- vne-led.vn: tang 1 khong co GI de tut xuong ---------------------------
#
# Hai site tren deu con OpenGraph hoac microdata de tang 1 bam vao. vne-led.vn
# thi khong: JSON-LD duy nhat la BreadcrumbList va trang khong phat the og:*
# nao. Day la ca da lam lo ra rang `ten_san_pham` CHUA BAO GIO di qua tang 1.5
# - no lay thang tu tang 1 - nen 120/120 ban ghi mat ten du ten nam ro trong
# <h1 class="product_title">.

VNE_URL = "https://vne-led.vn/index.php/product/am-tran-7w-3-mau-mat-trang-tron-emc/"

VNE_HTML = """
<html><head><title>Âm trần 7W 3 màu mặt trắng trơn EMC</title>
<script type="application/ld+json">
{"@context":"https://schema.org/","@type":"BreadcrumbList","itemListElement":[
 {"@type":"ListItem","position":1,"item":{"name":"Home","@id":"https://vne-led.vn"}},
 {"@type":"ListItem","position":2,"item":{"name":"Đèn Led Dân Dụng",
  "@id":"https://vne-led.vn/index.php/product-category/den-led-dan-dung/"}},
 {"@type":"ListItem","position":3,"item":{"name":"Âm trần 7W 3 màu mặt trắng trơn EMC",
  "@id":"https://vne-led.vn/index.php/product/am-tran-7w-3-mau-mat-trang-tron-emc/"}}]}
</script></head>
<body>
  <h1 class="product_title">Âm trần 7W 3 màu mặt trắng trơn EMC</h1>
  <div class="product_meta"><span class="sku">VATE07/01</span></div>
  <figure class="woocommerce-product-gallery__wrapper">
    <img src="https://vne-led.vn/anh-600x600.jpg"
         data-large_image="https://vne-led.vn/anh-scaled.jpg">
  </figure>
  <div class="summary"><p class="price"></p></div>
</body></html>
"""


def test_vne_tang1_chi_ra_duoc_danh_muc_khong_ra_ten():
    """Chot lai DIEM XUAT PHAT: tang 1 tren site nay tra ve ten rong."""
    structured = extract_structured_data(VNE_HTML, VNE_URL)
    assert structured.ten_san_pham is None
    assert structured.link_anh_san_pham is None
    assert structured.category_1 == "Đèn Led Dân Dụng"


def test_ten_san_pham_duoc_va_boi_tang_1_5():
    """Test hoi quy cho loi day: `ten_san_pham` phai nam trong dict truyen cho
    apply_css_fallback. Bo no ra thi test nay do, con crawl that thi mat ten
    tren moi site khong co structured data lan OpenGraph."""
    structured = extract_structured_data(VNE_HTML, VNE_URL)
    patched = apply_css_fallback(
        VNE_HTML,
        {
            "gia": structured.gia,
            "gia_doi_chieu": None,
            "ma_san_pham": structured.ma_san_pham,
            "link_anh_san_pham": structured.link_anh_san_pham,
            "ten_san_pham": structured.ten_san_pham,
        },
        "vne-led.vn",
    )
    assert patched["ten_san_pham"] == "Âm trần 7W 3 màu mặt trắng trơn EMC"
    assert patched["ma_san_pham"] == "VATE07/01"


def test_anh_lay_ban_goc_khong_lay_thumbnail():
    """`src` la thumbnail 600x600 do WooCommerce sinh; anh that o
    `data-large_image`. Lay nham thi moi anh trong dataset deu bi thu nho."""
    patched = apply_css_fallback(
        VNE_HTML, {"link_anh_san_pham": None}, "vne-led.vn"
    )
    assert patched["link_anh_san_pham"] == "https://vne-led.vn/anh-scaled.jpg"


def test_khong_dang_ky_rule_gia_cho_vne():
    """VNE khong niem yet gia - `.summary .price` co that nhung rong tren moi
    trang da do. De trong moi dung; dang ky mot rule `gia` o day la mo duong
    cho tang 1.5 nhat bua mot con so nao do tren trang."""
    patched = apply_css_fallback(VNE_HTML, {"gia": None}, "vne-led.vn")
    assert patched["gia"] is None


# --- roman.vn: breadcrumb la thu duy nhat tach duoc san pham khoi bai viet --
#
# Roman de MOI trang o `/<slug>.html` - san pham, danh muc va bai blog cung
# mot hinh URL. Moi tin hieu NOI DUNG deu truot: bai "10 thong so den LED can
# biet" nhac du cong suat/quang thong/dien ap/nhiet do mau/CRI nen vuot ca
# nguong `spec_field_count >= 5` cua tang do.
#
# Trang VAN co breadcrumb - `div.breadCrumbBox`, chu C VIET HOA. Cac dot khao
# sat truoc tim bang `[class*=breadcrumb]` (CSS phan biet hoa thuong) nen ket
# luan nham "Roman khong co breadcrumb" va de trong 139/139 ban ghi. Chinh
# fixture nay da chua no tu dau.


def test_roman_co_breadcrumb_chu_C_viet_hoa(fixture_html):
    """Chot lai cai bay: selector chu thuong KHONG khop, chu hoa thi co."""
    html = fixture_html("roman_product.html")

    assert extract_categories(html, "roman.vn") != (None, None, None)


def test_roman_bo_hai_cap_dieu_huong_dau(fixture_html):
    """Giu "Trang chu"/"San pham" thi ca site roi vao mot sheet "San pham" -
    dung bang mat ca danh muc."""
    html = fixture_html("roman_product.html")

    cat_1, cat_2, cat_3 = extract_categories(html, "roman.vn")

    assert cat_1 == "Thiết bị chiếu sáng - Led"
    assert cat_2 == "Đèn nội thất"
    assert cat_3 == "Đèn Downlight LED"
