## Context

Change `competitor-product-crawler` (38/39 task, chưa archive) đã dựng xong pipeline 4 tầng (site-probing → structured-data → CSS fallback → LLM normalization) và chạy thành công thật với Vertex AI trên TLC/category "Đèn LED âm trần" (129 sản phẩm). Đo thật từ log crawl đó:

| | Thời gian trung bình | Tỷ lệ |
|---|---|---|
| Fetch (Playwright) + tầng 1/1.5 | ~2.5s | 12% |
| Chờ phản hồi Vertex AI (tầng 2) | ~18.5s | 88% |
| **Tổng/sản phẩm** | **~21s** | 100% |

Toàn bộ chạy tuần tự — `crawl_product_urls` là 1 vòng `for` thuần, xử lý xong sản phẩm này mới sang sản phẩm kế. 129 sản phẩm mất 45 phút. Nhưng site-probing đã xác nhận TLC có **559 sản phẩm toàn site** (trải khắp mọi dòng sản phẩm, không chỉ category âm trần) qua `product-sitemap.xml` — ở tốc độ hiện tại sẽ mất ~3h15. Mục tiêu mới: crawl toàn bộ 1 site trong 1 lần chạy, tối ưu tối đa (không giới hạn thời gian cứng, nhưng phải nhanh hơn đáng kể so với hiện trạng).

## Goals / Non-Goals

**Goals:**
- Song song hoá fetch + gọi LLM để giảm thời gian chờ I/O (88% thời gian hiện tại là ngồi chờ mạng, không phải tính toán).
- Gộp batch nhỏ (3-5 sản phẩm/lệnh LLM) để giảm số round-trip mạng, với bậc thang xử lý ưu tiên độ tin cậy — không bao giờ mất dữ liệu, trường hợp xấu nhất tốc độ bằng hiện trạng.
- Xác định toàn bộ URL sản phẩm của 1 site trong 1 lần: dùng thẳng sitemap khi đáng tin (miễn phí), phân trang tổng quát khi không có sitemap đáng tin.
- Giữ nguyên schema bản ghi đầu ra, cơ chế crawl-lại-có-chọn-lọc, và tính "1 file Excel/site" đã chốt ở change trước — đây là optimization pipeline nội bộ, không đổi hợp đồng đầu ra.

**Non-Goals:**
- Không song song hoá nhiều site khác nhau cùng lúc (quyết định đã chốt trong explore — mỗi lần chạy chỉ nhắm 1 domain).
- Không tự động phát hiện site đối thủ mới (ngoài phạm vi, giống change trước).
- Không cam kết 1 con số thời gian chạy cụ thể — tối ưu tối đa trong giới hạn an toàn (không bị site đối thủ chặn, không vượt quota LLM), không phải tối ưu bằng mọi giá.
- Không tự giải CAPTCHA hay vượt qua các cơ chế chống bot nâng cao hơn cloakBrowser đã xử lý.

## Decisions

### 1. Chuyển lớp fetch từ Playwright sync API sang async API — không dùng ThreadPoolExecutor bọc sync API

**Vấn đề với phương án ban đầu nêu trong proposal** ("ThreadPoolExecutor bọc `StealthFetcher` sync hiện có, ít rewrite hơn"): đây là giả định sai. Playwright sync API **không an toàn khi chia sẻ 1 `Browser`/`BrowserContext` giữa nhiều OS thread** — driver connection của sync API gắn với đúng 1 thread tạo ra nó. Muốn dùng ThreadPoolExecutor thật sự an toàn, mỗi thread phải tự mở **1 Playwright instance + 1 browser process riêng** — nghĩa là N thread = N browser process chạy song song (mỗi process headless Chromium tốn ~100-200MB RAM), tốn tài nguyên hơn nhiều so với việc cần thiết.

**Quyết định**: chuyển `StealthFetcher` sang Playwright **async API** (`async_playwright`). Đây là cách chính thức được hỗ trợ để có nhiều context/page chạy đồng thời trên **cùng 1 browser process** — nhẹ hơn nhiều so với nhiều process riêng. Việc này lan ra:
- `pipeline.py`: viết lại `crawl_product_urls` thành hàm `async`, điều phối bằng `asyncio.gather`/`asyncio.Semaphore`.
- `llm/vertex_provider.py`, `llm/deepseek_provider.py`: cần bản gọi async (`google-genai` có `client.aio.models.generate_content(...)`, `openai` có `AsyncOpenAI`) — thêm method async cạnh method sync hiện có, không xoá bản sync (giữ tương thích cho script/test đơn giản không cần concurrency).
- `probing/prober.py`, `probing/menu_crawl.py`, module phân trang tổng quát mới: cũng cần async hoá vì đều gọi `fetcher.fetch()`.

