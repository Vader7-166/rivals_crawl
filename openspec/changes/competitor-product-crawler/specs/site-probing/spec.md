## ADDED Requirements

### Requirement: Sitemap discovery
Hệ thống SHALL dò tìm sitemap của 1 domain bằng cách đọc `robots.txt` để tìm chỉ thị `Sitemap:`, và nếu không có, SHALL thử các đường dẫn quy ước phổ biến (`/sitemap.xml`, `/sitemap_index.xml`, `/product-sitemap.xml`).

#### Scenario: robots.txt khai báo sitemap
- **WHEN** `robots.txt` của domain có dòng `Sitemap: <url>`
- **THEN** hệ thống dùng URL đó làm điểm bắt đầu dò sitemap

#### Scenario: robots.txt không khai báo sitemap
- **WHEN** `robots.txt` không có chỉ thị `Sitemap:` (hoặc `robots.txt` không tồn tại)
- **THEN** hệ thống thử lần lượt các đường dẫn quy ước phổ biến trước khi kết luận domain không có sitemap

### Requirement: Đánh giá độ tin cậy của sitemap bằng tỷ lệ URL khớp
Hệ thống SHALL chấm điểm độ tin cậy của 1 sitemap đã tìm được bằng cách lấy mẫu ngẫu nhiên URL trong sitemap, fetch từng URL mẫu và xác nhận có phải trang sản phẩm thật hay không (dùng chung tín hiệu với "Phát hiện trang/URL sản phẩm thật" bên dưới: mật độ giá, structured-data Product...). Tỷ lệ URL mẫu được xác nhận là trang sản phẩm thật (URL khớp) SHALL đạt tối thiểu 80% thì sitemap mới được coi là nguồn URL sản phẩm đáng tin cậy. `lastmod` KHÔNG được dùng làm tiêu chí quyết định (chỉ có thể log tham khảo) vì đây là giá trị site tự khai báo, không đảm bảo URL còn hợp lệ.

#### Scenario: Sitemap có tỷ lệ URL khớp cao
- **WHEN** lấy mẫu URL từ sitemap và ≥ 80% mẫu được xác nhận là trang sản phẩm thật còn tồn tại
- **THEN** sitemap được chấp nhận làm nguồn URL sản phẩm chính cho domain

#### Scenario: Sitemap có tỷ lệ URL khớp thấp
- **WHEN** lấy mẫu URL từ sitemap và tỷ lệ mẫu được xác nhận là trang sản phẩm thật thấp hơn 80% (lẫn nhiều URL trỏ tới trang nội dung/tĩnh hoặc không còn tồn tại)
- **THEN** sitemap KHÔNG được dùng làm nguồn duy nhất; hệ thống chuyển sang chiến lược crawl menu/breadcrumb dự phòng

### Requirement: Crawl menu/breadcrumb dự phòng
Khi không có sitemap đáng tin cậy, hệ thống SHALL dò theo menu điều hướng/breadcrumb của site để tìm các trang danh mục ứng viên.

#### Scenario: Không có sitemap đáng tin
- **WHEN** bước đánh giá độ tin cậy kết luận domain không có sitemap đáng tin cậy
- **THEN** hệ thống duyệt các liên kết trong menu điều hướng của site để xác định danh sách trang danh mục ứng viên

### Requirement: Phát hiện trang/URL sản phẩm thật
Hệ thống SHALL cung cấp 1 bộ phát hiện dùng chung để xác nhận 1 URL có phải trang sản phẩm thật hay không, dựa trên các tín hiệu: mật độ xuất hiện của từ giá, số khối lặp lại dạng ảnh+tên+giá, số lượng structured-data kiểu Product trên trang, và sự hiện diện của control phân trang (với trang danh mục). Bộ phát hiện này SHALL được dùng ở cả 2 chỗ: (a) xác nhận trang danh mục ứng viên khi crawl menu/breadcrumb dự phòng, và (b) lấy mẫu xác nhận URL khi chấm điểm độ tin cậy sitemap.

#### Scenario: URL mẫu là trang sản phẩm thật
- **WHEN** trang tại URL được kiểm tra có giá hiển thị và/hoặc structured-data kiểu Product
- **THEN** URL được xác nhận là trang sản phẩm thật

#### Scenario: Trang danh mục thực chất là landing rỗng
- **WHEN** trang ứng viên không có (hoặc rất ít) xuất hiện từ giá, không có khối lặp lại ảnh+tên+giá, và không có structured-data Product nào
- **THEN** trang bị phân loại là trang nội dung/landing, không được dùng làm nguồn URL sản phẩm, và được gắn cờ để review

#### Scenario: Trang danh mục là lưới sản phẩm thật
- **WHEN** trang ứng viên có nhiều khối lặp lại ảnh+tên+giá và/hoặc control phân trang
- **THEN** trang được phân loại là lưới sản phẩm thật và được dùng làm nguồn URL sản phẩm

### Requirement: Cache kết quả probe theo domain
Hệ thống SHALL lưu lại kết quả probe (chiến lược nguồn URL, danh sách URL danh mục hợp lệ) theo từng domain, để các lần crawl sau không phải probe lại từ đầu.

#### Scenario: Domain đã có kết quả probe còn hiệu lực
- **WHEN** 1 domain đã có kết quả probe được lưu và còn trong thời hạn hiệu lực
- **THEN** lần crawl tiếp theo tái sử dụng kết quả probe đã cache, không thực hiện lại các bước dò sitemap/menu
