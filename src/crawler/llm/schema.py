"""Prompt + output schema cho trich xuat Tags tu thong so ky thuat tu do. Task 7.1.

Schema thuoc tinh cua "tags" la LINH HOAT theo tung site/category (quyet dinh
thiet ke - xem specs/llm-attribute-normalization/spec.md): khong ep ve 1 danh
sach field co dinh nhu 4 thuoc tinh mau cua rangdong.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExtractionOutput:
    tags: dict[str, str] = field(default_factory=dict)
    ma_san_pham: Optional[str] = None


# JSON schema dung cho cac provider ho tro structured output truc tiep (vd
# Vertex AI response_json_schema). "tags" co dinh dang object voi
# additionalProperties dang string - chinh la cho phep so luong/ten key linh
# hoat theo tung san pham/site, dung tinh than "schema thuoc tinh linh hoat".
EXTRACTION_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "ma_san_pham": {"type": ["string", "null"]},
        "tags": {
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
    },
    "required": ["tags"],
}


_PROMPT_TEMPLATE = """\
Bạn là hệ thống trích xuất dữ liệu sản phẩm chiếu sáng LED. Dưới đây là nội \
dung thông số kỹ thuật thô lấy từ trang sản phẩm "{product_name}" (có thể \
lộn xộn, thiếu cấu trúc, lặp lại).

Nhiệm vụ:
1. Nếu xác định được rõ Mã sản phẩm / Model trong nội dung, điền vào \
"ma_san_pham". Nếu không thấy, để null - KHÔNG bịa.
2. Chuyển các thông số có định dạng rõ ràng (công suất, điện áp, nhiệt độ \
màu, kích thước, CRI, IP, bảo hành, góc chiếu, v.v.) thành các cặp \
key-value trong "tags". Tên key đặt bằng tiếng Việt không dấu, snake_case, \
dựa theo chính tên thuộc tính xuất hiện trong nội dung nguồn - KHÔNG ép theo \
1 danh sách cố định, mỗi sản phẩm có thể có số thuộc tính khác nhau. Giữ \
nguyên định dạng số liệu/đơn vị như trong nguồn (vd "12W", "150-265V").
3. Không bịa thêm thuộc tính không xuất hiện trong nội dung nguồn.

Chỉ trả về DUY NHẤT 1 đối tượng JSON đúng hình dạng sau, không giải thích thêm:
{{"ma_san_pham": "<string hoặc null>", "tags": {{"<key>": "<value>", ...}}}}

Nội dung nguồn:
\"\"\"
{spec_text}
\"\"\"
"""


def build_prompt(product_name: str, cleaned_spec_text: str) -> str:
    return _PROMPT_TEMPLATE.format(product_name=product_name or "(không rõ tên)", spec_text=cleaned_spec_text)
