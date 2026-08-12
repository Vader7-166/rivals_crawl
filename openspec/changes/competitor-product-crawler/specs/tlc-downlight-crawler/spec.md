## ADDED Requirements

### Requirement: Crawl end-to-end category "Đèn LED âm trần" của TLC
Hệ thống SHALL crawl toàn bộ sản phẩm trong category "Đèn LED âm trần" trên `tlclighting.com.vn`, sử dụng phối hợp site-probing, stealth-fetch, structured-data-extraction, và llm-attribute-normalization, sinh ra bản ghi tuân theo product-record-schema cho từng sản phẩm.

#### Scenario: Chạy crawler cho category
- **WHEN** crawler được chạy nhắm vào category "Đèn LED âm trần" của TLC
- **THEN** dataset đầu ra chứa 1 bản ghi cho mỗi URL sản phẩm được xác định qua kết quả site-probing của domain này, mỗi bản ghi tuân theo product-record-schema

### Requirement: Bao phủ toàn bộ phân trang
Crawler SHALL bao phủ toàn bộ sản phẩm của category, không chỉ trang danh sách đầu tiên, bất kể danh mục có phân trang hay không.

#### Scenario: Category có nhiều trang danh sách
- **WHEN** category "Đèn LED âm trần" có tổng số sản phẩm nhiều hơn số sản phẩm hiển thị trên 1 trang danh sách (danh mục có phân trang nhiều hơn 1 trang)
- **THEN** dataset đầu ra chứa sản phẩm từ tất cả các trang, không chỉ riêng trang đầu tiên
