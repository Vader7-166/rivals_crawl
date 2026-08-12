## 1. Project setup

- [x] 1.1 Khởi tạo cấu trúc project (ngôn ngữ/runtime, quản lý dependency) và cấu hình biến môi trường cho: Vertex AI credentials (project/region, model `gemini-2.5-flash`), DeepSeek API key, cloakBrowser
- [x] 1.2 Thêm dependency: cloakBrowser, thư viện parser schema.org tổng quát (JSON-LD/Microdata/RDFa, vd họ `extruct`), SDK Vertex AI, SDK/HTTP client DeepSeek, thư viện ghi Excel (`.xlsx`)

## 2. Product record schema & Excel output

- [x] 2.1 Định nghĩa model/struct bản ghi sản phẩm theo `product-record-schema` spec (field, kiểu dữ liệu, field nào nullable), gồm cả field trạng thái crawl nội bộ (ok/error/partial-missing-fields)
- [x] 2.2 Cài đặt logic Giá tri-state (số / literal "Liên hệ" / null) và validate không cho phép nhầm lẫn giữa "Liên hệ" và null
- [x] 2.3 Cài đặt writer ghi bản ghi ra 1 file `.xlsx` riêng theo từng site, cột đặt tên/thứ tự mô phỏng sheet "2. LED Downlight" của `product_Metadata (1).xlsx`; field trạng thái crawl KHÔNG xuất ra cột Excel
- [x] 2.4 Cài đặt logic đọc lại file `.xlsx` đã có của 1 site (nếu tồn tại) để xác định bản ghi nào ở trạng thái lỗi/thiếu field, phục vụ crawl lại có chọn lọc

## 3. Stealth fetch layer

- [x] 3.1 Tích hợp cloakBrowser làm client fetch dùng chung, expose 1 interface fetch(url) cho các tầng khác gọi
- [x] 3.2 Cấu hình fingerprint/header thực tế mặc định (UA, Accept-Language...) theo interface đó
- [x] 3.3 Cài đặt cơ chế đợi/kích hoạt nội dung render bằng JS (vd tab thông số kỹ thuật) trước khi trả HTML cho tầng trích xuất
- [x] 3.4 Thêm retry khi gặp lỗi chặn bot cơ bản (406/403) trước khi coi là fetch thất bại

## 4. Site probing

- [x] 4.1 Cài đặt đọc `robots.txt` tìm chỉ thị `Sitemap:`
- [x] 4.2 Cài đặt thử các path sitemap quy ước khi robots.txt không khai báo (`/sitemap.xml`, `/sitemap_index.xml`, `/product-sitemap.xml`)
- [x] 4.3 Cài đặt bộ phát hiện "trang/URL sản phẩm thật" dùng chung (tín hiệu: mật độ từ giá, khối lặp ảnh+tên+giá, số Product structured-data, control phân trang) — đã kiểm chứng thực nghiệm trên cặp fixture landing/listing thật của Roman, phải bỏ tín hiệu pagination/structured-data làm ngưỡng phụ vì cả 2 trang đều có, chỉ `card_link_count` (số thẻ `<a>` bọc `<img>`) mới tách được (17 vs 52, ngưỡng chọn = 30)
- [x] 4.4 Cài đặt chấm điểm độ tin cậy sitemap bằng cách lấy mẫu URL, chạy qua bộ phát hiện ở 4.3, chấp nhận sitemap khi ≥ 80% mẫu khớp là trang sản phẩm thật
- [x] 4.5 Cài đặt fallback crawl menu/breadcrumb khi không có sitemap đáng tin cậy, áp bộ phát hiện ở 4.3 cho từng trang danh mục ứng viên và gắn cờ trang bị nghi là landing rỗng
- [x] 4.6 Cài đặt cache kết quả probe theo domain (chiến lược nguồn URL + danh sách URL danh mục hợp lệ)

## 5. Structured data extraction (Tầng 1)

- [x] 5.1 Cài đặt parser đọc JSON-LD Product/BreadcrumbList — phải xử lý trường hợp 1 trang có NHIỀU block ld+json riêng biệt (case TLC: block core WordPress có BreadcrumbList rỗng/gãy, block Yoast SEO riêng mới có Product+BreadcrumbList đầy đủ), ưu tiên tìm Product và BreadcrumbList trong cùng 1 graph thay vì gộp phẳng toàn bộ rồi lấy match đầu tiên
- [x] 5.2 Cài đặt parser đọc Microdata Product (itemscope/itemprop)
- [x] 5.3 Cài đặt parser đọc RDFa (dùng chung code với Microdata vì `extruct` trả về cùng 1 hình dạng node cho cả 2 cú pháp)
- [x] 5.4 Cài đặt fallback đọc OpenGraph/meta tag khi không có schema.org nào
- [x] 5.5 Cài đặt logic map kết quả các parser trên vào field tương ứng của product-record-schema, để trống field không lấy được

## 6. CSS fallback nhẹ (Tầng 1.5)

