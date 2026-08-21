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
    # KHONG phai noi dung muc uu diem, chi la 1 DONG de dinh vi no trong DOM -
    # xem quy tac 9 cua prompt va extraction/advantages.py.
    muc_uu_diem: Optional[str] = None


# JSON schema dung cho cac provider ho tro structured output truc tiep (vd
# Vertex AI response_json_schema). "tags" co dinh dang object voi
# additionalProperties dang string - chinh la cho phep so luong/ten key linh
# hoat theo tung san pham/site, dung tinh than "schema thuoc tinh linh hoat".
EXTRACTION_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "ma_san_pham": {"type": ["string", "null"]},
        "muc_uu_diem": {"type": ["string", "null"]},
        "tags": {
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
    },
    "required": ["tags"],
}


_PROMPT_TEMPLATE = """\
Bạn là bộ TRÍCH XUẤT dữ liệu, không phải bộ tư vấn sản phẩm. Việc của bạn là \
SAO CHÉP thông tin có sẵn trong nội dung nguồn bên dưới. KHÔNG suy luận, KHÔNG \
bổ sung kiến thức bên ngoài.

Nội dung nguồn lấy từ trang sản phẩm "{product_name}" (có thể lộn xộn, thiếu \
cấu trúc, lặp lại).

QUY TẮC BẮT BUỘC:

1. GIÁ TRỊ PHẢI LẤY TỪ NỘI DUNG NGUỒN. Chép lại số liệu, đơn vị và chữ nghĩa \
đúng như nguồn viết: KHÔNG quy đổi đơn vị, KHÔNG làm tròn, KHÔNG diễn đạt lại. \
Được phép bỏ tên thuộc tính, dấu hai chấm và khoảng trắng thừa ở hai đầu.
   - Nguồn "Độ Hoàn Màu: CRI>90" → "CRI>90" | sai: "CRI 85", "khoảng 90"

2. THUỘC TÍNH NHIỀU GIÁ TRỊ PHẢI LẤY ĐỦ, không được bỏ bớt. Nguồn liệt kê \
nhiều giá trị (xuống dòng, dấu phẩy, gạch chéo) thì gộp lại thành MỘT chuỗi \
ngăn cách bằng dấu phẩy, giữ nguyên thứ tự.
   - Nguồn "Nhiệt Độ Màu: 6500K, 4000K, 3000K" → "6500K, 4000K, 3000K"
   - Nguồn "Ánh Sáng:" rồi 3 dòng "Trắng" / "Trung tính" / "Vàng" \
→ "Trắng, Trung tính, Vàng" | sai: chỉ lấy "Trắng"

3. KHÔNG LẤY GIÁ TRỊ TỪ ĐÂU KHÁC ngoài nội dung nguồn. Cấm suy ra từ:
   - kiến thức của bạn về đèn LED nói chung (vd "đèn bàn thường chạy 12V")
   - tên sản phẩm (tên có chữ "12W" KHÔNG cho phép tự điền công suất nếu nguồn \
không ghi)
   - giá trị "thường thấy" của dòng sản phẩm đó
   Nguồn không viết ra thì thuộc tính đó KHÔNG được xuất hiện trong kết quả.

4. CHỈ LẤY THUỘC TÍNH CỦA ĐÚNG SẢN PHẨM NÀY. Trang nguồn có thể nhắc tới sản \
phẩm khác (phụ kiện, sản phẩm liên quan, sản phẩm cùng dòng) kèm thông số \
riêng của chúng. Không chắc một giá trị thuộc về "{product_name}" hay thuộc \
về sản phẩm khác thì BỎ, không đoán.

5. THIẾU KHÔNG PHẢI LÀ LỖI. Trả về ít thuộc tính là chấp nhận được; trả về một \
thuộc tính sai thì không. Nguồn chỉ có 2 dòng thông số thì trả về đúng 2 tag. \
Không có thông số nào thì trả về "tags": {{}}.

6. TÊN KEY đặt bằng tiếng Việt không dấu, snake_case, theo đúng tên thuộc tính \
xuất hiện trong nguồn - KHÔNG ép theo một danh sách cố định, mỗi sản phẩm có \
thể có số thuộc tính khác nhau. Quy tắc bỏ dấu CHỈ áp dụng cho TÊN KEY; phần \
GIÁ TRỊ giữ nguyên dấu tiếng Việt (xem quy tắc 1).
   - Đúng: {{"anh_sang": "3 màu", "bao_hanh": "24 tháng", "cong_suat": "12W"}}
   - Sai:  {{"anh_sang": "3 mau", "bao_hanh": "24 thang"}}

7. KHÔNG đưa tên sản phẩm và giá bán vào "tags" (đã có cột riêng), chỉ đưa \
thông số kỹ thuật.

8. "ma_san_pham": chỉ điền nếu mã/model được viết rõ trong nguồn. Không thấy \
thì để null - KHÔNG tự ghép từ tên sản phẩm.

9. "muc_uu_diem" - LA BÀN, KHÔNG PHẢI NỘI DUNG. Trang thường có một mục liệt \
kê các điểm mạnh của sản phẩm, nhưng tiêu đề mục đó KHÔNG cố định: "Ưu điểm", \
"Đặc điểm nổi bật", "Lợi ích khi sử dụng", "Tại sao nên dùng...", thậm chí \
không có tiêu đề nào. Hãy chép NGUYÊN VĂN đúng MỘT dòng để định vị mục đó:
   - có tiêu đề  -> chép đúng dòng tiêu đề
   - không tiêu đề -> chép đúng dòng đầu tiên của danh sách điểm mạnh
   QUAN TRỌNG: dòng bạn chỉ vào phải có NỘI DUNG THẬT ngay bên dưới. Trang có \
thể có một tiêu đề nghe rất giống (vd "ưu điểm sản phẩm") nhưng bỏ trống, \
trong khi các điểm mạnh thật lại nằm chỗ khác dưới dạng các đề mục nhỏ. Gặp \
trường hợp đó thì chỉ vào chỗ CÓ nội dung, đừng chỉ vào cái tiêu đề rỗng.
   Không thấy mục nào như vậy thì để null. KHÔNG viết lại, KHÔNG tóm tắt - \
dòng bạn trả về phải xuất hiện y nguyên trong nội dung nguồn.
   Đây KHÔNG phải mục thông số kỹ thuật, KHÔNG phải mục ứng dụng, hướng dẫn \
lắp đặt hay địa chỉ mua hàng.

TRƯỚC KHI TRẢ LỜI: rà lại từng giá trị bạn định trả về và chỉ ra được nó nằm ở \
dòng nào trong nội dung nguồn. Không chỉ ra được thì xoá thuộc tính đó khỏi kết \
quả. Kiểm tra thêm: thuộc tính nào nguồn liệt kê nhiều giá trị mà bạn mới lấy \
một, hãy bổ sung cho đủ.

Chỉ trả về DUY NHẤT 1 đối tượng JSON đúng hình dạng sau, không giải thích thêm:
{{"ma_san_pham": "<string hoặc null>", "muc_uu_diem": "<string hoặc null>", "tags": {{"<key>": "<value>", ...}}}}

Nội dung nguồn:
\"\"\"
{spec_text}
\"\"\"
"""


def build_prompt(product_name: str, cleaned_spec_text: str) -> str:
    return _PROMPT_TEMPLATE.format(product_name=product_name or "(không rõ tên)", spec_text=cleaned_spec_text)
