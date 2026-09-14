## ADDED Requirements

### Requirement: Dùng thẳng sitemap làm nguồn URL toàn site khi đáng tin cậy
Khi kết quả site-probing của 1 domain xác định chiến lược là sitemap (đáng tin cậy), hệ thống SHALL dùng trực tiếp toàn bộ danh sách URL sản phẩm đã có từ kết quả probe làm nguồn crawl toàn site, không thực hiện thêm bất kỳ bước phát hiện category hay phân trang nào.

#### Scenario: Site có sitemap đáng tin cậy bao phủ nhiều dòng sản phẩm
- **WHEN** kết quả site-probing của 1 domain có strategy là sitemap và danh sách URL sản phẩm bao gồm nhiều dòng sản phẩm khác nhau
- **THEN** hệ thống crawl toàn bộ danh sách URL đó, không giới hạn theo 1 category cụ thể nào

### Requirement: Phân trang tổng quát khi không có sitemap đáng tin cậy
Khi kết quả site-probing của 1 domain xác định chiến lược là crawl menu (không có sitemap đáng tin cậy), hệ thống SHALL liệt kê toàn bộ URL sản phẩm của từng trang danh mục đã xác nhận là lưới thật bằng cách thử lần lượt các cơ chế phân trang theo thứ tự ưu tiên: tín hiệu semantic (rel=next), sau đó các pattern URL phổ biến có so sánh nội dung để phát hiện hết trang, sau đó nút "tải thêm" dạng JS, cuối cùng coi là danh mục 1 trang nếu không cơ chế nào áp dụng được.

#### Scenario: Trang danh mục có liên kết rel=next
- **WHEN** trang danh mục đang xử lý có thẻ liên kết mang thuộc tính rel=next
- **THEN** hệ thống dùng liên kết đó để lấy trang tiếp theo, không thử các cơ chế khác

#### Scenario: Không có rel=next nhưng URL pattern phổ biến hoạt động
- **WHEN** trang danh mục không có rel=next, và thử 1 trong các pattern URL phổ biến (tăng số trang) cho ra trang chứa URL sản phẩm khác với trang trước
- **THEN** hệ thống tiếp tục tăng số trang theo đúng pattern đó cho tới khi trang mới không còn URL sản phẩm nào khác trang trước

#### Scenario: Trang "ảo" trả về HTTP 200 nhưng nội dung lặp lại trang trước
- **WHEN** 1 URL trang tiếp theo theo pattern thử nghiệm trả về mã HTTP thành công nhưng tập URL sản phẩm trên trang đó trùng hoàn toàn với trang liền trước
- **THEN** hệ thống coi đây là dấu hiệu đã hết trang (không dựa vào mã lỗi HTTP để quyết định dừng)

#### Scenario: Không pattern URL nào hoạt động nhưng có nút tải thêm dạng JS
- **WHEN** không có rel=next, không pattern URL nào cho kết quả mới, và trang có 1 phần tử tương tác dạng "xem thêm"/"tải thêm"
- **THEN** hệ thống thực hiện click liên tiếp vào phần tử đó, thu thập URL sản phẩm mới sau mỗi lần click, dừng khi 1 lần click không sinh thêm URL sản phẩm nào mới

#### Scenario: Danh mục không có bất kỳ cơ chế phân trang nào
- **WHEN** trang danh mục không có rel=next, không pattern URL nào hoạt động, và không có phần tử tải thêm dạng JS
- **THEN** hệ thống coi danh mục chỉ có đúng 1 trang, không đánh dấu đây là lỗi

### Requirement: Việc liệt kê phân trang của các danh mục khác nhau chạy độc lập
Khi 1 site có nhiều trang danh mục cần liệt kê phân trang (chiến lược crawl menu), hệ thống SHALL cho phép việc liệt kê của các trang danh mục khác nhau chạy đồng thời với nhau, trong khi việc liệt kê bên trong CÙNG 1 trang danh mục (đặc biệt khi dùng cơ chế click "tải thêm") SHALL thực hiện tuần tự.

#### Scenario: Nhiều trang danh mục cùng cần liệt kê bằng cơ chế click tải thêm
- **WHEN** 1 site có 2 trang danh mục khác nhau đều phải dùng cơ chế click "tải thêm" để liệt kê hết sản phẩm
- **THEN** việc click liệt kê của 2 trang danh mục đó có thể diễn ra đồng thời với nhau, nhưng trong nội bộ mỗi trang, các lần click diễn ra tuần tự theo đúng thứ tự

### Requirement: Kết quả liệt kê được gộp và loại trùng theo toàn site
Sau khi liệt kê xong tất cả trang danh mục của 1 site (chiến lược crawl menu), hệ thống SHALL gộp toàn bộ URL sản phẩm thu được từ mọi trang danh mục và loại bỏ trùng lặp trước khi đưa vào crawl, vì 1 sản phẩm có thể xuất hiện ở nhiều trang danh mục khác nhau.

#### Scenario: Cùng 1 sản phẩm xuất hiện ở 2 trang danh mục
- **WHEN** 1 URL sản phẩm xuất hiện trong kết quả liệt kê của cả 2 trang danh mục khác nhau
- **THEN** danh sách URL sản phẩm cuối cùng đưa vào crawl chỉ chứa URL đó đúng 1 lần
