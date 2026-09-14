## ADDED Requirements

### Requirement: So sánh hai phiên bản bộ trích xuất trên cùng snapshot
Hệ thống SHALL cho phép so sánh kết quả của hai phiên bản bộ trích xuất trên cùng một domain. Phép so sánh SHALL chỉ tính trên các snapshot có mặt ở **cả hai** phiên bản.

Ràng buộc "cùng snapshot" là bắt buộc: khác snapshot thì khác biệt đến từ site đối thủ chứ không phải từ mã nguồn mình, gộp chung vào là làm phép so mất nghĩa.

#### Scenario: So hai phiên bản có snapshot chung
- **WHEN** người dùng so hai phiên bản bộ trích xuất của một domain
- **THEN** kết quả cho biết phép so tính trên bao nhiêu snapshot chung, và chỉ những snapshot đó được tính

#### Scenario: Hai phiên bản không có snapshot chung
- **WHEN** hai phiên bản được chọn không cùng chạy trên snapshot nào
- **THEN** hệ thống nói rõ là không có gì để so và hướng dẫn cách tạo ra phép so hợp lệ, thay vì hiển thị một bảng rỗng

#### Scenario: Bản ghi không có snapshot
- **WHEN** domain có bản ghi nhập từ file cũ, không kèm snapshot
- **THEN** các bản ghi đó bị loại khỏi phép so và số lượng bị loại được nói rõ

### Requirement: Phân loại thay đổi thành vá được, làm hỏng, đổi khác
Với mỗi cột được so, hệ thống SHALL đếm riêng ba nhóm thay đổi: ô **trước trống sau có** (vá được), ô **trước có sau trống** (làm hỏng), và ô **cả hai đều có nhưng khác giá trị** (đổi khác).

Ba nhóm này mang ý nghĩa khác hẳn nhau nên SHALL KHÔNG được gộp thành một con số "số ô đã đổi".

#### Scenario: Một chỉnh sửa vừa vá vừa làm hỏng
- **WHEN** một phiên bản mới của bộ trích xuất điền được thêm một số ô nhưng làm mất một số ô khác
- **THEN** bảng kết quả hiện cả hai con số tách biệt cho từng cột

#### Scenario: Không ô nào đổi
- **WHEN** hai phiên bản cho kết quả giống hệt nhau trên mọi snapshot chung
- **THEN** hệ thống nói rõ không có ô nào đổi

### Requirement: Xem giá trị trước và sau của từng ô
Từ bảng đếm, hệ thống SHALL cho phép đi tới danh sách các sản phẩm có ô thay đổi và xem giá trị **trước** và **sau** của ô đó đặt cạnh nhau, kèm liên kết tới trang sản phẩm gốc.

Đây là phần mà công cụ dòng lệnh hiện có không làm được: nó in ra bảng đếm và ba URL mẫu, phần còn lại người dùng phải tự mở cơ sở dữ liệu.

#### Scenario: Đi từ con số tới ô cụ thể
- **WHEN** người dùng chọn một con số trong bảng đếm
- **THEN** hệ thống liệt kê các sản phẩm thuộc nhóm đó, không giới hạn ở vài mẫu

#### Scenario: Xem một ô đã đổi
- **WHEN** người dùng mở một ô đã đổi
- **THEN** giá trị trước và giá trị sau hiển thị cạnh nhau, kèm URL sản phẩm gốc

#### Scenario: Ô có nội dung rất dài
- **WHEN** ô được xem chứa văn bản dài (thông số kỹ thuật, nội dung ưu điểm)
- **THEN** nội dung hiển thị đầy đủ hoặc cắt có báo rõ, không cắt âm thầm

### Requirement: Xem một lượt crawl của một domain
Hệ thống SHALL cho phép xem trạng thái hiện tại của một domain: danh sách sản phẩm, trạng thái crawl của từng bản ghi, và những bản ghi cần người xử lý tay.

#### Scenario: Lọc bản ghi cần xử lý tay
- **WHEN** người dùng lọc các bản ghi cần xử lý tay của một domain
- **THEN** danh sách trả về đúng các bản ghi thiếu dữ liệu hoặc có độ tin cậy thấp, kèm lý do của từng bản ghi

#### Scenario: Domain chưa crawl lần nào
- **WHEN** người dùng mở một domain chưa có bản ghi nào
- **THEN** hệ thống nói rõ domain chưa có dữ liệu và mời chạy crawl, thay vì hiển thị bảng rỗng không giải thích
