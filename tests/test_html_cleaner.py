"""Regression test cho extract_spec_text (field "Thông số kỹ thuật").

2 bug thuc te da gap va sua:
1. thong_so_ky_thuat ban dau tai su dung thang output cua clean_html_for_llm
   (chua ca menu dieu huong + mo ta marketing dai) - phai tach rieng ham chi
   lay dung bang thong so ky thuat sach.
2. Sau khi tach rieng, phat hien them: strip tag <form> (tuong la vo hai, chi
   de bo cac form nho nhu tim kiem/lien he) lai xoa SACH TOAN BO noi dung
   trang Roman.vn - vi ASP.NET WebForms boc ca trang trong 1 <form id="form1">
   duy nhat. Phai bo "form" khoi danh sach strip.
3. KingLED khong dung <table> ma dung <label>/<span>, VA dung lai chinh bo cuc
   do cho khoi "san pham lien quan" - nen viec doc duoc cap label/value phai di
   kem pham vi (spec_root_selector), khong duoc quet ca trang.
"""
from crawler.llm.html_cleaner import clean_html_for_llm, extract_spec_text


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


def test_kingled_spec_needs_scope_because_page_has_no_table(fixture_html):
    """Bug 3 (KingLED): ca trang khong co MOT the <table> nao - thong so nam
    trong bo cuc <label>Công Suất</label><span>: 12w</span>. Khong khai
    spec_root_selector thi field Thong so ky thuat rong hoan toan."""
    html = fixture_html("kingled_product_rendered.html")

    assert extract_spec_text(html) == ""


def test_kingled_scoped_spec_excludes_related_products(fixture_html):
    """Bug 3 tiep: bo cuc <label>/<span> con duoc dung lai cho khoi "san pham
    lien quan" - trang nay co 107 the <label> nhung chi 16 cai la cua san pham
    dang xem. Quet ca trang se ghi thong so cua san pham KHAC vao ban ghi nay,
    va khong ai phat hien duoc khi review vi moi gia tri deu co that tren
    trang."""
    html = fixture_html("kingled_product_rendered.html")

    spec = extract_spec_text(html, spec_root_selector='div.property[data-id="Property"]')

    assert "Mã SP: DL-12SS-T140" in spec
    assert "Công Suất: 12w" in spec
    # DL-6SS-T100 / DL-8SS-T120 la san pham lien quan o cuoi trang, khong phai
    # san pham dang xem.
    assert "DL-6SS-T100" not in spec
    assert "DL-8SS-T120" not in spec
    assert "Họ tên" not in spec, "lọt <label> của form đăng ký tư vấn vào specs"
    assert len(spec) < 500


def test_kingled_multi_value_attribute_is_comma_separated(fixture_html):
    """Thuoc tinh nhieu gia tri duoc site tach thanh nhieu <a> rieng. Noi bang
    dau cach thi "Trắng Trung tính Vàng" doc ra nhu 1 gia tri lien khuc."""
    html = fixture_html("kingled_product_rendered.html")

    spec = extract_spec_text(html, spec_root_selector='div.property[data-id="Property"]')

    assert "Ánh Sáng: Trắng, Trung tính, Vàng" in spec
    assert "Nhiệt Độ Màu: 6500K, 4000K, 3000K" in spec


def test_kingled_llm_input_puts_spec_block_first(fixture_html):
    """Khoi thong so cua KingLED nam gan CUOI trang (trong popup tab). Neu giu
    thu tu tu nhien thi no bi cat mat boi gioi han max_chars va tang 2 khong
    con gi de doc."""
    html = fixture_html("kingled_product_rendered.html")

    cleaned = clean_html_for_llm(
        html, spec_root_selector='div.property[data-id="Property"]'
    )

    assert cleaned.startswith("Mã SP: DL-12SS-T140")
    assert "Công Suất: 12w" in cleaned[:400]


def test_kingled_related_products_are_stripped_before_reaching_llm(fixture_html):
    """Bug 4: khoanh vùng mới chỉ cứu được cột "Thông số kỹ thuật".
    `clean_html_for_llm` CÓ CHỦ ĐÍCH kèm cả text mô tả của trang (nhiều thuộc
    tính thật nằm ở đó), và chính phần "rộng" đó mang theo thông số của các sản
    phẩm liên quan.

    Fixture là trang thật đã gây lỗi: `bo-nguon-150w` có khối thông số riêng vỏn
    vẹn 4 dòng và KHÔNG có dòng bảo hành, thế mà LLM vẫn trả về
    `bao_hanh="Đổi mới 2 năm"` - nhặt từ một phụ kiện liên quan ở cuối trang.

    Chú ý trang NGẮN mới là trang nguy hiểm: trang dài thì giới hạn 12.000 ký tự
    tự nó đã cắt mất khối sản phẩm liên quan, còn trang thông số thưa - đúng
    loại cần tầng 2 nhất - thì khối đó lọt trọn vào prompt.
    """
    html = fixture_html("kingled_related_products.html")
    kwargs = {"spec_root_selector": 'div.property[data-id="Property"]'}

    before = clean_html_for_llm(html, **kwargs)
    after = clean_html_for_llm(html, noise_selector="div.item", **kwargs)

    assert len(before) < 12_000, "fixture phải ngắn hơn giới hạn cắt thì mới tái hiện được lỗi"
    assert "Bảo Hành" in before and "Đổi mới 2 năm" in before
    assert "Bảo Hành" not in after and "Đổi mới 2 năm" not in after
    # Thông số của chính sản phẩm đang xem phải còn nguyên.
    assert "Mã SP: ND-TO-150-12" in after
    assert "Công Suất: 150W" in after


def test_denvinaled_spec_pairs_use_bold_labels_not_label_tags(fixture_html):
    """Bug 4 (denvinaled.vn): ca trang cung khong co <table>, va thong so cung
    khong nam trong the <label> nhu KingLED - chung la
    `<strong>Công suất:</strong> 9W<br>` trong phan mo ta ngan.

    Cau truc the o day KHONG dang tin: trong cung mot doan, "Công suất:" nam
    trong <span><strong> con "Kích thước:" nam trong <strong><span> - dao
    nguoc nhau. Nen phai doc theo DONG TEXT (nhan la chuoi ket thuc bang ":",
    gia tri la chuoi ngay sau).
    """
    html = fixture_html("denvinaled_product.html")

    assert extract_spec_text(html) == "", "chưa khoanh vùng thì không đọc được gì"

    spec = extract_spec_text(html, spec_root_selector="div.product-short-description")

    assert "Công suất: 9W" in spec
    assert "Kích thước: Ø87xH33mm" in spec
    assert "Kích thước thi công: Ø75mm" in spec
    # Gia cua san pham khac trong sidebar/luoi lien quan khong duoc lot vao.
    assert "₫" not in spec
