"""Chặn dữ liệu bịa ở tầng 2 - lớp bảo vệ cuối trước khi ghi vào file giao đi.

Prompt đã yêu cầu "không bịa", nhưng yêu cầu không phải là đảm bảo. Kiểu sai đo
được thật trên kingled.com.vn và KHÔNG lộ ra khi review bằng mắt vì giá trị
"trông như thật": `bo-nguon-150w` có khối thông số riêng KHÔNG hề có dòng bảo
hành, vẫn được gán `bao_hanh="Đổi mới 2 năm"` - nhặt từ một phụ kiện liên quan ở
cuối trang.

Nửa còn lại của bộ test cũng quan trọng ngang: KHÔNG được xoá nhầm dữ liệu thật.
Model đổi cách trình bày ("IP 44" -> "IP44") mà vẫn chép đúng số liệu, và nhiều
thuộc tính thật chỉ được nói trong phần mô tả chứ không có trong bảng thông số -
đối chiếu quá chặt sẽ cắt mất đúng những giá trị đó.
"""
from crawler.llm.validate import drop_ungrounded_tags

SOURCE = (
    "Mã SP: DB-HS-10-DM\n"
    "Công Suất: 10w\n"
    "Nguồn Điện: 220V/50Hz\n"
    "Độ Hoàn Màu: CRI>90\n"
    "Tiêu Chuẩn: IP 44\n"
    "Nhiệt Độ Màu: 6500K, 4000K, 3000K"
)


def test_value_invented_by_model_is_dropped():
    tags = {"cong_suat": "10w", "dien_ap": "12VDC"}

    assert drop_ungrounded_tags(tags, SOURCE) == {"cong_suat": "10w"}


def test_value_borrowed_from_another_product_is_dropped():
    """Nguồn ở đây là text ĐÃ gỡ khối sản phẩm liên quan, nên giá trị mượn của
    sản phẩm khác không còn chỗ nào đối chiếu được."""
    tags = {"bao_hanh": "Đổi mới 2 năm"}

    assert drop_ungrounded_tags(tags, SOURCE) == {}


def test_reformatted_but_real_values_survive():
    """Không được thẳng tay so khớp chuỗi: model đổi cách trình bày (bỏ dấu
    cách, đổi dấu phân cách) mà vẫn chép đúng số liệu - đó là giá trị THẬT."""
    tags = {
        "tieu_chuan": "IP44",            # nguồn ghi "IP 44"
        "cri": "> 90",                    # nguồn ghi "CRI>90"
        "nhiet_do_mau": "6500K/4000K/3000K",  # nguồn ghi "6500K, 4000K, 3000K"
    }

    assert drop_ungrounded_tags(tags, SOURCE) == tags


def test_no_source_text_means_no_filtering():
    """Không có nguồn để đối chiếu thì không được im lặng xoá sạch tag - đó là
    mất dữ liệu chứ không phải chống bịa."""
    tags = {"cong_suat": "10w"}

    assert drop_ungrounded_tags(tags, "") == tags
