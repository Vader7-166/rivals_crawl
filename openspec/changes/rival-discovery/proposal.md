## Why

Danh sách đối thủ hiện là **dữ liệu khai tay**: 12 nhãn trong `crawl_list.md`,
14 hồ sơ trong `sites/registry.py`. Danh sách đó đúng vào ngày viết ra và không
có cơ chế nào phát hiện khi nó sai đi. Hai cách nó sai:

1. **Đối thủ đổi site.** Domain chết, đổi tên miền, hoặc dựng site mới bên cạnh
   site cũ. Hệ thống hiện không biết — `crawl_site.py` chỉ báo "probe không ra
   URL sản phẩm", không phân biệt được "site hỏng" với "site đã dọn đi nơi
   khác".
2. **Đối thủ mới.** Ngành chiếu sáng LED Việt Nam có hàng chục nhà sản xuất;
   danh sách 12 nhãn là kết quả của một lần khảo sát tay.

## What Changes

- **Một bộ tìm kiếm trả về top N site LED ứng viên**, kèm điểm và **lý do từng
  tín hiệu**. Hai đường dùng chung một bộ máy: tìm đối thủ mới (từ khoá là loại
  hàng) và tìm lại site của một nhãn đã biết (từ khoá là tên nhãn).
- **Không domain nào được thêm tự động.** Kết quả là danh sách để người đọc
  quyết định — cùng hình với màn xác nhận phạm vi đã có.
- Truy vấn mặc định **dựng từ tên danh mục trong kho**, không phải một danh
  sách từ khoá nghĩ ra.

### Không làm trong đợt này

- **Không** tự thêm domain vào registry, không tự tạo job crawl. Một domain sai
  đi vào kho là thứ phải phát hiện bằng mắt sau đó.
- **Không** theo dõi định kỳ. Chạy tay khi cần; tự động hoá khi biết đối thủ đổi
  site thường xuyên đến mức nào.
- **Không** dùng LLM để phán đoán "đây có phải nhà sản xuất không". Kết quả phải
  tất định và giải thích được bằng số đo, như mọi tầng chọn lọc khác của dự án.

## Capabilities

### New Capabilities

- `rival-discovery`: từ khoá → top N site LED ứng viên, kèm điểm và lý do từng
  tín hiệu; loại thẳng các tập đóng (sàn TMĐT, mạng xã hội, từ điển, site của
  chính mình); chạy được cả hai đường (tìm mới / tìm lại một nhãn).

### Modified Capabilities

Không có. Không tầng nào đang chạy bị đổi hành vi.

## Impact

| Chỗ | Kiểu đụng |
|---|---|
| `src/crawler/discovery/` | Mới: engine + queries + scoring + finder |
| `scripts/find_rivals.py` | Mới |
| `src/crawler/web/api.py` | Thêm một endpoint `/api/discover` |
| `src/crawler/web/static/` | Thêm một màn |
| Phần còn lại của `crawler/` | **Không đụng** |

Phụ thuộc: `httpx` (đã có). Không thêm khoá API — Bing không đòi, và
`SearchEngine` trừu tượng để cắm Google/Serper khi cần.
