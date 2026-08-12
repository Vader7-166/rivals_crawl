## ADDED Requirements

### Requirement: Đọc structured data đa cú pháp
Hệ thống SHALL đọc dữ liệu sản phẩm dạng schema.org ở cả 3 cú pháp phổ biến — JSON-LD, Microdata, RDFa — không chỉ giới hạn ở 1 cú pháp.

#### Scenario: Trang chỉ dùng Microdata, không có JSON-LD
- **WHEN** trang sản phẩm nhúng dữ liệu `Product` dưới dạng Microdata (`itemscope`/`itemprop`) và không có khối `application/ld+json` nào
- **THEN** hệ thống vẫn trích xuất được các field name/sku/price/image từ khối Microdata đó

#### Scenario: Trang dùng JSON-LD
- **WHEN** trang sản phẩm nhúng dữ liệu `Product` dưới dạng JSON-LD
- **THEN** hệ thống trích xuất các field tương ứng từ khối JSON-LD

### Requirement: Fallback OpenGraph/meta tags
Khi trang không có structured data schema.org nào, hệ thống SHALL thử lấy các field còn thiếu từ OpenGraph và meta tag tiêu chuẩn.

#### Scenario: Không có schema.org nhưng có OpenGraph
- **WHEN** trang không có JSON-LD/Microdata/RDFa nào nhưng có các thẻ `og:title`, `og:image`, hoặc thẻ giá tương tự
- **THEN** hệ thống trả về các field lấy được từ thẻ OpenGraph/meta, để trống các field còn lại cho tầng khác xử lý tiếp

### Requirement: Map field structured data vào schema bản ghi chuẩn
Các field trích xuất được từ structured data SHALL được map vào đúng field tương ứng trong schema bản ghi sản phẩm chuẩn (tên, giá, ảnh, URL sản phẩm, breadcrumb/category, mã sản phẩm khi có); field nào không lấy được từ structured data SHALL để trống (null) cho tầng trích xuất tiếp theo xử lý, không được suy diễn hay điền giá trị mặc định.

#### Scenario: Structured data có tên/giá/ảnh nhưng thiếu category
- **WHEN** structured data của trang cung cấp tên, giá, ảnh sản phẩm nhưng không có breadcrumb/category
- **THEN** 3 field đó được điền vào bản ghi, còn field category để trống (null) để tầng khác (CSS fallback hoặc thủ công) xử lý tiếp
