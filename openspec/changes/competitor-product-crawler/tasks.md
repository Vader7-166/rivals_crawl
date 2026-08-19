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
- [x] 9.4 Chạy `/verify` (hoặc tương đương) trên pipeline TLC pilot trước khi coi change hoàn thành — ĐÃ CHẠY `/opsx:verify` thật (ghi chú cũ nói skill này không tự gọi được từ phía trợ lý là SAI — gọi được qua Skill tool). Kết quả: `openspec validate --strict` pass; dựng lại `.venv` từ đầu và chạy 25/25 test pass; đối chiếu thủ công 23 requirement của 6 spec với code. Không có requirement nào chưa được implement. Phát hiện 2 điểm lệch spec↔code, ĐÃ SỬA CẢ 2 theo yêu cầu user:

  (a) **Output LLM lỗi không được gắn cờ.** `pipeline.py` nuốt lỗi validate nhưng `tags` không nằm trong `REQUIRED_FIELDS` nên bản ghi vẫn ra `crawl_status=ok` — trái spec llm-attribute-normalization ("kết quả không hợp lệ SHALL được gắn cờ để review"). Đã kiểm chứng bằng probe trước khi sửa: status = `ok`, không được gắn cờ. **Sửa:** thêm `tags` vào `REQUIRED_FIELDS` + `missing_required_fields` coi `{}` là thiếu (`record/schema.py`), pipeline ghi thêm lý do vào `crawl_error`. Chọn cách này thay vì chỉ set status trong pipeline vì `crawl_status` KHÔNG được ghi ra Excel — trạng thái phải suy ra lại được từ chính các cột đã lưu, nên `tags` rỗng là dấu vết duy nhất sống sót qua vòng ghi/đọc file.

  (b) **Chấm điểm độ tin cậy sitemap không thể từ chối sitemap rác.** `looks_like_single_product_page` đếm chữ "giá" — chữ này có ở menu/footer mọi trang tiếng Việt. **Sửa:** đổi sang đếm SỐ TIỀN thật (`\d[\d.,]*\s*(vnđ|vnd|đồng|₫|đ)`) trên TEXT đã trích (không phải HTML thô — WooCommerce tách số và ký hiệu tiền ra 2 thẻ nên regex trên HTML thô đếm ra 0 cho chính trang TLC). Ngưỡng chọn dựa trên đo thực nghiệm 5 fixture thật, trong đó 2 fixture "rác" MỚI (`tlc_blog_post.html`, `tlc_static_page.html`) lấy trực tiếp từ `post-sitemap.xml`/`page-sitemap.xml` của TLC. Đã thử và LOẠI marker "Liên hệ" khỏi công thức vì nó có ở footer mọi trang TLC (blog 5 lần, trang tĩnh 4 lần) làm cả 2 fixture rác pass trở lại. Kết quả công thức `structured_data>=1 or so_tien>=1` tách đúng cả 5/5. **Xác nhận khi chạy thật sau khi sửa: độ tin cậy = 90% (trước khi sửa luôn là 100%)** — bộ phát hiện giờ thực sự loại được mẫu, vẫn qua ngưỡng 80%.

  Điểm còn lại (mức SUGGESTION, chưa sửa): `probing/robots.py` + `probing/sitemap.py` gọi thẳng `requests` thay vì `StealthFetcher` — code có comment biện minh (robots/sitemap là tài nguyên máy đọc, không phải "nội dung trang") nhưng spec stealth-fetch chưa ghi ngoại lệ này; `click_selectors`/`wait_selector` chưa có caller nào; RDFa chưa có fixture riêng. Chưa có test tự động khoá lại 2 fix (a)/(b) — user chọn bỏ qua bước viết test

## 10. Khuôn cột đầy đủ & output nhiều sheet

- [x] 10.1 Giữ **đủ 20 cột** của sheet "2. LED Downlight" thay vì 17 — trả lại `STT`, `Giá đối chiếu`, `VD HDSD`. Cột không lấy được dữ liệu thì **để ô trống chứ không bỏ cột**: khuôn cột lệch thì bên nhận phải căn chỉnh tay trước khi ghép vào file tham chiếu. `Giá đối chiếu` + `VD HDSD` thêm vào `OPTIONAL_FIELDS` (để trống là đúng, không phải dấu hiệu crawl hỏng). Tên cột chép **nguyên văn** kể cả khoảng trắng thừa (`' category 1 '`, `'Thông số kỹ thuật '`) để header so khớp tuyệt đối với khuôn gốc.
- [x] 10.2 `STT` do writer tự đánh 1..N theo từng sheet; khi đọc lại thì **bỏ giá trị cũ** — bản ghi đổi sheet (category đổi) sẽ làm số cũ thủng/trùng ở lần ghi sau.
- [x] 10.3 Đổi output sang **1 file, mỗi loại sản phẩm 1 sheet** (chia theo `category 1` của chính site nguồn), bám cách tổ chức của `product_Metadata (1).xlsx`. Thứ tự sheet theo thứ tự xuất hiện đầu tiên (phản ánh thứ tự duyệt của site) chứ không sắp A–Z; bản ghi chưa có `category 1` gom vào sheet `Chưa phân loại` cuối file để lần sau còn crawl lại được. Xử lý giới hạn 31 ký tự + ký tự cấm của tên sheet Excel, có chống trùng tên sau khi cắt.
- [x] 10.4 `excel_reader` ghép cột theo **TÊN header (đã strip)** thay vì theo vị trí, và gộp toàn bộ sheet lại thành 1 map phẳng. Nhờ vậy file 17 cột của phiên bản trước vẫn đọc lại được — nếu không, đổi khuôn cột đồng nghĩa bắt crawl lại từ đầu cả site. Đã kiểm chứng: đọc `output/tlclighting.xlsx` (17 cột, 1 sheet) ra đúng 129 bản ghi.
- [x] 10.5 **Sửa lỗi lọc sitemap taxonomy** (phát hiện khi crawl toàn site): bộ lọc "sub-sitemap có chữ product" kéo theo cả `product_cat-sitemap.xml`, làm **73 trang danh mục** `/danh-muc/...` lọt vào danh sách URL sản phẩm (559 thay vì 486). Chạy thử 6 URL đầu tiên: 0/6 OK, toàn bản ghi rỗng vì trang danh mục không có JSON-LD Product. Đã loại sitemap taxonomy theo tiền tố `product_` của WooCommerce → **486 URL = 485 sản phẩm + 1 trang `/shop/`**, độ tin cậy 100%. Ghi chú cũ ở 8.1 nói "559 URL sản phẩm thuần" là SAI.
- [x] 10.6 Thêm test khoá lại khuôn cột và cấu trúc sheet (`tests/test_excel_output.py`, 7 test) + test chống tái phát lỗi sitemap taxonomy. Tổng 33/33 test pass.
- [x] 10.7 Thêm `scripts/crawl_tlc_all.py` (crawl toàn site, ghi file theo lô 40 SP để mất mạng/cạn quota giữa chừng không mất sạch công) và `scripts/report_crawl.py` (đo chất lượng dữ liệu của file đã crawl).
