## Context

Dự án hiện trống (chưa có code). Mục tiêu là crawl dữ liệu sản phẩm từ nhiều website đối thủ ngành đèn LED, mỗi site một nền tảng kỹ thuật khác nhau. Đã khảo sát trực tiếp 3 site đại diện cho 3 kiểu kiến trúc khác nhau, dùng làm cơ sở cho các quyết định thiết kế dưới đây:

| | TLC (tlclighting.com.vn) | Roman (roman.vn) | KingLED (kingled.com.vn) |
|---|---|---|---|
| Nền tảng | WordPress + WooCommerce + Yoast | ASP.NET WebForms tự viết | CMS tự viết riêng |
| Structured data | JSON-LD `Product` đầy đủ | Không có | Microdata `Product` đầy đủ |
| Bảng thông số kỹ thuật | HTML nhưng label/value gộp lộn xộn trong 1 `<td>` | `<table>` sạch, chuẩn | Rỗng trong HTML tĩnh — chỉ có sau khi JS chạy |
| Nguồn danh sách URL SP | `product-sitemap.xml` tự động, mới nhất | `sitemap.xml` tĩnh, lastmod 2021, thiếu sản phẩm hiện tại | Sitemap động chia theo content-type (`?page=Product`), mới nhất |
| Bẫy cấu trúc site | Không | Trang danh mục cấp cha là landing rỗng, danh mục con mới là lưới SP thật | Không |
| Chặn/giới hạn | WAF trả 406 với User-Agent quá đơn giản | Không thấy | Không thấy |

Kết luận rút ra: không có 2 site nào giống nhau ở bất kỳ khâu nào (nền tảng, cú pháp structured data, độ sạch specs, độ tin cậy sitemap, cần JS hay không). Một pipeline "1 site 1 config" sẽ không scale. Cần một pipeline nhiều tầng, mỗi tầng cố gắng lấy dữ liệu theo cách tổng quát trước, chỉ rơi xuống tầng tốn kém hơn (LLM) khi các tầng rẻ hơn không đủ.

## Goals / Non-Goals

**Goals:**
- Crawl đúng và đầy đủ dữ liệu sản phẩm theo schema chuẩn cho 1 site đối thủ (TLC, category "Đèn LED âm trần") mà không viết selector cứng riêng cho từng field/từng site.
- Pipeline phải tổng quát hoá được sang site khác (Roman, KingLED) ở các change sau mà không cần thiết kế lại kiến trúc cốt lõi — chỉ cần thêm kết quả probe + fallback selector tối thiểu cho site mới.
- Chi phí LLM cho mỗi category ~100-200 sản phẩm ở mức không đáng kể (đã ước tính dưới $1 với DeepSeek khi có làm sạch HTML).

**Non-Goals:**
- Chuẩn hoá category về 1 taxonomy chung giữa các site đối thủ (quyết định giữ nguyên category gốc từng site).
- Phân tích, so sánh, hoặc matching sản phẩm chéo site — phạm vi hiện tại chỉ dừng ở crawl.
- Tự động phát hiện toàn bộ site đối thủ mới (site probing chỉ áp dụng khi đã biết domain, không phải discovery engine tìm đối thủ).
- Giải mọi loại CAPTCHA/thử thách chống bot nâng cao (cloakBrowser xử lý fingerprinting cơ bản, không phải giải CAPTCHA có người).

## Decisions

### 1. Pipeline trích xuất nhiều tầng, không dùng LLM cho toàn bộ trang

Thứ tự: **Tầng 0 (site probing)** → **Tầng 1 (structured data)** → **Tầng 1.5 (CSS fallback nhẹ)** → **Tầng 2 (LLM normalization)**.

Lý do: structured data (khi có) chính xác và miễn phí hơn LLM nhiều lần; nhưng không site nào có đủ 100% field cần thiết qua structured data (TLC thiếu specs sạch, Roman không có gì, KingLED thiếu specs). Dùng LLM cho toàn bộ HTML mỗi trang sẽ tốn hơn không cần thiết (HTML thô 1 trang TLC ~200KB, nếu không lọc trước sẽ tốn ~15.000 token/trang thay vì ~2.000 token nếu chỉ đưa phần liên quan). Alternative đã cân nhắc: LLM-only cho mọi field — bị loại vì tốn kém hơn và kém tin cậy hơn với field có structured data sẵn (giá, tên, ảnh không cần LLM đoán).

### 2. Structured-data parser tổng quát (JSON-LD + Microdata + RDFa + OpenGraph)

Không hard-code theo JSON-LD (như ban đầu nghĩ khi mới xem TLC) vì KingLED dùng thuần Microdata — nếu chỉ regex tìm `application/ld+json` sẽ bỏ sót hoàn toàn site này. Dùng 1 thư viện parser schema.org tổng quát (kiểu `extruct`) đọc được cả 3 cú pháp, cộng thêm fallback đọc OpenGraph/meta tags khi không có schema.org nào (fallback yếu nhất, ít field nhất).

