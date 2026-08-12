## ADDED Requirements

### Requirement: Provider chính + fallback tự động
Hệ thống SHALL gọi Vertex AI làm provider LLM chính cho việc trích xuất/chuẩn hoá thông số kỹ thuật, và SHALL tự động chuyển sang DeepSeek khi Vertex AI lỗi hoặc hết quota, mà không làm crawl thất bại.

#### Scenario: Vertex AI hết quota
- **WHEN** lời gọi tới Vertex AI thất bại do hết quota hoặc lỗi provider
- **THEN** hệ thống tự động gửi lại cùng yêu cầu trích xuất (cùng prompt/schema đầu ra) tới DeepSeek, và crawl tiếp tục bình thường thay vì báo lỗi toàn bộ

### Requirement: Trích xuất Tags theo schema linh hoạt per-site
Hệ thống SHALL trích xuất nội dung thông số kỹ thuật dạng tự do trên trang thành field `Tags` (JSON), với tập thuộc tính (key) được suy ra từ chính nội dung nguồn của từng site/category, không ép về 1 schema thuộc tính cố định dùng chung cho mọi site.

#### Scenario: Site nguồn có nhiều thuộc tính hơn schema tham chiếu
- **WHEN** bảng thông số kỹ thuật của trang nguồn liệt kê các thuộc tính không có trong schema tham chiếu 4 field mẫu (vd CRI, UGR, chỉ số IP)
- **THEN** kết quả `Tags` bao gồm cả các thuộc tính bổ sung đó, không bị lược bỏ hay ép vào đúng 4 field cố định

### Requirement: Giảm thiểu input trước khi gọi LLM
Hệ thống SHALL chỉ đưa vào LLM phần nội dung HTML/text đã làm sạch, liên quan tới sản phẩm (không đưa nguyên trang HTML thô) để kiểm soát chi phí token.

#### Scenario: Trang sản phẩm có HTML thô lớn
- **WHEN** HTML thô của 1 trang sản phẩm có kích thước lớn (hàng trăm KB, chứa nhiều script/nav/tracking)
- **THEN** pipeline trích xuất loại bỏ phần nav/script/tracking không liên quan trước khi dựng prompt, chỉ giữ lại khối nội dung liên quan tới sản phẩm

### Requirement: Validate output của LLM trước khi lưu
Hệ thống SHALL kiểm tra kết quả JSON trả về từ LLM đúng cấu trúc/hợp lý trước khi lưu vào bản ghi; kết quả không hợp lệ SHALL được gắn cờ để review thay vì lưu thẳng.

#### Scenario: LLM trả về dữ liệu không hợp lệ
- **WHEN** kết quả trả về từ LLM không phải JSON hợp lệ, hoặc có giá trị số nằm ngoài khoảng hợp lý cho field đó
- **THEN** bản ghi được gắn cờ để review thủ công thay vì được lưu như dữ liệu đã xác thực