**Alternative đã cân nhắc và loại**: giữ sync API, chấp nhận N browser process cho N-way fetch concurrency. Loại vì tốn tài nguyên không cần thiết khi mục tiêu là crawl hàng trăm-nghìn sản phẩm, và không giải quyết được việc thống nhất 1 mô hình concurrency cho cả fetch lẫn LLM (2 semaphore riêng biệt trong cùng 1 event loop đơn giản hơn quản lý thread pool + async LLM SDK riêng lẻ).

### 2. Producer/consumer qua `asyncio.Queue` cho checkpoint — không cần lock thủ công

Nhiều worker task (fetch+trích xuất 1 sản phẩm) chạy đồng thời sẽ hoàn thành **không theo thứ tự URL gốc**. Thay vì đếm số lượng hoàn thành bằng biến chia sẻ (cần lock, dễ race condition), dùng mô hình producer/consumer: mỗi worker task, sau khi crawl xong 1 sản phẩm, `put()` bản ghi vào 1 `asyncio.Queue` dùng chung. Có đúng 1 coroutine "writer" duy nhất `get()` từ queue, append vào danh sách kết quả trong bộ nhớ, và cứ mỗi `checkpoint_every` bản ghi mới thì gọi `write_records_to_excel` (bọc trong `asyncio.to_thread` vì `openpyxl.save()` là I/O chặn đồng bộ, không được gọi trực tiếp trong event loop). Vì chỉ có 1 coroutine chạm vào danh sách kết quả và bộ đếm, không cần lock tường minh — đúng tinh thần single-threaded của asyncio giữa các điểm `await`.

### 3. Batch response là JSON object khoá theo ID rõ ràng, không phải array theo vị trí

Rủi ro thực tế đã nêu trong explore: nếu prompt yêu cầu trả về JSON **array**, và model bỏ sót 1 phần tử ở giữa, các phần tử còn lại vẫn "khớp hình dạng array" về mặt cú pháp nhưng **bị lệch vị trí** — sản phẩm thứ 3 trong batch có thể vô tình nhận nhầm dữ liệu của sản phẩm thứ 2. Đây là lỗi âm thầm, không bị validate.py hiện tại (chỉ kiểm tra "là JSON hợp lệ") bắt được.

**Quyết định**: prompt batch yêu cầu trả về JSON **object**, khoá bằng chính URL (hoặc ID cục bộ gắn rõ trong prompt) của từng sản phẩm — `{"<url_hoặc_id>": {"tags": {...}, "ma_san_pham": "..."}, ...}`. Validate bước 1: mọi ID gửi đi phải xuất hiện đủ trong key của response; thiếu bất kỳ ID nào → coi cả batch là lỗi (không nhận phần đã đúng), theo đúng nguyên tắc "ưu tiên độ tin cậy" đã chốt — chấp nhận tốn thêm vài lệnh gọi lẻ cho các sản phẩm vốn đã đúng trong 1 batch bị coi là hỏng, đổi lại không bao giờ phải tin tưởng 1 phần kết quả từ 1 lệnh gọi đã biết có vấn đề.

### 4. Bậc thang xử lý batch — 3 tầng, không rơi tự do xuống lỗi

```
gọi batch (3-5 sp) → JSON object đủ ID, mỗi item hợp lệ?
    CÓ  → nhận toàn bộ, xong
    KHÔNG → retry NGUYÊN batch đó (tối đa 2 lần, có backoff ngắn)
              vẫn KHÔNG → rã batch, gọi RIÊNG TỪNG sản phẩm
                            (dùng lại extract_tags_from_html hiện có, tầng 2 cũ)
```
Tầng cuối chính là code hiện tại của change trước — không viết mới, tái sử dụng nguyên vẹn. Vì vậy thiết kế này **không có kịch bản nào chậm hơn hiện trạng**, chỉ có thể nhanh hơn khi batch thành công.

### 5. Site-wide product discovery: 2 nhánh theo `ProbeResult.strategy`, tận dụng site-probing đã có

