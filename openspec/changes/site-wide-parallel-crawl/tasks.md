## 1. Cấu hình & phụ thuộc

- [ ] 1.1 Thêm biến cấu hình mới vào `src/crawler/config.py`/`.env.example`: `FETCH_CONCURRENCY` (mặc định 8), `LLM_BATCH_CONCURRENCY` (mặc định 5), `LLM_BATCH_SIZE` (mặc định 4, trong khoảng 3-5), `CHECKPOINT_EVERY`
- [ ] 1.2 Xác nhận `google-genai` và `openai` (đã cài trong dự án) hỗ trợ client async (`client.aio.*`, `AsyncOpenAI`) đúng version đang dùng

## 2. Fetch layer: chuyển sang Playwright async API

- [ ] 2.1 Viết `StealthFetcher` bản async (`async_playwright`, `async def fetch(...)`) song song với bản sync hiện có (không xoá bản sync) trong `src/crawler/fetch/stealth_fetch.py`
- [ ] 2.2 Giữ nguyên hành vi hiện có khi chuyển sang async: retry khi gặp mã lỗi chặn bot cơ bản (406/403/429), click_selectors/wait_selector cho nội dung render bằng JS
- [ ] 2.3 Viết test xác nhận nhiều `fetch()` async gọi đồng thời trên cùng 1 browser instance không lỗi (dùng fixture nội bộ hoặc site thật nhẹ)

## 3. LLM provider: bản async + phân biệt lỗi tạm thời

- [ ] 3.1 Thêm method async cho `VertexAIProvider`/`DeepSeekProvider`/`FallbackLLMProvider` (interface `LLMProvider` bổ sung `generate_json_async`, giữ nguyên `generate_json` sync)
- [ ] 3.2 Cài đặt nhận diện lỗi quota/rate-limit (429 hoặc thông điệp đặc trưng SDK) tách biệt với lỗi khác trong từng provider
- [ ] 3.3 Cài đặt backoff + retry (2-3 lần) với chính provider khi gặp lỗi quota/rate-limit, trước khi coi là thất bại và để `FallbackLLMProvider` chuyển provider dự phòng
- [ ] 3.4 Viết test cho logic phân biệt lỗi tạm thời vs lỗi vĩnh viễn bằng provider giả lập (tương tự `test_llm_fallback.py` đã có)

## 4. Batch prompt & validate

- [ ] 4.1 Thiết kế prompt batch: nhận N sản phẩm (mỗi sản phẩm có ID tường minh - dùng URL), yêu cầu trả JSON object khoá theo đúng ID đó, KHÔNG dùng JSON array
- [ ] 4.2 Cập nhật `EXTRACTION_JSON_SCHEMA` (hoặc thêm schema mới) phản ánh hình dạng object-khoá-theo-ID cho batch
- [ ] 4.3 Cài đặt validate batch: kiểm tra đủ mọi ID đã gửi có mặt trong response, mỗi item hợp lệ theo đúng luật hiện có (`validate.py`); thiếu bất kỳ ID nào hoặc có item không hợp lệ → coi cả batch thất bại, không nhận một phần
- [ ] 4.4 Viết test cho validate batch: batch đủ & hợp lệ (pass), batch thiếu 1 ID (fail toàn bộ), batch có ID lạ không gửi (bỏ qua/fail tuỳ thiết kế - quyết định rõ trong code)

## 5. Bậc thang xử lý batch

- [ ] 5.1 Cài đặt hàm xử lý 1 batch: gọi batch → validate → nếu lỗi thì retry nguyên batch tối đa 2 lần → nếu vẫn lỗi thì rã batch, gọi lại `extract_tags_from_html` (tầng 2 hiện có) riêng cho từng sản phẩm trong batch đó
- [ ] 5.2 Viết test xác nhận: batch thành công ngay lần đầu trả đúng kết quả; batch lỗi rồi retry thành công trả đúng kết quả; batch lỗi cả 3 lần rồi rã lẻ vẫn trả đúng kết quả cho từng sản phẩm (dùng provider giả lập kiểm soát được kịch bản lỗi)

## 6. Orchestration: producer/consumer + checkpoint

- [ ] 6.1 Viết lại `crawl_product_urls` thành coroutine: N worker task (giới hạn bởi `FETCH_CONCURRENCY`) fetch + tầng 1/1.5, gom sản phẩm sẵn sàng thành batch (`LLM_BATCH_SIZE`), M batch chạy đồng thời (giới hạn bởi `LLM_BATCH_CONCURRENCY`) qua bậc thang ở mục 5
- [ ] 6.2 Cài đặt `asyncio.Queue` nhận bản ghi đã hoàn thành từ mọi worker, 1 coroutine "writer" duy nhất tiêu thụ queue, append vào danh sách kết quả, và checkpoint (`write_records_to_excel` bọc `asyncio.to_thread`) mỗi `CHECKPOINT_EVERY` bản ghi mới
- [ ] 6.3 Giữ nguyên hành vi crawl-lại-có-chọn-lọc: bản ghi đã `CrawlStatus.OK` từ file Excel cũ (`load_existing_records`) được tái sử dụng, không đưa vào hàng đợi crawl lại
- [ ] 6.4 Viết test xác nhận checkpoint ghi đúng số lượng dù thứ tự hoàn thành xáo trộn (mô phỏng bằng worker giả có độ trễ khác nhau)

