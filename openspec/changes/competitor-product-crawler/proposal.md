## Why

Cần thu thập dữ liệu sản phẩm từ các website đối thủ (ngành đèn LED chiếu sáng) để có dữ liệu so sánh, nhưng mỗi site dùng một nền tảng/cấu trúc HTML/kiểu structured-data khác nhau hoàn toàn — đã khảo sát trực tiếp 3 site (TLC, Roman, KingLED) và không site nào giống site nào ở bất kỳ khâu nào (nền tảng, cú pháp structured data, độ sạch của bảng thông số, cách phân trang, cách lấy danh sách URL sản phẩm). Viết và bảo trì một bộ config crawl riêng cho từng site sẽ không mở rộng được khi số lượng đối thủ tăng lên. Cần một pipeline crawl tổng quát, tự thích ứng theo từng site thay vì hard-code theo từng site.

## What Changes

- Thêm cơ chế **site probing** chạy một lần khi thêm 1 domain đối thủ mới: dò `robots.txt`/sitemap để tìm nguồn danh sách URL sản phẩm đáng tin cậy, và khi không có sitemap tin cậy thì tự phát hiện trang nào là lưới sản phẩm thật (tránh crawl nhầm trang landing/nội dung).
- Thêm lớp **fetch/render** dùng cloakBrowser (Chromium ẩn danh, tương thích API Playwright) làm điểm fetch chung cho toàn bộ pipeline, xử lý cả chặn bot cơ bản lẫn nội dung chỉ xuất hiện sau khi JS chạy.
- Thêm **tầng 1 — trích xuất structured data tổng quát**: đọc JSON-LD, Microdata, RDFa, và OpenGraph meta tags (không hard-code theo 1 cú pháp) để lấy các field có sẵn miễn phí (tên, giá, ảnh, url, breadcrumb, sku khi có).
- Thêm **tầng 1.5 — CSS selector fallback nhẹ** cho các field còn thiếu sau tầng 1, dùng cấu hình tối thiểu theo site (không phải toàn bộ config crawl).
- Thêm **tầng 2 — LLM normalization**: dùng LLM (Vertex AI với model Gemini 2.5 Flash làm chính, fallback DeepSeek v4-flash) để trích xuất/chuẩn hoá phần thông số kỹ thuật dạng tự do thành field `Tags` (JSON), với schema thuộc tính linh hoạt theo từng site/category thay vì ép về 1 schema cố định.
- Định nghĩa **schema bản ghi sản phẩm đầu ra**, dựa theo khuôn cột hiện có (`product_Metadata (1).xlsx`, sheet "2. LED Downlight") với các điều chỉnh: bỏ cột Giá đối chiếu; Mã SAP/Link mua hàng online là optional (để trống khi site không có); Giá nhận giá trị literal `"Liên hệ"` khi site không công khai giá (khác NULL = chưa crawl được); category giữ nguyên breadcrumb gốc của từng site, không chuẩn hoá chéo site.
- **Output**: mỗi site đối thủ crawl ra 1 file Excel (`.xlsx`) riêng, cấu trúc cột mô phỏng sát khuôn `product_Metadata (1).xlsx`. Crawl 1 lần duy nhất cho mỗi site; các bản ghi lỗi/thiếu field sẽ được crawl lại có chọn lọc ở lần chạy sau, không crawl lại toàn bộ và không có lịch crawl định kỳ.
- Triển khai **pilot crawler cho TLC** (`tlclighting.com.vn`, category "Đèn LED âm trần", 129 sản phẩm) chạy end-to-end qua toàn bộ pipeline trên, làm bằng chứng kiến trúc hoạt động và làm file Excel đầu ra đầu tiên.

## Capabilities

### New Capabilities
- `site-probing`: Dò và chọn nguồn danh sách URL sản phẩm đáng tin cậy cho 1 domain đối thủ (sitemap hoặc crawl menu + phát hiện trang lưới sản phẩm thật), kết quả cache theo domain.
- `stealth-fetch`: Lớp fetch/render trang dùng cloakBrowser, dùng chung cho mọi tầng trích xuất, xử lý cả anti-bot lẫn nội dung render bằng JS.
- `structured-data-extraction`: Trích xuất dữ liệu sản phẩm từ structured data có sẵn trên trang (JSON-LD/Microdata/RDFa/OpenGraph) theo cách tổng quát, không riêng cho 1 site.
- `llm-attribute-normalization`: Dùng LLM để trích xuất/chuẩn hoá thông số kỹ thuật tự do thành field Tags (JSON) theo schema linh hoạt per-site, có fallback provider khi provider chính hết quota/lỗi.
- `product-record-schema`: Định nghĩa và validate cấu trúc bản ghi sản phẩm đầu ra dùng chung cho mọi site đối thủ (field bắt buộc/optional, quy tắc giá trị sentinel, category passthrough).
- `tlc-downlight-crawler`: Crawl end-to-end category "Đèn LED âm trần" trên TLC bằng pipeline trên, sinh dataset đầu ra theo `product-record-schema`.

### Modified Capabilities
(không có — đây là dự án mới, chưa có capability nào tồn tại trước đó)

## Impact

- **Hệ thống mới hoàn toàn** (thư mục dự án hiện đang trống) — không có code/API cũ bị ảnh hưởng.
- **Dependency mới**: cloakBrowser (fetch/render), 1 thư viện parser schema.org tổng quát (đọc JSON-LD/Microdata/RDFa, ví dụ họ `extruct`), SDK/API client cho Vertex AI và DeepSeek.
- **Chi phí vận hành mới**: gọi LLM API (Vertex AI, fallback DeepSeek) theo mỗi sản phẩm cần chuẩn hoá thông số — chi phí ước tính rất thấp (đã kiểm chứng ở tier DeepSeek: dưới $1 cho một category ~200 sản phẩm khi làm sạch HTML trước khi đưa vào LLM).
- **Dữ liệu ra**: 1 dataset sản phẩm TLC category "Đèn LED âm trần" theo schema đã chốt, làm nền để mở rộng sang các site đối thủ khác (Roman, KingLED, ...) ở các change sau mà không cần thiết kế lại pipeline.
