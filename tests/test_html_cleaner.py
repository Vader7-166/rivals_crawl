"""Regression test cho extract_spec_text (field "Thông số kỹ thuật").

2 bug thuc te da gap va sua:
1. thong_so_ky_thuat ban dau tai su dung thang output cua clean_html_for_llm
   (chua ca menu dieu huong + mo ta marketing dai) - phai tach rieng ham chi
   lay dung bang thong so ky thuat sach.
2. Sau khi tach rieng, phat hien them: strip tag <form> (tuong la vo hai, chi
   de bo cac form nho nhu tim kiem/lien he) lai xoa SACH TOAN BO noi dung
   trang Roman.vn - vi ASP.NET WebForms boc ca trang trong 1 <form id="form1">
   duy nhat. Phai bo "form" khoi danh sach strip.
"""
from crawler.llm.html_cleaner import extract_spec_text


def test_tlc_spec_text_excludes_category_menu_and_marketing_copy(fixture_html):
    """Bug 1: khong duoc lan menu danh muc (~70 muc) hay mo ta marketing dai
    vao field Thong so ky thuat - chi bang thong so that."""
    html = fixture_html("tlc_product.html")

    spec = extract_spec_text(html)

    assert len(spec) < 500, "Thông số kỹ thuật không được dài như dump cả trang"
    assert "Mã sản phẩm: TLC-AECA-VB-10W" in spec
    assert "Công suất: 10W" in spec
    assert "Đèn LED âm trần siêu mỏng" not in spec, "lọt menu danh mục vào specs"
    assert "Skip to content" not in spec


def test_roman_spec_table_survives_form_tag_stripping(fixture_html):
    """Bug 2: Roman.vn (ASP.NET WebForms) boc toan bo trang trong <form
    id="form1">. Neu strip het the <form>, bang specs that (o day) cung bi
    xoa theo - phai con nguyen."""
    html = fixture_html("roman_product.html")

    spec = extract_spec_text(html)

    assert spec, "Bảng thông số kỹ thuật của Roman bị xóa sạch do strip <form>"
    assert "Công suất: 12W" in spec
    assert "Kích thước lỗ khoét: 110mm" in spec