### 3. cloakBrowser làm lớp fetch/render duy nhất

Alternative đã cân nhắc: dùng `requests`/`curl` thuần, chỉ dùng browser thật khi bị chặn. Bị loại vì phát hiện KingLED **không hề chặn bot** nhưng vẫn cần browser thật (phần "Thông số kỹ thuật" chỉ render sau khi JS chạy, HTML tĩnh rỗng) — nghĩa là "cần browser" không tương đương "bị chặn bot", không thể chỉ bật browser khi phát hiện chặn. Dùng cloakBrowser làm mặc định cho mọi site tránh phải phân loại "site này có cần JS không" thủ công, đổi lại chi phí/độ trễ mỗi request cao hơn HTTP thuần — chấp nhận được vì khối lượng crawl (hàng trăm sản phẩm/category) không lớn.

### 4. Site probing cache theo domain, không phải config crawl đầy đủ

Với mỗi domain mới: đọc `robots.txt` tìm `Sitemap:`, thử các path quy ước (`/sitemap.xml`, `/sitemap_index.xml`, `/product-sitemap.xml`...). **Độ tin cậy của sitemap được tính bằng tỷ lệ URL khớp**: lấy mẫu ngẫu nhiên N URL trong sitemap, fetch và chạy qua chính bộ tín hiệu "phát hiện trang sản phẩm thật" (mật độ giá, structured-data Product, v.v. — dùng lại từ bộ phát hiện lưới sản phẩm bên dưới) để xác nhận URL đó có đúng là trang sản phẩm còn tồn tại hay không; tỷ lệ khớp ≥ 80% thì coi sitemap đáng tin cậy (ngưỡng có thể tinh chỉnh sau khi có dữ liệu thực tế từ nhiều site hơn). Không dùng `lastmod` làm tiêu chí chính (dù có thể log tham khảo) vì `lastmod` chỉ là do site tự khai báo, không phản ánh trực tiếp việc URL có còn đúng/còn tồn tại không — case Roman cho thấy 1 sitemap có thể HTTP 200 bình thường nhưng vẫn thiếu sản phẩm thật.

Nếu qua ngưỡng tin cậy → dùng sitemap làm nguồn URL sản phẩm chính (case TLC, KingLED). Nếu không → crawl theo menu/breadcrumb, và mỗi trang danh mục ứng viên phải qua **bộ phát hiện "lưới sản phẩm thật"** (tín hiệu: mật độ xuất hiện của từ giá, số khối lặp lại ảnh+tên+giá, số Product structured-data trên trang, có control phân trang) trước khi được coi là nguồn sản phẩm hợp lệ (case Roman — tránh crawl nhầm trang landing rỗng). Kết quả probe (nguồn URL, có cần browser hay không, CSS fallback nếu cần) cache lại theo domain — đây là phần "cấu hình" duy nhất per-site, nhẹ hơn nhiều so với việc viết full scraping config.

### 5. LLM provider: Vertex AI (Gemini 2.5 Flash) chính, DeepSeek fallback

Vertex AI với model **Gemini 2.5 Flash** được ưu tiên vì đã có quota/API key sẵn sàng sử dụng, và Flash là mức chi phí/tốc độ phù hợp cho tác vụ trích xuất hàng loạt (không cần model suy luận mạnh nhất). DeepSeek (đã kiểm chứng giá: v4-flash ~$0.14/1M input cache-miss, $0.28/1M output) làm fallback khi Vertex AI hết quota hoặc lỗi. Cần 1 interface LLM provider chung (prompt + schema JSON output giống nhau cho cả 2 provider) để chuyển đổi không ảnh hưởng logic nghiệp vụ — tầng 2 gọi qua interface này, không biết đang dùng provider nào.

### 6. Schema bản ghi sản phẩm

Theo khuôn cột `product_Metadata (1).xlsx` (sheet "2. LED Downlight"), điều chỉnh:
- Bỏ `Giá đối chiếu`.
- `Mã SAP`, `Link mua hàng online`, `Link file HDSD`: optional, NULL khi site không có tương đương (không coi là lỗi crawl).
- `Giá`: 3 trạng thái — số tiền cụ thể, literal string `"Liên hệ"` (site xác nhận không công khai giá), hoặc NULL (chưa crawl được/lỗi — cần phân biệt với "Liên hệ").
- `category 1/2/3`: lấy nguyên breadcrumb gốc của site đối thủ, số cấp có thể khác nhau giữa các site (đã thấy 2-5 cấp), không ép về taxonomy chung.
- `Tags`: JSON attribute do tầng 2 LLM sinh ra, schema thuộc tính (tên field) linh hoạt theo từng site/category — không ép cố định theo 4 field mẫu của rangdong.
- Mỗi bản ghi có thêm field trạng thái crawl nội bộ (vd `ok` / `error` / `partial-missing-fields`, không nằm trong khuôn cột xuất ra file Excel) để phục vụ việc crawl lại có chọn lọc (xem mục 7).

