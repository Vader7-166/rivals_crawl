"""Task 9.2: structured-data extraction voi fixture JSON-LD va Microdata rieng
biet, dam bao khong hard-code theo 1 cu phap.
"""
from crawler.extraction.structured_data import extract_structured_data


def test_jsonld_site_extracts_name_price_image_and_category(fixture_html):
    html = fixture_html("tlc_product.html")

    result = extract_structured_data(
        html, "https://tlclighting.com.vn/san-pham/am-tran-eyecare-chong-am-10w-vien-bac-ba-mau/"
    )

    assert result.source == "json-ld"
    assert result.ten_san_pham == "Âm Trần Eyecare Chống Ẩm 10W Viền Bạc - Ba màu"
    assert result.gia == 166000.0
    assert result.link_anh_san_pham is not None
    assert result.category_1 == "Đèn LED âm trần"
    assert result.category_2 == "Đèn LED âm trần thế hệ mới Eyecare chống ẩm"
    assert result.category_3 is None


def test_microdata_only_site_is_not_missed(fixture_html):
    """KingLED khong co bat ky block JSON-LD nao - neu extractor hard-code
    theo JSON-LD se bo sot hoan toan site nay."""
    html = fixture_html("kingled_product.html")

    result = extract_structured_data(html, "https://kingled.com.vn/den-led-am-tran-downlight-12w-don-sac")

    assert result.source == "microdata"
    assert result.ten_san_pham == "Đèn Led Âm Trần Downlight Ruby 12W Đơn Sắc"
    assert result.ma_san_pham == "DL-12SS-T140"
    assert result.gia == 240000.0
    assert result.category_1 == "ĐÈN DOWNLIGHT ÂM TRẦN"
    assert result.category_2 == "TÁN QUANG ĐƠN SẮC"


def test_site_without_schema_org_falls_back_to_opengraph(fixture_html):
    """Roman khong co JSON-LD/Microdata/RDFa nao cho san pham - phai fallback
    ve OpenGraph va de trong cac field khac thay vi bao loi hoac bia du lieu."""
    html = fixture_html("roman_product.html")

    result = extract_structured_data(
        html, "https://roman.vn/den-led-downlight-am-tran-cam-bien-12w-eld9001.html"
    )

    assert result.source == "opengraph"
    assert result.ten_san_pham
    assert result.link_anh_san_pham is not None
    assert result.gia is None
    assert result.category_1 is None