## 7. Site-wide product discovery

- [ ] 7.1 Thêm field `card_links: set[str]` vào `PageSignals` trong `src/crawler/probing/detection.py` (hiện chỉ có `card_link_count`), giữ nguyên các field/hành vi khác
- [ ] 7.2 Viết `src/crawler/probing/generic_pagination.py`: hàm liệt kê URL sản phẩm của 1 `listing_url` theo bậc thang rel=next → thử pattern URL (`?page=N`, `?paged=N`, `/page/N/`, `/trang-N`) có so sánh tập `card_links` giữa các trang để phát hiện hết trang → click "Xem thêm"/"Load more" (selector suy đoán theo text phổ biến) tuần tự → fallback 1 trang duy nhất
- [ ] 7.3 Viết hàm site-wide: nếu `ProbeResult.strategy == "sitemap"` → dùng thẳng `probe.product_urls`; nếu `"menu_crawl"` → chạy `generic_pagination` đồng thời cho từng `listing_url`, gộp + loại trùng kết quả
- [ ] 7.4 Viết test cho `generic_pagination` bằng fixture HTML giả lập (rel=next, pattern URL, nút load-more, không có gì) - không phụ thuộc site thật để test ổn định
- [ ] 7.5 Đánh dấu `src/crawler/sites/tlc.py` (`discover_category_product_urls`) là không dùng cho mục tiêu site-wide nữa (giữ file cho tham khảo/pilot cũ, không xoá vì `scripts/crawl_tlc_downlight.py` cũ vẫn phụ thuộc)

## 8. Entry point mới

- [ ] 8.1 Viết `scripts/crawl_site.py` (hoặc tên tương đương) nhận domain làm tham số, generic không hard-code TLC: chạy site-probing → site-wide discovery (mục 7) → pipeline song song+batch (mục 6) → xuất `output/<domain>.xlsx`
- [ ] 8.2 Áp dụng đúng khuôn field/quy tắc Giá tri-state/category passthrough đã chốt ở change `competitor-product-crawler` (không đổi schema đầu ra)

## 9. Kiểm chứng thật trên TLC (559 sản phẩm toàn site)

- [ ] 9.1 Chạy `scripts/crawl_site.py` thật trên `tlclighting.com.vn` (nhánh `strategy=sitemap`, không cần đụng tới `generic_pagination` để kiểm chứng riêng phần concurrency+batch trước)
- [ ] 9.2 Đo thời gian chạy thật, so sánh với baseline 21s/sản phẩm tuần tự đã đo ở change trước; xác nhận không tệ hơn baseline ở trường hợp xấu nhất (mọi batch đều fail, mọi thứ rã lẻ)
- [ ] 9.3 Xác nhận 129 sản phẩm category "Đèn LED âm trần" đã có trong `output/tlclighting.xlsx` (từ change trước) được tái sử dụng qua cơ chế crawl-lại-có-chọn-lọc, không bị crawl lại từ đầu
- [ ] 9.4 Review thủ công 1 mẫu bản ghi thuộc dòng sản phẩm KHÁC (vd đèn pha, đèn tuýp - không phải âm trần) để xác nhận site-wide discovery + pipeline hoạt động đúng ngoài phạm vi category đã kiểm chứng trước đó
- [ ] 9.5 Quan sát tỷ lệ lỗi 429/quota thực tế trong log, điều chỉnh `LLM_BATCH_CONCURRENCY` mặc định nếu cần

## 10. Kiểm chứng phân trang tổng quát (khi có site menu_crawl thật)

- [ ] 10.1 Chạy site-probing thật trên 1 site rơi vào nhánh `menu_crawl` (ứng viên: roman.vn, đã khảo sát ở phiên explore trước change `competitor-product-crawler`)
- [ ] 10.2 Xác nhận `generic_pagination` liệt kê được số lượng URL sản phẩm hợp lý cho ít nhất 1 `listing_url` thật, đối chiếu thủ công với số lượng hiển thị trên site
- [ ] 10.3 Nếu bậc thang phân trang không khớp thực tế của site đó (site dùng cơ chế phân trang khác chưa lường trước) → quay lại design.md cập nhật quyết định, không ép code cho khớp bằng hard-code riêng cho site đó
