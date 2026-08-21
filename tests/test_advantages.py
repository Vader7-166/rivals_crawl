"""Trích mục "Ưu điểm" -> 2 cột `Tóm tắt ưu điểm, tính năng` và `Nội dung Ưu điểm SP`.

Dữ liệu này CÓ THẬT trên trang nhưng trước đó pipeline không dùng tới nên 2 cột
trống 100%. Cơ chế phải TỔNG QUÁT cho mọi site - không có config riêng theo
domain - nên bộ test này đối chiếu 3 site có 3 hình dạng khác hẳn nhau.
"""
from crawler.extraction.advantages import extract_advantages

KINGLED_NOISE = "div.item"
SPEC_SELECTOR_NOISE = {"noise_selector": KINGLED_NOISE}


def test_tlc_bullets_are_list_items_with_bold_labels(fixture_html):
    """TLC: gạch đầu dòng là <li>, nhãn nằm trong <strong>."""
    summary, content = extract_advantages(fixture_html("tlc_product.html"))

    assert summary.split("\n") == [
        "Chống ẩm tối ưu",
        "Chiếu sáng dịu nhẹ, bảo vệ mắt",
        "Ánh sáng chân thực, tự nhiên",
        "Thiết kế hiện đại – thẩm mỹ tinh tế",
        "Tiết kiệm điện năng",
    ]
    assert content.startswith("Ưu điểm của Âm Trần Eyecare Chống Ẩm 10W")
    assert "Nhờ thiết kế đạt chuẩn IP54" in content


def test_tlc_cross_sell_line_is_excluded(fixture_html):
    """Cuối mục có dòng bán chéo ">>> Xem thêm: ..." - không phải ưu điểm."""
    _, content = extract_advantages(fixture_html("tlc_product.html"))

    assert "Xem thêm" not in content


def test_kingled_bullets_are_sub_headings_not_list_items(fixture_html):
    """KingLED: gạch đầu dòng là <h3> con, KHÔNG phải <li>.

    Trong mục còn có 1 <ul> lồng bên trong một ý (các bước lắp đặt) - ưu tiên
    <li> trước heading con sẽ ra danh sách sai hoàn toàn.
    """
    summary, content = extract_advantages(
        fixture_html("kingled_product_rendered.html"), **SPEC_SELECTOR_NOISE
    )

    lines = summary.split("\n")
    assert lines[0] == "Tiết kiệm điện năng"
    assert "Tiêu chuẩn IP44 kháng xâm nhập" in lines
    # Số thứ tự mục ("1.1 ", "1.7 ") phải bị bỏ - nó không cố định giữa các SP.
    assert not any(line[0].isdigit() for line in lines)
    assert len(content) > 1000


def test_richest_section_wins_when_page_has_several(fixture_html):
    """KingLED có 2 khối "ưu điểm": <h3>ưu điểm sản phẩm</h3> (4 dòng tóm lược)
    đứng TRƯỚC <h2>1. Ưu điểm của...</h2> (mục đầy đủ). Lấy theo thứ tự tài liệu
    sẽ vớ phải khối ngắn."""
    _, content = extract_advantages(
        fixture_html("kingled_product_rendered.html"), **SPEC_SELECTOR_NOISE
    )

    assert content.startswith("Ưu điểm của đèn LED âm trần 12W Ruby Kingled")


def test_roman_section_is_found_even_though_it_never_says_uu_diem(fixture_html):
    """Tôi từng kết luận "Roman không có mục ưu điểm" - SAI, vì chỉ tìm đúng chữ
    "ưu điểm". Roman gọi nó là "Đặc điểm nổi bật của..." và có đủ 5 ý thật.

    Đây chính là lý do khâu TÌM phải thả lưới rộng (mọi tín hiệu dương) rồi mới
    lọc, thay vì tìm hẹp bằng một từ khoá."""
    summary, content = extract_advantages(fixture_html("roman_product.html"))

    assert summary.split("\n")[:2] == ["Chất liệu cao cấp", "Tiết kiệm điện năng"]
    assert content.startswith("Đặc điểm nổi bật của đèn downlight")


def test_heading_with_empty_body_is_not_reported(fixture_html):
    """`bo-nguon-150w` có <h3>ưu điểm sản phẩm</h3> bỏ trống - ghi mỗi dòng tiêu
    đề ra file chỉ là rác."""
    assert extract_advantages(
        fixture_html("kingled_related_products.html"), **SPEC_SELECTOR_NOISE
    ) == (None, None)


