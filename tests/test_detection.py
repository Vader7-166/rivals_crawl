"""Task 9.1: bo phat hien "trang lưới sản phẩm thật" - dung fixture that tu Roman.vn.

roman_landing_page.html = /den-led-am-tran.html (trang danh muc cap cha, thuc
chat la landing SEO rong - "bay" da phat hien luc explore).
roman_listing_page.html = /den-downlight-led.html (danh muc con, luoi san
pham that voi ~50 san pham).
"""
from crawler.probing.detection import analyze_page


def test_roman_landing_page_is_not_a_real_listing(fixture_html):
    html = fixture_html("roman_landing_page.html")

    signals = analyze_page(html)

    assert signals.looks_like_product_listing is False


def test_roman_real_listing_page_is_detected(fixture_html):
    html = fixture_html("roman_listing_page.html")

    signals = analyze_page(html)

    assert signals.looks_like_product_listing is True


def test_single_product_pages_are_detected_across_sites(fixture_html):
    for fixture_name in ("roman_product.html", "tlc_product.html", "kingled_product.html"):
        html = fixture_html(fixture_name)

        signals = analyze_page(html)

        assert signals.looks_like_single_product_page is True, fixture_name
