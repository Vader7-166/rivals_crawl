## ADDED Requirements

### Requirement: Crawl chạy nền, không chiếm một request
Hệ thống SHALL chạy mỗi lượt crawl như một công việc nền. Thao tác bắt đầu crawl SHALL trả về ngay một định danh công việc thay vì chờ crawl hoàn tất.

Căn cứ: một lượt crawl toàn site đo được 33–70 phút (TLC 485 sản phẩm 33 phút, KingLED 549 sản phẩm 70 phút) — quá dài cho một chu kỳ request/response.

#### Scenario: Bắt đầu một lượt crawl
- **WHEN** người dùng bắt đầu crawl cho một phạm vi
- **THEN** hệ thống trả về định danh công việc ngay lập tức, và giao diện vẫn dùng được trong lúc crawl chạy

#### Scenario: Đóng trình duyệt giữa chừng
- **WHEN** người dùng đóng giao diện trong lúc một công việc đang chạy
- **THEN** công việc vẫn chạy tiếp, và mở lại giao diện thì thấy đúng tiến độ hiện tại

### Requirement: Tiến độ quan sát được trong lúc chạy
Với mỗi công việc đang chạy, hệ thống SHALL cho biết trạng thái, số sản phẩm đã xử lý trên tổng số, và sản phẩm đang xử lý. Tiến độ SHALL cập nhật trong lúc crawl chạy chứ không chỉ khi kết thúc.

#### Scenario: Theo dõi tiến độ giữa chừng
- **WHEN** một công việc đã xử lý một phần phạm vi
- **THEN** tiến độ hiển thị đúng số đã xử lý trên tổng số tại thời điểm hỏi

#### Scenario: Công việc kết thúc có lỗi
- **WHEN** một công việc dừng vì lỗi (cạn quota LLM, site chặn, lỗi kỹ thuật)
- **THEN** trạng thái cuối ghi rõ lý do dừng, và số sản phẩm đã kịp lưu vào kho được giữ nguyên

### Requirement: Một tiến trình ghi duy nhất vào kho dữ liệu
Hệ thống SHALL đảm bảo tại mọi thời điểm chỉ có một tiến trình ghi vào kho dữ liệu. Các thành phần khác SHALL chỉ đọc.

Ràng buộc này kế thừa từ thiết kế kho dữ liệu hiện có ("mọi hàm ghi phải được gọi từ duy nhất một luồng") và mở rộng lên mức tiến trình khi hệ thống chạy nhiều container.

#### Scenario: Đọc trong lúc đang ghi
- **WHEN** một công việc đang crawl và ghi vào kho, đồng thời người dùng tra cứu hoặc xuất file
- **THEN** thao tác đọc chạy được bình thường, không bị lỗi khoá cơ sở dữ liệu

#### Scenario: Yêu cầu crawl thứ hai khi đã có công việc chạy
- **WHEN** một công việc crawl đang chạy và người dùng yêu cầu một công việc crawl khác
- **THEN** công việc mới được xếp hàng đợi thay vì chạy song song ghi cùng lúc

### Requirement: Công việc bị ngắt thì chạy lại là chạy tiếp
Sau khi một công việc bị ngắt giữa chừng, chạy lại cùng phạm vi SHALL chỉ crawl phần chưa có bản trích xuất đầy đủ, không crawl lại phần đã xong.

Đây là hành vi crawl-lại-có-chọn-lọc đã có sẵn; yêu cầu này chốt rằng tầng công việc nền không được làm mất nó.

#### Scenario: Chạy lại sau khi bị ngắt
- **WHEN** một công việc bị huỷ hoặc chết giữa chừng, rồi người dùng chạy lại đúng phạm vi đó
- **THEN** số sản phẩm cần crawl của lần chạy sau bằng đúng số còn thiếu, không phải toàn bộ phạm vi

#### Scenario: Chạy lại phạm vi đã hoàn tất
- **WHEN** người dùng chạy lại một phạm vi mà mọi sản phẩm đều đã có bản trích xuất đầy đủ
- **THEN** không request nào được gửi tới site đối thủ và không lời gọi LLM nào được thực hiện

### Requirement: Huỷ được công việc đang chạy
Hệ thống SHALL cho phép huỷ một công việc đang chạy. Dữ liệu đã lưu trước thời điểm huỷ SHALL được giữ nguyên trong kho.

#### Scenario: Huỷ giữa chừng
- **WHEN** người dùng huỷ một công việc đã xử lý được một phần
- **THEN** công việc dừng, các bản ghi đã lưu vẫn còn trong kho, và lần chạy sau tiếp tục từ phần còn thiếu