def test_word_in_menu_or_table_of_contents_is_not_mistaken_for_the_section(fixture_html):
    """Trang TLC có chữ "ưu điểm" ở 4 chỗ, chỗ ĐẦU TIÊN là mô tả blog trong
    mega-menu và chỗ thứ hai là mục lục tự động. Chỉ thẻ heading mới được tính -
    nếu không sẽ lấy nhầm nội dung của bài blog khác."""
    _, content = extract_advantages(fixture_html("tlc_product.html"))

    assert "Đèn sưởi nhà tắm" not in content, "lấy nhầm mô tả blog trong mega-menu"


def test_emoji_bullet_markers_are_recognised():
    """Đo trên 549 sản phẩm KingLED: 153 sản phẩm dùng emoji "☑️" làm dấu gạch
    đầu dòng chứ không phải "-". Chỉ nhận "-•–+" thì cột Nội dung Ưu điểm SP có
    dữ liệu mà cột Tóm tắt lại trống - lỗi im lặng, chỉ lộ ra khi so 2 cột."""
    html = """
    <html><body>
      <h3>ưu điểm sản phẩm</h3>
      <div>
        <p>☑️ Dễ dàng lắp đặt. An toàn</p>
        <p>☑️ Vỏ bọc IP65 chống nước hiệu quả</p>
      </div>
    </body></html>
    """

    summary, content = extract_advantages(html)

    assert summary.split("\n") == [
        "Dễ dàng lắp đặt. An toàn",
        "Vỏ bọc IP65 chống nước hiệu quả",
    ]
    assert "IP65" in content


def test_section_numbering_is_stripped_but_real_numbers_are_kept():
    """Bỏ số thứ tự mục ("4. ", "1.7 ") nhưng KHÔNG được cắt số liệu thật: nhãn
    "2 dải LED to bản" của TLC từng tụt xuống còn "dải LED to bản" vì luật bỏ số
    quá tham."""
    from crawler.extraction.advantages import _clean_line

    assert _clean_line("4. Ưu điểm của Âm Trần") == "Ưu điểm của Âm Trần"
    assert _clean_line("1.7 Tiêu chuẩn IP44") == "Tiêu chuẩn IP44"
    assert _clean_line("2 dải LED to bản") == "2 dải LED to bản"
    assert _clean_line("3 chế độ màu") == "3 chế độ màu"


ANCHOR_HTML = """
<html><body><div class="desc">
  <h2>4. Điều làm nên khác biệt của phích cắm 4500W</h2>
  <ul><li><strong>Độ an toàn cao:</strong> chống giật, chống cháy.</li>
      <li><strong>Chịu tải lớn:</strong> lên tới 4500W.</li></ul>
  <h2>5. Địa chỉ mua hàng</h2>
</div></body></html>
"""

NO_HEADING_HTML = """
<html><body><div class="desc">
  <h2>1. Thông số kỹ thuật</h2>
  <figure>ảnh</figure>
  <ul><li>Đèn sử dụng chip LED COB với khả năng chiếu sáng vượt trội.</li>
      <li>Ánh sáng đèn giúp bảo vệ mắt hiệu quả với Ra &gt; 85.</li></ul>
</div></body></html>
"""


def test_anchor_finds_section_whose_heading_no_keyword_can_match():
    """Tiêu đề mục này không có chuẩn nào: đo trên 20 trang thật đếm được
    "Ưu điểm vượt trội", "Đặc điểm cấu tạo", "ĐẶC ĐIỂM NỔI BẬT CỦA...",
    "Lợi ích khi sử dụng...", "Vì sao nên lắp đặt...", "Tại sao nên sử dụng...".
    Danh sách từ khoá không bao giờ đủ."""
    assert extract_advantages(ANCHOR_HTML) == (None, None)

    summary, content = extract_advantages(
        ANCHOR_HTML, anchor="4. Điều làm nên khác biệt của phích cắm 4500W"
    )

    assert summary.split("\n") == ["Độ an toàn cao", "Chịu tải lớn"]
    assert "chống giật" in content
    assert "Địa chỉ mua hàng" not in content


def test_anchor_works_when_section_has_no_heading_at_all():
    """Ca giết chết mọi hướng bám tiêu đề: trang `den-am-tran-cob-plast-7w` của
    TLC để danh sách ưu điểm là một <ul> trần, không tiêu đề. La bàn khi đó là
    dòng đầu tiên của danh sách, code leo lên <ul> bọc ngoài."""
    summary, content = extract_advantages(
        NO_HEADING_HTML,
        anchor="Đèn sử dụng chip LED COB với khả năng chiếu sáng vượt trội.",
    )

    assert "chip LED COB" in content
    assert "Thông số kỹ thuật" not in content
    assert len(summary.split("\n")) == 2


def test_anchor_too_short_is_ignored():
    """La bàn quá ngắn thì khớp bừa bãi - thà bỏ trống."""
    assert extract_advantages(ANCHOR_HTML, anchor="Ưu") == (None, None)