- [x] 6.1 Định nghĩa cấu trúc cấu hình fallback selector tối thiểu theo domain (chỉ để vá field còn thiếu sau tầng 1, không phải full scraping config)
- [x] 6.2 Cài đặt cơ chế: nếu field còn null sau tầng 1 và domain có fallback selector cho field đó → áp dụng selector để lấy giá trị — kiểm chứng bằng fixture Roman thật (`div.price .val` → 339900.0, `div.code .val` → "ELD9001/12W")

## 7. LLM attribute normalization (Tầng 2)

- [x] 7.1 Thiết kế prompt + JSON output schema chung cho việc trích xuất Thông số kỹ thuật → Tags (schema thuộc tính linh hoạt, không cố định)
- [x] 7.2 Cài đặt provider interface LLM chung, implement adapter cho Vertex AI dùng model `gemini-2.5-flash`
- [x] 7.3 Implement adapter cho DeepSeek (v4-flash) theo cùng interface
- [x] 7.4 Cài đặt logic fallback tự động: Vertex AI lỗi/hết quota → chuyển sang DeepSeek, log lại lần chuyển đổi — kiểm chứng bằng test với provider giả (test_llm_fallback.py)
- [x] 7.5 Cài đặt bước làm sạch HTML/trích phần nội dung liên quan trước khi đưa vào prompt (giảm token, loại nav/script/tracking) — có xử lý riêng bảng thông số lộn xộn kiểu TLC (2 cột br-stacked) thành cặp "label: value"
- [x] 7.6 Cài đặt validate output LLM (đúng JSON, giá trị hợp lý) và gắn cờ bản ghi khi output không hợp lệ

## 8. TLC pilot crawler

- [x] 8.1 Chạy site-probing cho `tlclighting.com.vn`, xác nhận `product-sitemap.xml` được nhận diện là nguồn đáng tin cậy — chạy THẬT trên site sống: phát hiện `sitemap_index.xml` → lúc đầu lẫn cả URL blog/trang tĩnh (559 vs kỳ vọng), đã sửa `resolve_sitemap_entries` ưu tiên sub-sitemap có "product" trong tên; sau khi sửa: 559 URL sản phẩm thuần, độ tin cậy 100%
- [x] 8.2 Lọc danh sách URL sản phẩm thuộc category "Đèn LED âm trần" từ kết quả probe — chạy THẬT: `discover_category_product_urls` phân trang 7 trang, ra đúng 129 URL, đối chiếu 100% khớp với sitemap đã probe (0 URL lệch)
- [x] 8.3 Nối toàn bộ pipeline (fetch → tầng 1 → tầng 1.5 → tầng 2) chạy end-to-end cho danh sách URL đó — chạy THẬT với Vertex AI (Gemini 2.5 Flash, credentials người dùng cung cấp): **129/129 sản phẩm crawl thành công, 0 lỗi**
- [x] 8.4 Xuất file `tlclighting.xlsx` chứa toàn bộ bản ghi — **129 dòng dữ liệu**, khớp chính xác 129 sản phẩm hiển thị trên site
- [x] 8.5 Review thủ công 1 mẫu bản ghi (đối chiếu trực tiếp với trang sản phẩm gốc) — đối chiếu dòng đầu tiên với dữ liệu đã kiểm tra tay lúc explore: tên/mã SP (TLC-AECA-VB-10W)/giá (166.000)/category đều khớp 100%; quét toàn bộ 129 dòng: 0 thiếu tên/giá/mã SP/category1/tags, giá từ 123.000-1.445.000đ hợp lý, Tags trung bình ~13 thuộc tính/sản phẩm (phong phú hơn hẳn 4 field mẫu của rangdong, đúng tinh thần "schema linh hoạt")
- [x] 8.6 Chạy lại pipeline theo cơ chế crawl-lại-có-chọn-lọc (2.4) trên chính dataset TLC — chạy lại thật: hoàn tất trong ~17s (so với ~7 phút lần đầu), log xác nhận "0 cần crawl lại" và **0 lần gọi LLM provider** — đúng như thiết kế

## 9. Kiểm thử & xác minh

- [x] 9.1 Viết test cho bộ phát hiện "trang lưới sản phẩm thật" dùng fixture mô phỏng case landing rỗng (dựa theo case Roman đã khảo sát)
- [x] 9.2 Viết test cho structured-data extraction với fixture JSON-LD, fixture Microdata riêng biệt (đảm bảo không hard-code theo 1 cú pháp)
- [x] 9.3 Viết test cho logic Giá tri-state (số/"Liên hệ"/null)
- [ ] 9.4 Chạy `/verify` (hoặc tương đương) trên pipeline TLC pilot trước khi coi change hoàn thành — skill `verify` chỉ chạy được khi USER tự gõ `/verify` (không tự gọi được từ phía trợ lý); đã làm phần "tương đương" thủ công: chạy toàn bộ 25 test (`pytest tests/`) pass, và 2 lần chạy sống thật `scripts/crawl_tlc_downlight.py` với Vertex AI thật (129/129 OK lần đầu, selective re-crawl xác nhận đúng ở lần 2) — đề xuất user tự gõ `/verify` nếu muốn thêm 1 lớp xác minh độc lập