- `strategy == "sitemap"`: dùng thẳng `probe.product_urls` (đã có sẵn, miễn phí — TLC đã kiểm chứng 559 URL trải khắp mọi dòng sản phẩm). Không lọc trước các URL "khả nghi không phải sản phẩm" (vd `/shop/` archive root từng thấy lẫn trong sitemap) — để nguyên, dựa vào cơ chế `missing_required_fields`/`CrawlStatus.PARTIAL_MISSING_FIELDS` đã có sẵn từ change trước tự động gắn cờ các URL không phải sản phẩm thật khi crawl thử, thay vì tốn thêm 1 lượt fetch chỉ để lọc trước (lọc trước sẽ triệt tiêu chính lợi thế "miễn phí" của nhánh này).
- `strategy == "menu_crawl"`: với mỗi `listing_url` đã xác nhận là lưới thật (từ site-probing), chạy bậc thang phân trang tổng quát (module mới `probing/generic_pagination.py`):
  1. Tìm `<link rel="next">`/`<a rel="next">` trong trang.
  2. Không có → thử lần lượt các pattern URL phổ biến (`?page=N+1`, `?paged=N+1`, `/page/N+1/`, `/trang-N+1`), so sánh **tập URL sản phẩm thu được** với trang trước (không dựa vào mã lỗi HTTP vì nhiều site trả 200 cho trang "ảo" không tồn tại) — trùng lặp hoàn toàn thì coi là hết trang.
  3. Không pattern nào cho kết quả mới → tìm nút "Xem thêm"/"Load more" (selector suy đoán theo text phổ biến: "xem thêm", "load more", "hiển thị thêm"), dùng `click_selectors`/`wait_selector` đã có sẵn trong `StealthFetcher`, click lặp tới khi không sinh sản phẩm mới.
  4. Không có gì trong 3 bước trên → coi danh mục chỉ có 1 trang, **không phải lỗi**.
  
  Bước 3 (click) bắt buộc tuần tự trong nội bộ 1 `listing_url` (mỗi click phụ thuộc DOM sau click trước). Nhiều `listing_url` khác nhau của cùng 1 site vẫn là các task độc lập, chạy đồng thời với nhau dưới cùng giới hạn fetch-concurrency chung.

  **Cần bổ sung nhỏ vào `probing/detection.py`**: `analyze_page` hiện chỉ trả `card_link_count` (số lượng), không trả tập href thật. Cần thêm 1 field `card_links: set[str]` vào `PageSignals` để module phân trang có dữ liệu thật để so sánh/gộp URL sản phẩm giữa các trang, không phải đếm lại.

### 6. 2 giới hạn concurrency độc lập: fetch và LLM

- `FETCH_CONCURRENCY` (mặc định thấp, ví dụ 8): giới hạn số page Playwright fetch đồng thời — tránh dồn quá nhiều request vào 1 site trong thời gian ngắn (rủi ro WAF chặn IP, TLC đã từng trả 406 với UA đơn giản).
- `LLM_BATCH_CONCURRENCY` (mặc định thấp, ví dụ 5): giới hạn số lệnh gọi batch LLM đồng thời — vì chưa biết rate limit chính xác của Vertex AI theo tài khoản người dùng, bắt đầu bảo thủ, có thể tăng dần sau khi quan sát thực tế không bị lỗi 429.

2 giới hạn này độc lập vì fetch bị giới hạn bởi "site đối thủ chịu được bao nhiêu tải", còn LLM bị giới hạn bởi "quota nhà cung cấp" — không liên quan nhau, gộp chung 1 giới hạn sẽ vô tình bó hẹp cái này theo cái kia.

### 7. Phân biệt lỗi "vượt quota/rate limit" (retry cùng provider) với lỗi khác (fallback provider ngay)

`vertex_provider.py`/`deepseek_provider.py` hiện bắt mọi `Exception` và bọc đồng nhất thành `LLMProviderError`, không phân biệt được lỗi tạm thời (429/quota — nên retry lại chính provider đó sau vài giây) với lỗi không thể phục hồi (auth sai, model không tồn tại — nên chuyển provider ngay). Khi có concurrency, nhiều lệnh gọi cùng lúc gặp 429 sẽ đồng loạt đổ dồn sang DeepSeek nếu không phân biệt, làm mất lợi ích "Vertex AI là chính" một cách không cần thiết.

**Quyết định**: thêm nhận diện lỗi quota/rate-limit (dựa vào mã lỗi HTTP 429 hoặc thông điệp lỗi đặc trưng của từng SDK) ngay trong provider, áp dụng backoff ngắn + retry (2-3 lần) với chính provider đó trước khi coi là thất bại và ném `LLMProviderError` lên cho `FallbackLLMProvider` chuyển sang DeepSeek.

## Risks / Trade-offs

