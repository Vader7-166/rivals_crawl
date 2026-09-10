## ADDED Requirements

### Requirement: Khởi chạy toàn bộ hệ thống bằng một lệnh
Toàn bộ hệ thống (giao diện, tầng API, tiến trình chạy crawl, kho dữ liệu) SHALL khởi chạy được bằng một lệnh Docker Compose duy nhất, không cần cài Python, Node hay trình duyệt trên máy chủ.

#### Scenario: Khởi chạy trên máy sạch
- **WHEN** chạy lệnh khởi động trên một máy chỉ có Docker
- **THEN** mọi thành phần lên và giao diện truy cập được, không cần bước cài đặt tay nào ngoài việc điền biến môi trường

#### Scenario: Trình duyệt cho tầng fetch
- **WHEN** một lượt crawl chạy bên trong container
- **THEN** tầng fetch chạy được trình duyệt, tức image đã có sẵn thư viện hệ thống mà trình duyệt cần

### Requirement: Không dịch vụ nào bật cơ chế tự nạp lại mã nguồn
KHÔNG dịch vụ nào trong hệ thống SHALL bật cơ chế tự khởi động lại khi mã nguồn đổi (`--reload` hay tương đương). Sửa mã nguồn trong lúc một lượt crawl đang chạy SHALL KHÔNG làm lượt crawl đó bị ngắt.

Lý do: một lượt crawl kéo dài 33–70 phút, còn cơ chế nạp lại thì khởi động lại tiến trình mỗi lần lưu file. Cô lập worker sang container riêng đã đủ để `--reload` ở dịch vụ khác không chạm tới nó, nhưng bỏ hẳn thì rủi ro về 0 và bớt một biến phải suy luận.

#### Scenario: Sửa mã nguồn giữa lượt crawl
- **WHEN** một lượt crawl đang chạy và mã nguồn bị sửa ở bất kỳ dịch vụ nào
- **THEN** lượt crawl chạy tiếp tới khi xong, không bị khởi động lại giữa chừng

### Requirement: Sửa giao diện không phải dựng lại image
Mã nguồn giao diện SHALL được gắn từ máy chủ vào container và phục vụ trực tiếp, không qua bước build. Thay đổi SHALL có hiệu lực sau khi tải lại trang, không cần dựng lại image hay khởi động lại dịch vụ.

#### Scenario: Sửa một file giao diện
- **WHEN** sửa và lưu một file giao diện trên máy chủ rồi tải lại trang
- **THEN** thay đổi hiện ra, không dựng lại image, không khởi động lại dịch vụ nào

### Requirement: Tiến độ đẩy về theo dòng, không hỏi vòng
Tầng API SHALL đẩy tiến độ của một lượt crawl về trình duyệt theo dòng sự kiện, để người dùng thấy đang xử lý tới đâu mà không phải tải lại trang. Giao diện SHALL KHÔNG hỏi vòng (polling) để lấy tiến độ.

#### Scenario: Theo dõi một lượt crawl đang chạy
- **WHEN** người dùng mở màn tiến độ của một công việc đang chạy
- **THEN** số đã xử lý và sản phẩm đang xử lý tự cập nhật khi lượt crawl tiến triển

#### Scenario: Mở giao diện giữa chừng
- **WHEN** người dùng mở màn tiến độ sau khi công việc đã chạy được một phần
- **THEN** trạng thái hiện tại hiện ra ngay, rồi tiếp tục cập nhật theo dòng

#### Scenario: Mất kết nối dòng sự kiện
- **WHEN** dòng sự kiện đứt giữa chừng
- **THEN** giao diện nối lại và tiến độ hiển thị đúng trạng thái hiện tại, không kẹt ở số cũ

### Requirement: Tầng chạy crawl là tiến trình riêng
Tiến trình chạy crawl SHALL tách khỏi tiến trình phục vụ API.

Lý do kỹ thuật: tầng fetch dùng giao diện đồng bộ của thư viện điều khiển trình duyệt, không chạy chung được với vòng lặp sự kiện bất đồng bộ của tầng API.

#### Scenario: API vẫn phản hồi khi crawl đang chạy
- **WHEN** một lượt crawl đang chiếm trọn tiến trình chạy crawl
- **THEN** tầng API vẫn trả lời được các yêu cầu tra cứu và xem tiến độ

### Requirement: Kho dữ liệu bền qua việc dựng lại container
Kho dữ liệu SHALL nằm trên một volume bền, giữ nguyên khi container bị xoá và dựng lại. Cấu hình SHALL đảm bảo chỉ một dịch vụ ghi vào kho.

#### Scenario: Dựng lại container
- **WHEN** các container bị xoá và dựng lại
- **THEN** toàn bộ snapshot và kết quả trích xuất đã lưu vẫn còn

#### Scenario: Nhân bản tầng chạy crawl
- **WHEN** cấu hình cố nhân bản tầng chạy crawl lên nhiều bản
- **THEN** hệ thống ngăn việc đó hoặc nêu rõ ràng buộc một tiến trình ghi duy nhất, thay vì để lỗi khoá cơ sở dữ liệu xảy ra lúc chạy

### Requirement: Khoá và thông tin xác thực không nằm trong image
Khoá LLM, file thông tin xác thực và mọi giá trị bí mật khác SHALL được nạp lúc chạy qua biến môi trường hoặc volume, SHALL KHÔNG được đưa vào image.

#### Scenario: Dựng image không có khoá
- **WHEN** image được dựng
- **THEN** image không chứa khoá hay file xác thực nào, và cùng image đó chạy được với bộ khoá khác

#### Scenario: Thiếu cấu hình khoá
- **WHEN** hệ thống khởi chạy mà chưa cấu hình khoá LLM
- **THEN** hệ thống báo lỗi cấu hình rõ ràng lúc khởi động, thay vì để lượt crawl chạy được nửa chừng rồi mới hỏng
