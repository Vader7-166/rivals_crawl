## Why

Pipeline crawl hiện tại (`crawl_product_urls`) chạy hoàn toàn tuần tự — 1 sản phẩm/lần, fetch xong mới gọi LLM, gọi LLM xong mới sang sản phẩm tiếp theo. Đo thật từ log crawl 129 sản phẩm của change `competitor-product-crawler`: trung bình **21 giây/sản phẩm**, trong đó fetch (Playwright) + tầng 1/1.5 chỉ ~2.5s (12%), còn lại ~18.5s (88%) là ngồi chờ phản hồi Vertex AI. 129 sản phẩm mất 45 phút — nhưng TLC có 559 sản phẩm trải khắp mọi dòng sản phẩm (không chỉ category "Đèn LED âm trần" của pilot), và người dùng cần crawl toàn bộ site trong 1 lần chạy. Ở tốc độ hiện tại, việc đó mất ~3 giờ 15 phút cho riêng TLC — không khả thi khi mở rộng sang nhiều site khác.

## What Changes

- **Song song hoá tầng fetch và tầng LLM** trong pipeline: nhiều sản phẩm được fetch + gọi LLM đồng thời thay vì tuần tự từng cái một, với giới hạn concurrency riêng cho fetch (tránh dồn quá nhiều request vào 1 site, rủi ro bị WAF chặn) và riêng cho lệnh gọi LLM (tránh vượt rate limit Vertex AI).
- **Gộp nhiều sản phẩm vào 1 lệnh gọi LLM** (batch nhỏ 3-5 sản phẩm/lệnh) thay vì 1 sản phẩm/lệnh, để giảm số round-trip mạng — phần lớn độ trễ hiện tại là overhead cố định mỗi lệnh gọi, không tỉ lệ thuận với độ dài prompt. Có bậc thang xử lý ưu tiên độ tin cậy: gọi cả batch → nếu lỗi thì retry cả batch (rẻ vì nhỏ) → nếu vẫn lỗi thì rã batch gọi riêng từng sản phẩm (đúng cách pipeline hiện tại đang làm) — đảm bảo không bao giờ mất dữ liệu, trường hợp xấu nhất tốc độ bằng hiện trạng.
- **Dùng thẳng sitemap khi site-probing xác định đáng tin cậy** (`strategy=sitemap`) làm nguồn URL sản phẩm toàn site — không cần thêm bước phát hiện category/phân trang nào (đã kiểm chứng: TLC có 559 URL sản phẩm trải khắp mọi dòng sản phẩm ngay trong `product-sitemap.xml`, miễn phí vì đã cache sẵn từ site-probing).
- **Thêm bộ phân trang tổng quát** cho site rơi vào nhánh `menu_crawl` (không có sitemap đáng tin, như Roman): thử `<link rel="next">` → thử các URL pattern phổ biến (`?page=N`, `?paged=N`, `/page/N/`, `/trang-N`) có so sánh tập sản phẩm với trang trước để phát hiện hết trang (không dựa vào mã lỗi HTTP) → thử click nút "Xem thêm"/"Load more" (tuần tự trong nội bộ 1 trang danh mục) → nếu không có gì thì coi là danh mục 1 trang, không phải lỗi.
- **Sửa cơ chế checkpoint** (ghi tạm ra Excel mỗi N sản phẩm) để hoạt động đúng khi crawl song song — đếm theo số lượng hoàn thành (thread-safe), không còn giả định thứ tự URL gốc như trước.
- **Entry point mới scope toàn site** (thay `scripts/crawl_tlc_downlight.py` scope hẹp 1 category bằng script generic theo domain, không hard-code riêng TLC).
- **BREAKING**: `src/crawler/sites/tlc.py` (`discover_category_product_urls`, phân trang cứng kiểu WooCommerce cho 1 category) không còn được dùng cho mục tiêu crawl toàn site — thay bằng lấy thẳng `probe.product_urls` khi có sitemap đáng tin.

## Capabilities

### New Capabilities
- `concurrent-batch-llm-pipeline`: Song song hoá fetch + gọi LLM, gộp batch nhỏ sản phẩm/lệnh gọi LLM với bậc thang retry ưu tiên độ tin cậy, áp dụng chung cho mọi site (không riêng TLC).
- `site-wide-product-discovery`: Xác định toàn bộ URL sản phẩm của 1 site trong 1 lần — dùng thẳng sitemap khi đáng tin, hoặc phân trang tổng quát (pattern URL + click "Xem thêm") khi không có sitemap đáng tin.

### Modified Capabilities
(không có — capability `product-record-schema` thuộc change `competitor-product-crawler` chưa được archive, nên chưa tồn tại như 1 spec chính thức trong `openspec/specs/` để tạo delta. Thay đổi hành vi checkpoint được mô tả trong capability mới `concurrent-batch-llm-pipeline` bên dưới, vì đây thực chất là hành vi mới của pipeline song song, không phải sửa lại schema bản ghi đã chốt.)

## Impact

- **File bị ảnh hưởng**: `src/crawler/pipeline.py` (viết lại `crawl_product_urls` để song song + batch), `src/crawler/llm/` (thêm prompt/parse cho batch nhiều sản phẩm, cạnh prompt 1-sản-phẩm hiện có), `src/crawler/fetch/stealth_fetch.py` (hỗ trợ gọi đồng thời), `src/crawler/probing/` (thêm module phân trang tổng quát), `src/crawler/sites/tlc.py` (ngừng dùng cho mục tiêu toàn site), `scripts/crawl_tlc_downlight.py` (thay bằng entry point generic).
- **Quyết định kiến trúc cần chốt ở design.md**: dùng `ThreadPoolExecutor` bọc Playwright sync API (ít rewrite hơn) hay chuyển hẳn sang Playwright async API + `asyncio.gather` (rewrite nhiều hơn, lan sang cả `llm/*_provider.py` cần bản async của SDK) — ảnh hưởng tới toàn bộ cách viết lại `pipeline.py`.
- **Không ảnh hưởng schema dữ liệu đầu ra**: `ProductRecord`, field Excel, quy tắc Giá tri-state, category passthrough... giữ nguyên như change `competitor-product-crawler` đã chốt.
- **Dataset TLC hiện có** (`output/tlclighting.xlsx`, 129 sản phẩm category "Đèn LED âm trần") vẫn hợp lệ và sẽ được cơ chế crawl-lại-có-chọn-lọc tái sử dụng khi mở rộng crawl toàn site TLC (559 sản phẩm) — không cần crawl lại từ đầu.
