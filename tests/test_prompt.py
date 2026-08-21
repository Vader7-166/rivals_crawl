"""Prompt tầng 2 - chống bịa giá trị.

Bịa dữ liệu là kiểu lỗi tệ nhất của pipeline này: giá trị "trông như thật" nên
không lộ ra khi review bằng mắt, và người dùng cuối không có cách nào biết cột
nào tin được. Prompt vì vậy phải nêu rõ CƠ CHẾ (sao chép nguyên văn) chứ không
chỉ nêu yêu cầu ("không bịa").
"""
from crawler.llm.schema import build_prompt


def test_prompt_carries_product_name_and_source():
    prompt = build_prompt("Bộ Nguồn 150W", "Mã SP: ND-TO-150-12")

    assert "Bộ Nguồn 150W" in prompt
    assert "Mã SP: ND-TO-150-12" in prompt


def test_json_example_braces_are_not_doubled():
    """Template dùng str.format nên dấu ngoặc trong ví dụ JSON phải nhân đôi
    trong source. Quên một chỗ là model nhận được `{{"tags": ...}}` và học sai
    hình dạng output - lỗi im lặng, chỉ lộ ra ở tỷ lệ parse hỏng."""
    prompt = build_prompt("X", "Y")

    assert (
        '{"ma_san_pham": "<string hoặc null>", "muc_uu_diem": "<string hoặc null>"'
        ', "tags": {"<key>": "<value>", ...}}'
        in prompt
    )
    assert '{"anh_sang": "3 màu"' in prompt
    # `}}` cuối ví dụ trên là JSON lồng hợp lệ, không phải lỗi escape. Dấu hiệu
    # của lỗi escape là ngoặc mở nhân đôi ngay trước tên field.
    assert '{{"' not in prompt


def test_prompt_states_the_anti_fabrication_mechanism():
    """Không chỉ cấm bịa, mà phải nói RÕ cách tránh."""
    prompt = build_prompt("X", "Y")

    assert "LẤY TỪ NỘI DUNG NGUỒN" in prompt
    assert "tên sản phẩm" in prompt          # cấm suy từ tên sản phẩm
    assert "sản phẩm liên quan" in prompt    # cấm lấy của sản phẩm khác
    # Thiếu phải được coi là chấp nhận được, nếu không model sẽ cố lấp đầy.
    assert "THIẾU KHÔNG PHẢI LÀ LỖI" in prompt


def test_prompt_requires_all_values_of_a_multi_value_attribute():
    """Đo được: bản prompt bắt "sao chép Y NGUYÊN một đoạn ký tự" khiến model
    gặp thuộc tính nhiều giá trị thì chỉ lấy 1 - "6500K, 4000K, 3000K" tụt
    xuống còn "4000K". Siết chống bịa mà làm mất dữ liệu thật thì lỗ."""
    prompt = build_prompt("X", "Y")

    assert "NHIỀU GIÁ TRỊ PHẢI LẤY ĐỦ" in prompt
    assert '"6500K, 4000K, 3000K"' in prompt


def test_missing_product_name_does_not_break_prompt():
    prompt = build_prompt("", "Mã SP: X")

    assert "(không rõ tên)" in prompt
