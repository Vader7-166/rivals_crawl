## ADDED Requirements

### Requirement: Lớp fetch thống nhất qua cloakBrowser
Mọi yêu cầu lấy nội dung trang từ site đối thủ SHALL đi qua dịch vụ fetch dùng cloakBrowser, không dùng HTTP client thuần cho bất kỳ tầng trích xuất nào.

#### Scenario: Bất kỳ tầng nào cần lấy nội dung trang
- **WHEN** tầng site-probing, structured-data-extraction, hoặc llm-attribute-normalization cần nội dung của 1 URL
- **THEN** nội dung được lấy thông qua dịch vụ fetch dựa trên cloakBrowser, không gọi trực tiếp HTTP client khác

### Requirement: Fingerprint request thực tế
Dịch vụ fetch SHALL gửi header/fingerprint giống trình duyệt thật để tránh bị chặn bởi các cơ chế lọc bot cơ bản.

#### Scenario: Site chặn fingerprint đơn giản
- **WHEN** site đích trả về lỗi chặn bot (vd HTTP 406/403) cho 1 request có fingerprint tối giản
- **THEN** hệ thống thử lại với fingerprint/header đầy đủ giống trình duyệt thật và request thành công

### Requirement: Chờ nội dung render bằng JS
Dịch vụ fetch SHALL đợi/kích hoạt các phần nội dung được render phía client (ví dụ panel thông số kỹ thuật dạng tab) trước khi trả nội dung trang cho các tầng trích xuất phía sau.

#### Scenario: Nội dung chỉ xuất hiện sau khi tương tác/JS chạy
- **WHEN** trang đích có 1 vùng nội dung (vd tab "Thông số kỹ thuật") rỗng trong HTML tải về ban đầu nhưng được điền bằng JavaScript sau khi tương tác hoặc sau khi trang tải xong
- **THEN** dịch vụ fetch thực hiện tương tác/đợi cần thiết và trả về nội dung trang đã bao gồm phần được render động đó