- **[Risk]** Rewrite sang async lan ra nhiều file hơn ước tính ban đầu (không chỉ fetch, mà cả 2 LLM provider + toàn bộ probing) → khối lượng thay đổi lớn hơn 1 thay đổi "chỉ tối ưu tốc độ" thông thường.
  **Mitigation**: giữ nguyên các hàm sync hiện có (không xoá), chỉ thêm bản async song song — giảm rủi ro phá vỡ test/script hiện có, cho phép rollback từng phần nếu 1 nhánh async có vấn đề.

- **[Risk]** Batch nhiều sản phẩm có thể khiến prompt dài hơn, độ trễ mỗi lệnh gọi tăng theo, làm giảm bớt lợi ích của batching so với ước tính (18.5s hiện tại đo được là cho 1 sản phẩm/lệnh, chưa có số liệu thật cho batch 3-5).
  **Mitigation**: batch size nhỏ (3-5, theo đúng quyết định ưu tiên độ tin cậy) hạn chế mức tăng độ dài prompt; cần đo lại thực tế sau khi cài đặt để xác nhận batching vẫn có lợi ròng, không phải giả định suông.

- **[Risk]** Tăng concurrency fetch có thể khiến site đối thủ phát hiện pattern bất thường (nhiều request từ 1 IP trong thời gian ngắn) và chặn nặng hơn 406 đơn giản (vd chặn IP hẳn, hoặc captcha).
  **Mitigation**: mặc định `FETCH_CONCURRENCY` thấp (8), cấu hình được qua `.env` giống các tham số khác, để dễ giảm xuống nếu gặp dấu hiệu bị chặn khi chạy thật.

- **[Risk]** Chưa biết rate limit thật của Vertex AI theo tài khoản người dùng — số `LLM_BATCH_CONCURRENCY` mặc định là suy đoán, không phải số đã kiểm chứng.
  **Mitigation**: cơ chế backoff+fallback DeepSeek (Decision 7) là lưới an toàn — dù đoán sai số concurrency, hệ thống không crash, chỉ chậm lại hoặc chuyển provider.

- **[Trade-off]** Bậc thang batch "any lỗi → rã toàn bộ batch gọi lẻ" (Decision 3/4) có thể lãng phí vài lệnh gọi cho các sản phẩm vốn dĩ đã đúng trong 1 batch bị coi là hỏng — đổi lại loại bỏ hoàn toàn rủi ro lệch dữ liệu âm thầm. Đây là đánh đổi có chủ đích theo đúng ưu tiên "độ tin cậy hơn thông lượng" người dùng đã chọn.

## Migration Plan

1. **Pha 1**: thêm hạ tầng async (fetch, LLM provider async, batch prompt/validate) **song song** với code sync hiện có — không xoá code cũ, để dataset TLC hiện tại (129 sản phẩm) và mọi test hiện có (27 test) tiếp tục chạy được nguyên vẹn trong lúc phát triển.
2. **Pha 2**: viết `probing/generic_pagination.py`, bổ sung `card_links` vào `PageSignals`.
3. **Pha 3**: viết entry point mới scope toàn site (thay `scripts/crawl_tlc_downlight.py`), chạy thử trên chính TLC (559 sản phẩm, đã có sitemap đáng tin — không cần đụng tới nhánh phân trang tổng quát để kiểm chứng phần concurrency+batch trước).
4. **Pha 4**: kiểm chứng nhánh phân trang tổng quát trên 1 site có `strategy=menu_crawl` thật (ứng viên: Roman, đã khảo sát kỹ ở phiên explore trước) khi tới lúc mở rộng sang site đó.

Rollback: xoá/không dùng entry point mới, dataset và script cũ (`crawl_tlc_downlight.py`) vẫn nguyên vẹn vì không bị sửa/xoá.

## Open Questions

- Con số `FETCH_CONCURRENCY`/`LLM_BATCH_CONCURRENCY` mặc định (8/5 nêu trên) là ước lượng khởi điểm, cần tinh chỉnh sau khi chạy thật trên toàn bộ 559 sản phẩm TLC và quan sát tỷ lệ lỗi/429.
- Chưa xác nhận Roman (hoặc site `menu_crawl` khác) có nút "Xem thêm"/pattern URL nào thực tế khớp bậc thang phân trang đã thiết kế hay không — thiết kế dựa trên suy luận tổng quát từ các nền tảng phổ biến, chưa kiểm chứng trên 1 site `menu_crawl` cụ thể (sẽ kiểm chứng ở Pha 4).