def test_keyword_path_still_wins_when_it_works(fixture_html):
    """La bàn chỉ là đường lui. Trang có tiêu đề rõ ràng vẫn phải đi đường từ
    khoá - miễn phí và không phụ thuộc vào tầng 2."""
    summary, _ = extract_advantages(fixture_html("tlc_product.html"), anchor="rác")

    assert summary.split("\n")[0] == "Chống ẩm tối ưu"


APPLICATION_HTML = """
<html><body><div class="desc">
  <h2>Ứng dụng quan trọng của đèn âm trần</h2>
  <ul><li>Chiếu sáng phòng khách</li><li>Chiếu sáng hành lang</li></ul>
</div></body></html>
"""

EMPTY_TAB_HTML = """
<html><body>
  <div class="summary"><h3>ưu điểm sản phẩm</h3><div></div></div>
  <div class="desc"><h2>Đặc điểm nổi bật</h2>
    <ul><li><strong>Tuổi thọ cao:</strong> 50.000 giờ.</li>
        <li><strong>Tiết kiệm điện:</strong> giảm 60%.</li></ul>
  </div>
</body></html>
"""


def test_application_section_is_rejected_not_written_as_advantages():
    """Trang sản phẩm có nhiều mục CÙNG HÌNH DẠNG "tiêu đề + danh sách ý": ứng
    dụng, cấu tạo, phụ kiện, hướng dẫn lắp đặt. Ghi nhầm mục ứng dụng vào cột
    mang tên "Ưu điểm" là sai dữ liệu - thà để trống."""
    assert extract_advantages(APPLICATION_HTML) == (None, None)


def test_empty_decoy_heading_loses_to_the_real_section():
    """Bẫy chính của KingLED: mọi trang đều có nhãn tab "ưu điểm sản phẩm" nằm
    cạnh "Mô tả sản phẩm" / "Kiểm chứng chất lượng". Sau khi làm phẳng HTML nó
    trông y hệt tiêu đề mục thật, và cả bộ lọc từ khoá lẫn LLM đều bám vào đó -
    nhưng phần lớn trang thì tab đó BỎ TRỐNG.

    Ứng viên rỗng phải bị loại để mục thật (tiêu đề không hề có chữ "ưu điểm")
    thắng."""
    summary, content = extract_advantages(EMPTY_TAB_HTML)

    assert summary.split("\n") == ["Tuổi thọ cao", "Tiết kiệm điện"]
    assert content.startswith("Đặc điểm nổi bật")


CLUSTER_HTML = """
<html><body><div class="desc">
  <h3>Tiết kiệm năng lượng</h3><p>Giảm 60% điện so với đèn truyền thống.</p>
  <h3>Tuổi thọ cao</h3><p>Lên tới 40.000 giờ chiếu sáng.</p>
  <h3>Chip LED cao cấp</h3><p>Chip Samsung cho ánh sáng ổn định.</p>
  <h2>Địa chỉ mua hàng</h2><p>Xem hệ thống đại lý.</p>
</div></body></html>
"""

CLUSTER_UNDER_APPLICATIONS_HTML = """
<html><body><div class="desc">
  <h2>Ứng dụng của đèn led dán 22W</h2>
  <h3>Chiếu sáng lối đi</h3><p>Dùng cho hành lang, cầu thang.</p>
  <h3>Chiếu sáng văn phòng</h3><p>Dùng cho văn phòng, công sở.</p>
  <h3>Chiếu sáng nhà ở</h3><p>Dùng cho phòng khách, phòng ngủ.</p>
</div></body></html>
"""


def test_cluster_without_any_parent_heading_is_picked_up():
    """Nhiều site không đặt cho mục ưu điểm một tiêu đề nào, chỉ liệt kê thẳng
    các ý bằng đề mục ngang cấp. Đo trên mẫu ngẫu nhiên: có ở CẢ BA site - TLC
    `mat-cong-de-mong`, KingLED `den-exit`, và 3/7 trang Roman."""
    summary, content = extract_advantages(CLUSTER_HTML)

    assert summary.split("\n")[:3] == [
        "Tiết kiệm năng lượng",
        "Tuổi thọ cao",
        "Chip LED cao cấp",
    ]
    assert "Địa chỉ mua hàng" not in content


def test_cluster_sitting_under_a_negative_parent_heading_is_rejected():
    """Cụm bắt đầu từ đề mục con đầu tiên nên tín hiệu âm nằm ở TIÊU ĐỀ MẸ phía
    trên chứ không nằm trong chính các đề mục. "Chiếu sáng văn phòng / Chiếu
    sáng nhà ở" bản thân vô hại, nhưng mẹ của chúng là "Ứng dụng của...")."""
    assert extract_advantages(CLUSTER_UNDER_APPLICATIONS_HTML) == (None, None)
