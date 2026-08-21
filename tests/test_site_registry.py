"""Thêm một đối thủ mới không được đẻ thêm một file .py.

Domain chưa đăng ký phải chạy được ngay bằng hành vi mặc định; phần riêng của
site (nếu đo thấy cần) chỉ là MỘT DÒNG dữ liệu trong SITE_PROFILES.
"""
from crawler.sites import get_profile, select_product_urls


def test_unknown_domain_works_with_defaults():
    """Đây là tính chất quan trọng nhất của registry: site chưa từng khảo sát
    vẫn crawl được, không cần khai báo gì trước."""
    profile = get_profile("https://mot-doi-thu-moi.vn")

    assert profile.product_url_pattern is None
    assert profile.fetch_options == {}


def test_unknown_domain_keeps_every_url_from_sitemap():
    urls = ["https://moi.vn/den-a", "https://moi.vn/den-b"]

    assert select_product_urls(urls, "https://moi.vn") == sorted(urls)


def test_homepage_and_duplicates_are_dropped_for_every_site():
    """Sitemap thật có trùng lặp: KingLED khai 557 mục cho 549 URL riêng biệt.

    Bản trùng bị bỏ, nhưng bản GIỮ LẠI là dạng gặp đầu tiên và giữ nguyên văn -
    không bị chuẩn hoá dấu `/` (xem test bên dưới).
    """
    urls = [
        "https://kingled.com.vn/",
        "https://kingled.com.vn/den-a/",
        "https://kingled.com.vn/den-a",
        "https://kingled.com.vn/den-b",
    ]

    assert select_product_urls(urls, "https://kingled.com.vn") == [
        "https://kingled.com.vn/den-a/",
        "https://kingled.com.vn/den-b",
    ]


def test_url_pattern_is_applied_only_where_registered():
    """TLC: product-sitemap.xml còn lẫn trang lưu trữ /shop/, lọc lại được bằng
    pattern đường dẫn. KingLED: URL sản phẩm và URL danh mục đều phẳng nên
    KHÔNG có pattern nào lọc được - phải dựa vào phân tách của sitemap."""
    tlc = ["https://tlclighting.com.vn/shop/", "https://tlclighting.com.vn/san-pham/x"]

    assert select_product_urls(tlc, "https://tlclighting.com.vn") == [
        "https://tlclighting.com.vn/san-pham/x"
    ]
    assert get_profile("https://kingled.com.vn").product_url_pattern is None


def test_js_rendered_site_declares_wait_selector_as_data():
    """KingLED chỉ render thông số sau khi JS chạy. Điều đó là 1 dòng dữ liệu,
    không phải một module riêng."""
    options = get_profile("https://kingled.com.vn").fetch_options

    assert options == {"wait_selector": 'div.property[data-id="Property"] label'}


def test_trailing_slash_of_the_source_url_is_preserved():
    """Dấu `/` cuối là quy ước RIÊNG của từng site: cả 486 URL của TLC
    (WooCommerce) đều có, KingLED thì không URL nào có.

    Từng cắt dấu `/` cho "gọn" và đó là hồi quy thật: cột `Link sản phẩm` không
    còn là URL chính tắc, và cơ chế crawl-lại-có-chọn-lọc đối chiếu theo URL nên
    toàn bộ dataset cũ mất khớp - mỗi lần chạy sau đều phải crawl lại từ đầu.
    """
    tlc = ["https://tlclighting.com.vn/san-pham/den-a/"]

    assert select_product_urls(tlc, "https://tlclighting.com.vn") == tlc


def test_duplicates_differing_only_by_trailing_slash_keep_the_first_form():
    urls = ["https://moi.vn/den-a", "https://moi.vn/den-a/"]

    assert select_product_urls(urls, "https://moi.vn") == ["https://moi.vn/den-a"]