### 7. Output: 1 file Excel riêng cho mỗi site, mô phỏng cấu trúc `product_Metadata (1).xlsx`

Mỗi site đối thủ crawl ra 1 file `.xlsx` riêng, cột đặt tên và thứ tự cố gắng bám sát sheet "2. LED Downlight" gốc (trừ các điều chỉnh đã chốt ở mục 6) để dễ đối chiếu bằng mắt và dễ nhập lại vào hệ thống hiện có. Không gộp nhiều site vào 1 file — tránh nhầm lẫn nguồn khi review, và cho phép chạy/re-run từng site độc lập.

### 8. Crawl 1 lần duy nhất, chỉ crawl lại bản ghi lỗi/thiếu

Không có lịch crawl định kỳ trong phạm vi change này. Sau khi crawl 1 lần, các bản ghi có trạng thái `error` hoặc `partial-missing-fields` (mục 6) là ứng viên để chạy lại — chỉ re-crawl đúng các URL đó, không chạy lại toàn bộ category. Hệ quả: không cần thiết kế versioning/lịch sử giá theo thời gian ở change này (khác với 1 hệ thống theo dõi giá định kỳ).

## Risks / Trade-offs

- **[Risk]** Sitemap trông "có vẻ ổn" nhưng thực chất cũ/thiếu sản phẩm (case Roman: có sitemap, HTTP 200, nhưng thiếu sản phẩm đang bán) → im lặng bỏ sót dữ liệu mà không báo lỗi.
  **Mitigation**: chấm điểm độ tin cậy sitemap bằng `lastmod` + đối chiếu nhanh 1 mẫu URL từ menu-crawl xem có khớp không, thay vì tin tuyệt đối vào việc sitemap tồn tại.

- **[Risk]** Trang danh mục cấp cha là "bẫy" landing page rỗng (case Roman) → nếu bộ phát hiện lưới sản phẩm không đủ nhạy, crawler báo cáo "0 sản phẩm" hoặc tệ hơn là âm thầm bỏ qua.
  **Mitigation**: log/flag rõ ràng khi 1 trang danh mục được probe nhưng phát hiện 0 sản phẩm, để review thủ công thay vì coi là "category rỗng, bỏ qua".

- **[Risk]** cloakBrowser là dự án mã nguồn mở còn khá mới, các site có thể nâng cấp WAF khiến kỹ thuật ẩn danh hiện tại mất tác dụng.
  **Mitigation**: bọc lớp fetch sau 1 interface, có thể thay engine khác nếu cần mà không đổi logic tầng trên.

- **[Risk]** LLM (tầng 2) có thể tạo giá trị Tags sai/bịa (hallucination) do thông số tự do, đặc biệt khi trang nguồn thiếu field.
  **Mitigation**: ép output qua JSON schema/structured output của provider, validate range/đơn vị hợp lý trước khi lưu, đánh dấu bản ghi có field bất thường để review.

- **[Trade-off]** Dùng browser thật (cloakBrowser) cho mọi request kể cả site không cần (như TLC ở tầng fetch structured-data) → chậm và tốn tài nguyên hơn HTTP thuần, nhưng đổi lại không phải tự phân loại "site nào cần JS" thủ công (rủi ro bỏ sót như case KingLED).

## Migration Plan

Không có hệ thống cũ cần migrate (dự án mới). Rollout theo pha:
1. **Pha 1 (change này)**: build đủ 4 tầng pipeline + schema bản ghi, chạy end-to-end cho TLC/"Đèn LED âm trần", review thủ công 1 mẫu kết quả để xác nhận độ chính xác trước khi coi pipeline là ổn.
2. **Pha 2 (change sau, không thuộc phạm vi này)**: onboard Roman, KingLED và các site khác — chỉ cần chạy site-probing cho domain mới + bổ sung CSS fallback tối thiểu nếu tầng 1 không đủ, tái sử dụng toàn bộ tầng 1/1.5/2.

Rollback: dừng chạy crawler, không có tác động tới hệ thống khác vì output là dataset độc lập, không ghi đè dữ liệu sản xuất nào.

## Open Questions

Không còn câu hỏi mở tồn đọng — 4 điểm ở vòng review trước (model Vertex AI, nơi lưu output, tần suất crawl, ngưỡng độ tin cậy sitemap) đã được chốt và đưa vào mục Decisions (5, 7, 8, và 4).

Điểm cần theo dõi khi implement: ngưỡng 80% ở mục 4 là giá trị khởi điểm hợp lý dựa trên suy luận, chưa được kiểm chứng bằng dữ liệu thật từ nhiều site — có thể cần tinh chỉnh sau khi chạy probe trên vài site đầu tiên.
