# Pipeline crawl dữ liệu sản phẩm đối thủ

Tài liệu mô tả cách hệ thống lấy dữ liệu sản phẩm từ website đối thủ (ngành đèn
LED chiếu sáng) và xuất ra file Excel.

Vấn đề gốc: mỗi site đối thủ dùng một nền tảng khác nhau, không site nào giống
site nào ở bất kỳ khâu nào. Khảo sát 3 site thật cho thấy:

| | TLC | Roman | KingLED |
|---|---|---|---|
| Nền tảng | WordPress + WooCommerce | ASP.NET WebForms | CMS tự viết |
| Structured data | JSON-LD `Product` | **Không có gì** | Microdata `Product` |
| Bảng thông số | Lộn xộn, gộp trong 1 `<td>` | `<table>` sạch | **Không có `<table>` nào** — `<label>`/`<span>`, rỗng cho tới khi JS chạy |
| Sitemap | `product-sitemap.xml` mới | Cũ từ 2021, thiếu SP | Sitemap động theo content-type, **XML sai chuẩn** |
| Bẫy cấu trúc | Không | Danh mục cha là landing rỗng | 2 domain song song + khối "sản phẩm liên quan" dùng chung bố cục với thông số |
| Chặn bot | WAF trả 406 nếu UA đơn giản | Không | Không |

Vì vậy hệ thống **không** viết một bộ config riêng cho từng site. Thay vào đó
dùng pipeline nhiều tầng: tầng rẻ và tổng quát chạy trước, chỉ rơi xuống tầng
tốn kém hơn (LLM) cho phần dữ liệu mà tầng trước không lấy được.

---

## Tổng quan luồng chạy

```
                    ┌─────────────────────────────────────┐
                    │  Tầng 0: SITE PROBING               │
                    │  (chạy 1 lần cho mỗi domain mới)    │
                    │  robots.txt → sitemap → chấm điểm   │
                    │  độ tin cậy → cache theo domain     │
                    └──────────────┬──────────────────────┘
                                   │ danh sách URL sản phẩm
                                   ▼
                    ┌─────────────────────────────────────┐
                    │  LỚP FETCH (stealth-fetch)          │
                    │  cloakBrowser/Chromium — dùng chung │
                    │  cho mọi tầng, có retry chống bot   │
                    └──────────────┬──────────────────────┘
                                   │ HTML đã render
                                   ▼
   ┌───────────────────────────────────────────────────────────────┐
   │  Với MỖI URL sản phẩm:                                        │
   │                                                               │
   │   Tầng 1  ── structured data (JSON-LD/Microdata/RDFa/OG)      │
   │      │        → tên, giá, ảnh, breadcrumb, mã SP (nếu có)     │
   │      ▼                                                        │
   │   Tầng 1.5 ── CSS selector fallback theo domain               │
   │      │        → chỉ vá field còn thiếu sau tầng 1             │
   │      ▼                                                        │
   │   Tầng 1.6 ── mục "Ưu điểm" trong cụm mô tả                   │
   │      │        → tóm tắt (gạch đầu dòng) + toàn văn            │
   │      ▼                                                        │
   │   Tầng 2  ── LLM (Vertex AI → DeepSeek)                       │
   │               → Tags (JSON) từ bảng thông số kỹ thuật tự do   │
   └──────────────────────────┬────────────────────────────────────┘
                              │ ProductRecord
                              ▼
                    ┌─────────────────────────────────────┐
                    │  OUTPUT: 1 file .xlsx / 1 site      │
                    │  + trạng thái crawl nội bộ để       │
                    │    crawl lại có chọn lọc lần sau    │
                    └─────────────────────────────────────┘
```

---

## Tầng 0 — Site probing

**Mục đích:** tìm nguồn danh sách URL sản phẩm đáng tin cậy cho một domain mới.
Chạy **một lần** cho mỗi domain, kết quả được cache lại.

**Code:** `src/crawler/probing/`

### Các bước

1. **Đọc `robots.txt`** (`robots.py`) tìm chỉ thị `Sitemap:`.
2. **Thử các path quy ước** (`sitemap.py`) nếu robots.txt không khai báo:
   `/sitemap_index.xml`, `/sitemap.xml`, `/product-sitemap.xml`.
3. **Giải đệ quy sitemap index** thành danh sách URL phẳng. Nếu gặp sitemap
   index, **ưu tiên sub-sitemap có chữ "product" trong tên**, **trừ sitemap của
   taxonomy sản phẩm**. Đây là bài học thực tế từ TLC, phải học **hai lần**:
   - `sitemap_index.xml` gồm `post-sitemap.xml` + `page-sitemap.xml` +
     `product-sitemap.xml`, nếu gộp hết sẽ lẫn cả bài blog và trang tĩnh.
   - Nhưng lọc "có chữ product" thôi thì vẫn kéo theo `product_cat-sitemap.xml`
     — **73 trang danh mục** `/danh-muc/...` lọt vào danh sách "URL sản phẩm"
     (559 thay vì 486). Trang danh mục không có JSON-LD Product nên tốn lượt
     fetch + gọi LLM để rồi sinh ra bản ghi rỗng. Sau khi loại taxonomy:
     **486 URL = 485 sản phẩm + 1 trang `/shop/`**, độ tin cậy 100%.

   Bộ lọc taxonomy có **hai nhánh** vì hai site đặt tên hoàn toàn khác nhau:
   WooCommerce dùng tiền tố (`product_cat`, `product_tag`, `product_brand`…),
   còn CMS sinh sitemap động theo content-type thì dùng hậu tố Group/Category
   (KingLED: `sitemap.xml?page=ProductGroup` — **138 trang danh mục** — nằm
   ngay cạnh `sitemap.xml?page=Product` — 557 sản phẩm — trong cùng 1 index).

   > Với KingLED, việc lọc này **không sửa lại được ở bước sau**: URL sản phẩm
   > và URL danh mục đều phẳng (`https://kingled.com.vn/<slug>`), sản phẩm
   > `den-panel-hop-onyx-48w-60x60cm` nằm cạnh danh mục `am-tran-downlight`,
   > không có dấu hiệu nào trong URL để phân biệt. TLC thì lọc lại được bằng
   > `/san-pham/`. Nên với site kiểu này, **phân tách của sitemap là căn cứ duy
   > nhất**.

4. **Parse khoan dung với XML sai chuẩn.** Sitemap thật ngoài đời không phải
   lúc nào cũng hợp lệ: `kingled.com.vn/sitemap.xml?page=Product` nhúng URL ảnh
   có dấu `&` chưa escape (`...&refer=http___imgse...`), `ElementTree` báo
   "not well-formed" ngay ký tự đó và **vứt cả 557 sản phẩm**. Hậu quả không
   phải là báo lỗi mà là **âm thầm sai**: site tụt xuống nhánh menu-crawl và
   trả về 0 URL, trong khi sitemap của nó hoàn toàn đủ dữ liệu.

   Nên `_parse_sitemap_xml` thử `ElementTree` trước (nghiêm ngặt, rẻ), hỏng thì
   parse lại bằng parser `recover=True` của lxml. Cả hai nhánh đều phải kiểm
   tra **tag gốc** là `sitemapindex`/`urlset` — một trang HTML 200 hợp lệ (site
   trả về ở path sitemap không tồn tại) vẫn parse thành cây XML bình thường với
   tag gốc `html`, "parse được" không đồng nghĩa với "là sitemap".

5. **Chấm điểm độ tin cậy** (`prober.py`): lấy mẫu ngẫu nhiên N URL (mặc định
   10), fetch từng URL và chạy qua bộ phát hiện trang sản phẩm. Đạt **≥ 80%**
   thì sitemap được chấp nhận làm nguồn chính.
   `lastmod` **không** được dùng làm tiêu chí quyết định — đó là giá trị site tự
   khai báo, không đảm bảo URL còn hợp lệ (case Roman: sitemap trả HTTP 200
   bình thường nhưng thiếu hẳn sản phẩm đang bán).
6. **Fallback crawl menu** (`menu_crawl.py`) nếu không có sitemap đáng tin cậy:
   duyệt link trong menu điều hướng để tìm trang danh mục ứng viên, rồi lọc
   từng trang qua bộ phát hiện lưới sản phẩm.
7. **Cache kết quả** (`cache.py`) theo domain, TTL 30 ngày, lưu ở `.cache/probe/`.

### Bộ phát hiện trang sản phẩm (`detection.py`)

Đây là phần dùng chung ở 2 chỗ: chấm điểm sitemap (bước 4) và lọc trang danh mục
ứng viên (bước 5). Bộ này tính 4 tín hiệu trên HTML:

| Tín hiệu | Ý nghĩa |
|---|---|
| `price_amount_mentions` | Số lần xuất hiện **số tiền thật** (vd `339.900 đ`) |
| `product_structured_data_count` | Số block structured-data kiểu `Product` |
| `card_link_count` | Số thẻ `<a>` bọc `<img>` — tức số "card" sản phẩm |
| `has_pagination` | Có control phân trang hay không |

Từ đó suy ra 2 kết luận khác nhau:

- **`looks_like_single_product_page`** — dùng khi xác nhận 1 URL lẻ (mẫu từ
  sitemap) có phải trang sản phẩm không. Điều kiện: có structured-data `Product`
  **hoặc** có số tiền thật.

  > Quan trọng: phải bắt **số tiền** (`\d[\d.,]*\s*đ`) chứ không phải chữ "giá",
  > và phải đếm trên **text đã trích** chứ không phải HTML thô. Hai lý do, cả hai
  > đều đo được trên fixture thật:
  >
  > 1. Chữ "giá" xuất hiện ở menu/footer của gần như mọi trang tiếng Việt (kể cả
  >    bài blog tuyển dụng), nên đếm chữ "giá" thì một sitemap toàn blog vẫn
  >    được chấm 100% tin cậy — đúng lỗi đã gặp ở TLC lần chạy đầu.
  > 2. WooCommerce tách chữ số và ký hiệu tiền tệ ra 2 thẻ riêng
  >    (`<bdi>166.000<span>₫</span></bdi>`), nên regex chạy trên HTML thô đếm ra
  >    **0** cho chính trang sản phẩm TLC.
  >
  > Đã thử và **loại** marker "Liên hệ" khỏi công thức: nó xuất hiện ở footer của
  > mọi trang TLC (bài blog đếm được 5 lần, trang tĩnh 4 lần) nên thêm vào sẽ làm
  > cả 2 fixture "rác" pass trở lại.

- **`looks_like_product_listing`** — dùng khi phân loại 1 trang danh mục là lưới
  sản phẩm thật hay landing rỗng. Điều kiện: `card_link_count >= 30`.

  > Ngưỡng 30 là số thực nghiệm trên cặp trang thật của Roman: trang landing
  > "bẫy" `den-led-am-tran.html` chỉ có **17** card (toàn ảnh banner), trang lưới
  > thật `den-downlight-led.html` có **52**. Không dùng được pagination hay
  > structured-data để phân biệt vì **cả hai trang đều có** — Roman gắn nhầm một
  > JSON-LD `Product` lên chính trang landing, còn trang lưới thật thì lại
  > không có structured data nào cả.

---

## Lớp fetch (stealth-fetch)

**Code:** `src/crawler/fetch/stealth_fetch.py`

Mọi request lấy **nội dung trang** đều đi qua lớp này — không tầng nào được gọi
HTTP client thuần. Lớp này bọc cloakBrowser (một bản Chromium build riêng, nói
API Playwright chuẩn) sau một interface `fetch(url)` duy nhất.

Cấu hình qua `CLOAKBROWSER_EXECUTABLE_PATH`. Nếu để trống sẽ fallback về Chromium
mặc định của Playwright kèm cảnh báo — chạy được nhưng **không có khả năng chống
fingerprint**.

Ba việc lớp này lo:

1. **Fingerprint thật:** User-Agent Chrome đầy đủ, `Accept-Language: vi-VN`,
   locale `vi-VN`, viewport 1366×900. Cần thiết vì WAF của TLC trả **406** với
   User-Agent quá đơn giản.
2. **Chờ nội dung render bằng JS:** tham số `click_selectors` (bấm vào tab trước
   khi đọc HTML) và `wait_selector` (đợi selector xuất hiện). Cần cho case
   KingLED — khối "Thông số kỹ thuật" **có mặt nhưng rỗng** trong HTML tĩnh, chỉ
   được JS điền vào sau khi trang tải xong. Đo trên trang thật:
   `div.property` tồn tại ở cả hai bản, nhưng bản `requests` có **0 dòng** còn
   bản qua browser có **16 dòng**.

   Tùy chọn fetch là **dữ liệu theo domain** (`sites/registry.py`), truyền
   xuống qua `crawl_product_urls(..., fetch_options=...)` — pipeline không tự
   đoán site nào cần chờ gì, và site cần chờ cũng không phải viết code riêng.
3. **Retry khi bị chặn:** gặp HTTP 403/406/429 thì đợi rồi thử lại (mặc định 2
   lần) trước khi coi là fetch thất bại.

> **Ngoại lệ có chủ đích:** `robots.txt` và sitemap XML được lấy bằng `requests`
> thuần (`probing/robots.py`, `probing/sitemap.py`). Đây là tài nguyên máy đọc
> (text/XML), không phải nội dung trang cần render JS hay giả lập trình duyệt —
> dùng browser thật cho chúng chỉ tốn thời gian mà không được gì.

---

## Tầng 1 — Structured data

**Code:** `src/crawler/extraction/structured_data.py`

Đọc dữ liệu schema.org có sẵn trên trang. Đây là tầng **chính xác nhất và miễn
phí**, nên luôn chạy trước.

Thứ tự thử, dừng ở cú pháp đầu tiên tìm được `Product`:

1. **JSON-LD** — `<script type="application/ld+json">`
2. **Microdata** — `itemscope`/`itemprop`
3. **RDFa** — dùng chung code với Microdata, vì thư viện `extruct` trả về cùng
   một hình dạng node (`type`/`properties`) cho cả hai cú pháp
4. **OpenGraph/meta** — fallback yếu nhất, chỉ lấy được tên + ảnh + URL

Không hard-code theo JSON-LD, vì KingLED dùng thuần Microdata — chỉ regex tìm
`application/ld+json` sẽ bỏ sót hoàn toàn site này.

### Hai điểm xử lý đặc biệt

**Nhiều block JSON-LD trên cùng 1 trang.** Case TLC: trang có 2 block `ld+json`
riêng biệt — block core của WordPress chứa `BreadcrumbList` rỗng/gãy, block
Yoast SEO mới chứa `Product` + `BreadcrumbList` đầy đủ. Nếu gộp phẳng tất cả rồi
lấy match đầu tiên sẽ nhặt phải breadcrumb gãy. Vì vậy code **ưu tiên tìm
`Product` và `BreadcrumbList` trong cùng một `@graph`**.

**`sku` không phải lúc nào cũng là Mã sản phẩm.** TLC khai `sku=13178` — đó là ID
nội bộ WordPress, không phải mã sản phẩm người đọc được; mã thật
(`TLC-AECA-VB-10W`) nằm trong bảng thông số, phải để tầng 2 lấy. KingLED khai
`sku=DL-12SS-T140` thì đúng là mã thật. Quy tắc: `sku` chỉ được dùng làm
`Mã Sản Phẩm` nếu **có chứa chữ cái**; nếu thuần số thì cất vào `product_id`.

Field nào không lấy được thì **để null**, không suy diễn, không điền mặc định —
để tầng sau xử lý tiếp.

---

## Tầng 1.5 — CSS selector fallback

**Code:** `src/crawler/extraction/css_fallback.py`

Chỉ vá những field **còn thiếu** sau tầng 1. Đây **không** phải một bộ config
scraping đầy đủ cho cả trang — chỉ là vài selector tối thiểu đăng ký theo domain.

Ví dụ kinh điển là Roman: site không có structured data nào cả, nhưng giá lại nằm
ở một vị trí CSS ổn định. Lấy bằng selector rẻ hơn nhiều so với gọi LLM chỉ để
đọc một con số:

```python
DOMAIN_FALLBACK_RULES = {
    "roman.vn": [
        SelectorRule(field="gia", selector="div.price .val", is_price=True),
        SelectorRule(field="ma_san_pham", selector="div.code .val"),
    ],
}
```

Chỉ thêm entry khi đã khảo sát và xác nhận tầng 1 không đủ cho chính domain đó —
không đoán trước cho site chưa khảo sát.

Module này còn giữ hai registry cùng tinh thần "chỉ ghi domain đã khảo sát":

**`DOMAIN_SPEC_ROOT_SELECTORS` — khoanh vùng khối thông số.** Cần cho site không
dùng `<table>` (xem tầng 2 / `html_cleaner`).

**`DOMAIN_PLACEHOLDER_PRICES` — giá trị "chỗ trống" mà site dùng thay cho giá.**
KingLED trả `<meta itemprop="price" content="0">` cho sản phẩm không niêm yết
giá, và trang của chúng **không render khối giá nào cả**. Ba cách xử lý, chỉ một
cách đúng:

| Cách | Vấn đề |
|---|---|
| Ghi `0` vào cột Giá | Người đọc hiểu là **miễn phí** — sai hẳn ý của nguồn |
| Ép thành `"Liên hệ"` | **Tự đặt lời vào miệng site** — trang không hề nói vậy |
| Coi như **chưa phân giải** (`None`) | Đúng: tầng 1.5 được quyền đọc lại giá từ DOM; không có thì để trống và bản ghi tự rơi xuống `partial-missing-fields` để người review nhìn thấy |

Thứ tự này quan trọng: `apply_css_fallback` chỉ vá field **còn thiếu**, mà `0.0`
không phải giá trị thiếu — nên phải quy `0.0` về `None` **trước** khi vào tầng
1.5, nếu không selector đọc giá hiển thị sẽ không bao giờ được chạy.

> `normalize_price` cố tình **ném lỗi** thay vì đoán bừa khi gặp chuỗi lạ. Ở
> tầng 1.5 lỗi đó được bắt lại và bỏ qua field: một trang dị dạng không được
> phép giết cả đợt crawl vài trăm sản phẩm. Tinh thần "không đoán bừa" giữ
> nguyên — field vẫn để trống và bản ghi vẫn bị gắn cờ.

---

## Tầng 1.6 — Mục "Ưu điểm" trong cụm mô tả

**Code:** `src/crawler/extraction/advantages.py`

Điền 2 cột `Tóm tắt ưu điểm, tính năng` và `Nội dung Ưu điểm SP`. Đây là dữ liệu
**có thật** trên trang nhưng từng bị bỏ qua hoàn toàn — khác hẳn `Mã SAP` hay
`VD HDSD` (site thật sự không có gì tương đương).

Định dạng bám theo chính khuôn tham chiếu (`product_Metadata (1).xlsx`): mỗi
gạch đầu dòng một dòng ở cột tóm tắt, toàn văn mục ở cột nội dung.

### Tìm theo từ khoá là ngõ cụt — đây là bằng chứng

Cách hiển nhiên là tìm heading chứa chữ "ưu điểm". Cách đó **đã cài và đã bỏ**,
vì trên trang thật mục này gần như không bao giờ tự xưng tên:

| Trang thật | Tiêu đề mục ưu điểm |
|---|---|
| `tlc/…-am-tran-eyecare-10w` | "4. **Ưu điểm** của Âm Trần Eyecare…" ← ca duy nhất khớp từ khoá |
| `kingled/…` (phần lớn) | "Đặc điểm nổi bật" |
| `roman/plp102` | "Đặc điểm nổi bật của…" |
| `tlc/…-phich-cam-chiu-tai` | "Tại sao nên sử dụng phích cắm cái chịu tải" |
| `tlc/…-cob-mo-hong` | **không có tiêu đề nào cả** — chỉ một `<ul>` trần |

Ném cả trang cho LLM thì đọc được hết, nhưng đắt và chậm gấp nhiều lần cho một
việc mà cấu trúc HTML đã nói gần đủ. Nên tầng 1.6 làm ngược lại: **gom ứng viên
thật rộng bằng cấu trúc, rồi chấm điểm chọn một.**

### Ba nguồn ứng viên, một thang điểm

```
(1) heading có tiêu đề mang tín hiệu DƯƠNG   ── ưu điểm/đặc điểm/nổi bật/lợi ích/
                                                tại sao/vì sao/tính năng/ưu việt
(2) heading mà LLM chỉ tới (trường muc_uu_diem) ── "la bàn", xem bên dưới
(3) CỤM ĐỀ MỤC: dãy ≥2 heading anh em cùng cấp ── cứu ca không có tiêu đề
                                                             │
                          tất cả ứng viên ─────────────► chấm điểm ─► lấy cao nhất
```

Điểm: `+100` tiêu đề dương · `+60` được LLM trỏ tới · `+10 × min(số gạch đầu
dòng, 8)` · `+ độ dài text / 100`. Hai trường hợp **loại thẳng** trước khi chấm:
mục **rỗng** (chỉ có dòng tiêu đề) và tiêu đề mang **tín hiệu âm** (thông số /
ứng dụng / hướng dẫn / bảo hành / so sánh / sản phẩm tương tự…).

Ba site, ba hình dạng khác hẳn nhau, cùng một đoạn code:

| | Gạch đầu dòng là gì | Vào bằng nguồn nào |
|---|---|---|
| TLC | `<li>` với nhãn trong `<strong>` | (1) tiêu đề dương |
| KingLED | `<h3>` con (`1.1 Tiết kiệm điện năng`…) | (1) hoặc (3) tuỳ trang |
| Roman | `<h3>` con dưới "Đặc điểm nổi bật của…" | (1) |
| TLC COB | `<li>` không có tiêu đề nào phía trên | (3) cụm đề mục |

### Nhánh "cụm đề mục" — đánh đổi đã cân nhắc, không phải sơ suất

Nhánh (3) **suy đoán theo hình dạng**, không có tín hiệu nào xác nhận đó đúng là
mục ưu điểm. Nó là nhánh duy nhất cứu được các trang không đặt tiêu đề, nhưng
cũng là nhánh duy nhất có thể ghi nhầm dữ liệu vào đúng cột mang tên "Ưu điểm".
Ba lớp chặn đang có: **≥2 đề mục ngang cấp** theo sau, không đề mục nào mang tín
hiệu âm, và **tiêu đề mẹ** cao cấp hơn cũng không mang tín hiệu âm (cụm bắt đầu
từ đề mục con đầu tiên nên tín hiệu âm hay nằm ở tiêu đề mẹ — ca thật:
`kingled/den-led-op-tran-30w` vớ phải "Chiếu sáng văn phòng / Chiếu sáng nhà ở",
bản thân vô hại, nhưng mẹ chúng là "**Ứng dụng** của…").

Giá phải trả, **đo trên toàn bộ 360 ô đã điền của KingLED**: 3 ô vớ phải danh
sách phụ kiện (`Bộ nguồn / Thanh nhôm / Phụ kiện lắp ráp`, cùng một mục dùng
chung cho 3 dòng Đèn Led Dán) + 3 ô chỉ có một dòng vô nghĩa → **6/360 = 1,7%**.
Đổi lại độ phủ **+7,3 điểm** (58,3% → 65,6%).

> Con số 1,7% này là **chặn dưới**: nó dò bằng bộ từ khoá các dạng sai đã biết,
> không phải soi từng ô so với trang gốc. 10 ô lấy ngẫu nhiên soi tay thì cả 10
> đều đúng.
>
> **Đừng đo tỷ lệ sai trên mẫu chọn tay các ca khó.** Bản đầu tiên của tài liệu
> này ghi "~15% ô sai" — suy từ 20 trang được chọn riêng vì có hình dạng cụm.
> Mẫu thiên lệch thổi tỷ lệ lỗi lên gần **mười lần**.

Muốn tắt nhánh này: xoá đúng dòng `offer(heading, nodes, is_cluster=True)` trong
`extract_advantages`. Độ phủ tụt về mức tiêu đề-dương thuần.

### KingLED không phải ngoại lệ

Độ phủ của KingLED thấp hơn hẳn TLC nên câu hỏi tự nhiên là "có phải riêng site
này bố cục dị không?". Đo mẫu ngẫu nhiên trên cả 3 site (giai đoạn **trước** khi
bật nhánh cụm):

| Site | Mẫu tìm được mục | Ghi chú |
|---|---:|---|
| TLC | 10/10 | gần như trang nào cũng có tiêu đề đàng hoàng |
| Roman | 4/7 | **cả 3 ca trượt đều có nội dung thật**, ở dạng cụm không tiêu đề |
| KingLED | 58–60% toàn site | phần trượt phần lớn là phụ kiện / hàng công nghiệp |

Kết luận: hình dạng "cụm đề mục không tiêu đề" xuất hiện ở **cả ba** site, không
phải nét riêng của KingLED — đó là lý do nhánh (3) được bật thay vì bị coi là
cách chữa cháy cho một site. Phần độ phủ còn thiếu của KingLED chủ yếu là các
sản phẩm **thật sự không có mục ưu điểm** trên trang (phụ kiện: thanh ray, khớp
nối, bộ nguồn), tức để trống mới đúng.

> Cỡ mẫu nhỏ (7–10 trang/site) — dùng để trả lời câu hỏi định tính "hình dạng
> này có phổ biến không", **không** dùng làm tỷ lệ độ phủ.

### "La bàn" LLM — hỏi vị trí, không hỏi nội dung

Tầng 2 trả thêm trường `muc_uu_diem`: **một dòng tiêu đề** của mục ưu điểm, chép
nguyên văn. Không phải nội dung — nội dung vẫn do code cắt từ HTML. Lý do: LLM
nhận diện "đây là mục ưu điểm" tốt hơn mọi luật từ vựng, nhưng nếu để nó **viết**
hai cột thì không còn cách nào phân biệt chép và bịa. Hỏi vị trí thì câu trả lời
luôn đối chiếu được với chính HTML.

La bàn cũng chỉ là ứng viên `+60` điểm chứ không phải lệnh, vì **nó chỉ sai được**:
trang KingLED nào cũng có nhãn tab `<h3>ưu điểm sản phẩm</h3>` nằm cạnh "Mô tả
sản phẩm", và cả LLM lẫn luật từ khoá đều bám vào đó — trong khi phần lớn trang
để tab đó **rỗng**, nội dung thật nằm dưới các đề mục không mang dấu hiệu gì.
Luật loại-mục-rỗng vô hiệu hoá cái bẫy này.

### Ba chi tiết cắt HTML, mỗi cái là một bẫy đã thấy

1. **Dừng theo CẤP heading, không dừng ở thẻ `<h>` bất kỳ.** Mục của KingLED là
   `<h2>` và bên trong có 8 `<h3>` con — dừng ở `<h3>` đầu tiên thì cắt mất gần
   hết mục.

2. **Heading không phải lúc nào cũng có anh em.** Có trang bọc riêng heading
   trong một `<div>` → 0 thẻ anh em, phải leo lên thẻ cha rồi mới lấy. Có trang
   để heading phẳng cùng cấp với nội dung → phải nới điều kiện dừng.

3. **Bỏ số thứ tự mục và dòng bán chéo,** nhưng đừng bỏ quá tay: cắt tiền tố số
   kiểu ngây thơ biến `"2 dải LED to bản"` thành `"dải LED to bản"`. Chỉ cắt khi
   có dấu phân cách (`1.` `1)`) hoặc số nhiều cấp (`1.1`).

> Chữ **"đ"/"Đ" là ký tự riêng** (U+0111/U+0110), NFD không tách được thành
> `d` + dấu. Bỏ dấu kiểu thông thường thì "ưu điểm" ra "uu điem" — vẫn còn chữ
> đ và regex không khớp. Phải thay tay. Bug này từng làm cả 3 site trả về rỗng
> **mà không báo lỗi gì**.

---

## Tầng 2 — LLM normalization

**Code:** `src/crawler/llm/`

Phần thông số kỹ thuật trên trang là văn bản tự do, mỗi site trình bày một kiểu,
không thể parse bằng selector cố định. Tầng này dùng LLM để chuyển nó thành field
`Tags` dạng JSON.

### Luồng

```
HTML thô  ──►  html_cleaner  ──►  build_prompt  ──►  provider  ──►  validate
             (bỏ nav/script)     (prompt + schema)   (Vertex/     (parse JSON,
                                                      DeepSeek)    lọc giá trị)
```

**1. Làm sạch HTML** (`html_cleaner.py`) — bỏ `script`, `style`, `nav`, `footer`,
`header`, `form`, `iframe`…, gom bảng thành các dòng `label: value`, cắt còn tối
đa 12.000 ký tự. HTML thô một trang TLC nặng ~200KB (~15.000 token); sau khi làm
sạch chỉ còn ~2.000 token.

Có hai hàm phục vụ hai mục đích khác nhau, **không dùng chung output**:

- `clean_html_for_llm` — đưa cả bảng lẫn mô tả cho LLM, chấp nhận hơi "rộng" vì
  model tự lọc được.
- `extract_spec_text` — **chỉ** lấy đúng các dòng `label: value` từ bảng 2 cột
  đối xứng, dùng cho cột `Thông số kỹ thuật` trong bản ghi. Phải sạch vì đây là
  giá trị lưu thẳng vào Excel (bug đã gặp: field dài 4.000 ký tự vì lấy cả menu
  danh mục lẫn mô tả marketing).

Riêng bảng thông số kiểu TLC — hai cột nhưng label/value gộp lộn xộn bằng `<br>`
trong cùng một `<td>` — được tách theo số dòng đối xứng giữa 2 ô.

**Không phải site nào cũng có `<table>`.** KingLED không có **một thẻ `<table>`
nào** trên cả trang; thông số nằm ở bố cục
`<label>Công Suất</label><span>: 12w</span>` trong các `<div>` lồng nhau. Vì vậy
hai hàm trên còn đọc được cặp "label: value" — nhưng **chỉ trong phạm vi
`spec_root_selector`** đăng ký theo domain, và phạm vi ở đây là **bắt buộc chứ
không phải tùy chọn**:

> Chính bố cục `<label>`/`<span>` đó được KingLED **dùng lại cho khối "sản phẩm
> liên quan"** ở cuối trang. Một trang sản phẩm đếm được **38–107 thẻ `<label>`**,
> trong đó chỉ 10–16 cái đầu là của sản phẩm đang xem; số còn lại là
> "Mã SP / Công Suất / Quang Thông…" của **8 sản phẩm khác**. Quét cả trang sẽ
> ghi thông số của sản phẩm khác vào bản ghi này — đúng nghĩa bịa dữ liệu, và
> **không phát hiện được khi review** vì mọi giá trị đều "có thật trên trang",
> kể cả thước đo groundedness cũng chấm là đạt.
>
> `div.property[data-id="Property"]` khoanh đúng khối của sản phẩm đang xem (đó
> là tab "Thông số kỹ thuật" của chính nó). Selector không khớp node nào thì trả
> về rỗng — trang không đúng khuôn đã khảo sát thì để trống cho bản ghi bị gắn
> cờ, còn hơn đoán bừa.

Hai chi tiết nhỏ nhưng cần thiết ở bố cục này:

- Thuộc tính nhiều giá trị được site tách thành nhiều `<a>` riêng
  (`Ánh Sáng: <a>Trắng</a><a>Trung tính</a><a>Vàng</a>`) — nối bằng **dấu phẩy**
  chứ không phải dấu cách, vì "Trắng Trung tính Vàng" đọc ra như một giá trị
  liền khúc và LLM rất dễ hiểu sai.
- `<label>` của ô nhập liệu (form "Đăng ký tư vấn": Họ tên*, Số điện thoại*…)
  bị loại — không phải thông số kỹ thuật.

Với `clean_html_for_llm`, các dòng thông số được đặt **lên đầu** prompt. Khối
thông số của KingLED nằm gần **cuối** trang (trong popup tab), giữ thứ tự tự
nhiên thì nó bị cắt mất bởi giới hạn 12.000 ký tự và tầng 2 không còn gì để đọc.

**2. Gọi LLM** (`provider.py`, `vertex_provider.py`, `deepseek_provider.py`) —
một interface chung `generate_json(prompt, json_schema)`:

- **Vertex AI (`gemini-2.5-flash`)** — provider chính, hỗ trợ structured output
  trực tiếp qua `response_json_schema`.
- **DeepSeek (`deepseek-chat`)** — fallback, API tương thích OpenAI. Chỉ hỗ trợ
  JSON mode chung chung, không nhận schema cụ thể, nên `json_schema` bị bỏ qua có
  chủ đích và dựa vào hướng dẫn trong prompt + bước validate.

**3. Fallback tự động** (`fallback.py`) — `FallbackLLMProvider` thử lần lượt từng
provider; provider nào ném `LLMProviderError` (hết quota/auth/network) thì
chuyển sang provider kế tiếp và ghi log lần chuyển đổi. Chỉ khi **tất cả** đều
lỗi mới ném ra ngoài.

**4. Validate output** (`validate.py`) — parse JSON (gỡ cả khối ```json nếu model
tự bọc), bắt buộc có object `tags`, lọc bỏ key rỗng và value quá dài (>200 ký
tự), giới hạn 60 tag. Output không hợp lệ ném `ExtractionValidationError`, bản
ghi bị **gắn cờ để review** thay vì lưu như dữ liệu đã xác thực.

### Schema Tags là linh hoạt

Tên các key trong `Tags` được suy ra từ **chính nội dung nguồn của từng site**,
không ép về một danh sách cố định. Prompt yêu cầu đặt key bằng tiếng Việt không
dấu, `snake_case`, theo đúng tên thuộc tính xuất hiện trên trang, và **không bịa**
thuộc tính không có trong nguồn.

Thực tế trên TLC: trung bình ~13 thuộc tính/sản phẩm (công suất, điện áp, nhiệt
độ màu, CRI, IP, góc chiếu, bảo hành…), phong phú hơn hẳn 4 field mẫu của schema
tham chiếu.

---

## Kho dữ liệu (crawl.db)

**Code:** `src/crawler/store/`

Nguồn sự thật của dự án. File `.xlsx` **không còn là nơi lưu trữ** — nó là bản
kết xuất ở bước cuối.

Ba bảng, tách **hai lịch sử khác bản chất**:

```
      đối thủ đổi trang                      MÌNH đổi code
            │                                      │
            ▼                                      ▼
   ┌──────────────────┐                  ┌────────────────────┐
   │  page_snapshots  │  1:N             │    extractions     │
   │  1 dòng / FETCH  │─────────────────▶│  1 dòng / TRÍCH    │
   │  html_gz (zlib)  │                  │  extractor_version │
   └──────────────────┘                  └────────────────────┘
                                                   │ 1:N
                                          ┌────────────────────┐
                                          │   product_tags     │
                                          └────────────────────┘
```

Gộp chung vào một bảng ghi đè thì khi một giá trị khác đi so với lần trước,
**không phân biệt được** *"đối thủ hạ giá"* với *"mình vừa sửa parser"*. Tách ra
thì phân biệt được ngay: snapshot đổi → họ đổi; snapshot y nguyên mà extraction
đổi → mình đổi.

`products` là một **VIEW** ("bản trích xuất mới nhất trên snapshot mới nhất mỗi
URL"), không phải bảng — view luôn đúng theo định nghĩa, không lệch được với
bảng nguồn.

### HTML được lưu cho MỌI trang

Không chỉ trang trích xuất hỏng. Lý do: ô **sai mà tưởng đúng** không tự khai
báo — pipeline coi nó là thành công nên sẽ không lưu HTML, tức đúng ca cần soi
nhất lại là ca không có dữ liệu để soi. Tỉ lệ nén zlib đo thật: 8,8× (KingLED) /
4,8× (TLC) / 3,9× (Roman) → ~32 MB cho 1034 sản phẩm đã có.

### Sửa bộ trích xuất mà không phải crawl lại

```bash
python scripts/reextract.py kingled.com.vn --version v2
python scripts/diff_extractions.py kingled.com.vn v1 v2
```

`reextract` chạy lại tầng 1/1.5/1.6 trên HTML đã lưu — **0 request mạng, 0 quota
LLM**: kết quả tầng 2 (`tags`, `ma_san_pham`, và **la bàn** `uu_diem_la_ban`)
được mang theo từ lần trích xuất trước. Đo thật: **549 trang trong 203 giây**
(370 ms/trang) so với ~35 phút của một lượt crawl lại — 10×.

> Vì sao phải lưu cả la bàn chứ không chỉ `uu_diem_nguon`: nhánh `anchor` chỉ
> tìm được mục nhờ một dòng do tầng 2 chỉ ra. Không lưu lại thì mỗi lần chạy lại
> đều mất sạch nhánh đó, và `diff_extractions` báo hồi quy **giả** ở mọi ô vốn
> tìm thấy nhờ la bàn.

`diff_extractions` trả lời câu hỏi trước đây không trả lời được: một chỉnh sửa
**vá được mấy ô và làm hỏng mấy ô**.

### Nguồn gốc trích xuất

Cột `uu_diem_nguon` ghi lại **đường nào** định vị được mục ưu điểm:
`keyword` / `anchor` / `cluster` / `none`. Thông tin này trước đây bị vứt đi
ngay sau khi chấm điểm. Giữ lại thì món nợ kỹ thuật có ý thức ở nhánh cụm
(6/360 ô lấy nhầm của KingLED) trở thành một câu truy vấn thay vì một buổi mở
tay 360 ô.

---

## Bản ghi sản phẩm & output

**Code:** `src/crawler/record/`

### Khuôn cột

**Đủ 20 cột** của sheet "2. LED Downlight" trong `product_Metadata (1).xlsx`,
đúng tên và đúng thứ tự:

`STT`, `Product_ID`, `Tên sản phẩm`, `Mã Sản Phẩm`, `Mã SAP`, `category 1`,
`category 2`, `category 3`, `Tags`, `Giá`, `Giá đối chiếu`, `Link sản phẩm`,
`Link ảnh sản phẩm`, `Link mua hàng online`, `Tóm tắt TSKT`,
`Tóm tắt ưu điểm, tính năng`, `Thông số kỹ thuật`, `Link file HDSD`,
`VD HDSD`, `Nội dung Ưu điểm SP`

Cột nào site đối thủ không có dữ liệu tương đương thì **để ô trống chứ không bỏ
cột** — khuôn cột lệch thì bên nhận phải căn chỉnh tay trước khi ghép vào file
tham chiếu. Hiện luôn trống với TLC: `Mã SAP`, `Giá đối chiếu`,
`Link mua hàng online`, `Tóm tắt TSKT`, `Link file HDSD`, `VD HDSD`.

Tên cột được chép **nguyên văn** từ hàng header của sheet tham chiếu, kể cả
khoảng trắng thừa (`' category 1 '`, `'Thông số kỹ thuật '`) để header so khớp
tuyệt đối với khuôn gốc. Phía đọc lại (`excel_reader`) tự `strip()` khi ghép cột
nên khoảng trắng này không làm gãy round-trip.

`STT` là số thứ tự **dòng trong từng sheet**, writer tự đánh lại 1..N mỗi lần
ghi (đọc lại thì bỏ giá trị cũ đi — bản ghi đổi sheet sẽ làm số cũ thủng/trùng).

### Cấu trúc file: mỗi loại sản phẩm 1 sheet

Một site → **một file `.xlsx`**, chia thành nhiều sheet, mỗi sheet là một loại
sản phẩm, bám theo cách tổ chức của chính `product_Metadata (1).xlsx`. Loại sản
phẩm lấy theo `category 1` của site nguồn (không ánh xạ sang taxonomy khác).

Thứ tự sheet theo **thứ tự xuất hiện đầu tiên** của mỗi loại chứ không sắp A–Z:
thứ tự đó phản ánh thứ tự duyệt danh mục của site, dễ đối chiếu ngược lại hơn.
Bản ghi không có `category 1` (thường là fetch lỗi) gom vào sheet
`Chưa phân loại` ở cuối file — giữ lại để lần chạy sau còn crawl lại được, thay
vì vứt đi.

### Giá có 3 trạng thái

Đây là quy tắc cốt lõi, ba trạng thái **không được gộp lẫn nhau**:

| Giá trị | Ý nghĩa |
|---|---|
| `float` (vd `166000.0`) | Trang nguồn hiển thị giá bằng số |
| `"Liên hệ"` (literal) | Site **xác nhận** không công khai giá |
| `None` | **Chưa crawl được** — lỗi kỹ thuật, cần crawl lại |

`normalize_price` (`price.py`) chuẩn hoá giá trị thô về đúng một trong ba trạng
thái trên, xử lý cả dấu chấm phân cách nghìn kiểu Việt Nam (`339.900` →
`339900.0`). Giá trị không phân giải được thì **ném lỗi** thay vì đoán bừa.

### Field optional

`Mã SAP`, `Link mua hàng online`, `Link file HDSD`, `Giá đối chiếu`, `VD HDSD`
được phép null khi site nguồn không có tương đương — null ở đây **không** bị coi
là crawl lỗi.

### Category giữ nguyên theo site nguồn

`category 1/2/3` lấy nguyên breadcrumb gốc của từng site, **không** ánh xạ sang
taxonomy chung. Số cấp có thể khác nhau giữa các site (đã thấy 2–5 cấp). Cách
lấy: bỏ phần tử đầu (Trang chủ) và cuối (chính tên sản phẩm), lấy tối đa 3 cấp
còn lại.

### Trạng thái crawl & crawl lại có chọn lọc

Mỗi bản ghi có `crawl_status` nội bộ — `ok` / `error` / `partial-missing-fields`
— **không** xuất ra cột Excel nào: đó là dữ liệu vận hành, không thuộc khuôn
tham chiếu.

Vì trạng thái không nằm trong file, khi đọc lại nó được **suy ra lại** từ chính
các cột đã lưu: bản ghi thiếu bất kỳ field bắt buộc nào
(`Tên sản phẩm`, `Mã Sản Phẩm`, `category 1`, `Link sản phẩm`,
`Link ảnh sản phẩm`, `Giá`, `Tags`) là ứng viên crawl lại.

> `Tags` nằm trong nhóm bắt buộc chính vì lý do này: khi tầng 2 lỗi, `Tags` rỗng
> là **dấu vết duy nhất** còn lại trong file Excel cho biết bản ghi đó chưa hoàn
> chỉnh. Nếu không tính `Tags`, một bản ghi LLM lỗi sẽ được ghi ra với trạng thái
> `ok` và không bao giờ được crawl lại.

Cơ chế chạy lại (`pipeline.crawl_product_urls`): đọc file `.xlsx` đã có, URL nào
đã có bản ghi `ok` thì **tái sử dụng, không fetch lại và không gọi LLM lại**. Chỉ
crawl lại các URL lỗi/thiếu field.

Thực tế trên TLC: lần chạy đầu ~7 phút cho 129 sản phẩm; lần chạy lại ~17 giây
với **0 lần gọi LLM**.

### Xuất Excel

Mỗi site một file `.xlsx` **riêng** (`output/<tên-site>.xlsx`), không gộp nhiều
site vào một file — tránh nhầm nguồn khi review và cho phép chạy lại từng site
độc lập. `Tags` được serialize thành chuỗi JSON trong ô.

---

## Chạy pilot TLC

**Code:** `scripts/crawl_tlc_downlight.py`, `src/crawler/sites/tlc.py`

```bash
.venv/bin/python scripts/crawl_tlc_downlight.py
```

Các bước script thực hiện:

1. Dựng LLM provider (Vertex chính + DeepSeek fallback, tuỳ cấu hình có sẵn).
2. Site-probing `tlclighting.com.vn` → xác nhận `product-sitemap.xml` đáng tin cậy.
3. Lấy URL của riêng category "Đèn LED âm trần" bằng cách **phân trang qua chính
   trang danh mục** (`/danh-muc/den-led-am-tran/page/N/`).

   > Sitemap dùng để **đối chiếu**, không phải để liệt kê trực tiếp — vì sitemap
   > chứa toàn bộ sản phẩm của site nhưng **không mang thông tin category**.
   > Script cảnh báo nếu có URL từ category không khớp tập URL đã probe.

4. Đọc file `.xlsx` cũ (nếu có) để crawl lại có chọn lọc.
5. Chạy pipeline cho từng URL → `output/tlclighting.xlsx`.

**Cấu hình cần thiết** (xem `.env.example`): ít nhất một trong
`VERTEX_PROJECT_ID` (hoặc `GOOGLE_APPLICATION_CREDENTIALS` trỏ tới file service
account) và `DEEPSEEK_API_KEY`. `CLOAKBROWSER_EXECUTABLE_PATH` là tuỳ chọn.

### Hiệu năng & chi phí thực đo

Số liệu từ lần chạy thật ngày 13/08/2026, 129 sản phẩm, Vertex AI
`gemini-2.5-flash`:

| | Bật thinking (mặc định) | **Tắt thinking (hiện tại)** |
|---|---:|---:|
| Thời gian / sản phẩm | 25,0s | **7,0s** |
| Tổng thời gian 129 SP | ~54 phút (ước tính) | **15,1 phút** (đo thật) |
| Input token / SP | ~2.974 | ~2.974 |
| Output token / SP | ~2.238 | ~230 |
| **Chi phí 129 SP** | ~$0,62 – $0,84 | **~$0,19** |

Giá Vertex AI: $0,30/1M input, $2,50/1M output. Thinking token tính theo giá
output — đó là lý do nó từng chiếm ~85% hoá đơn.

### Song song hoá: bất đối xứng, và đó là cố ý

Trực giác "song song hoá tất cả" **sai** với pipeline này. Đo thực tế:

**Fetch song song làm CHẬM ĐI** (24 sản phẩm TLC):

| Luồng fetch | Thời gian | Kết quả |
|---:|---:|---|
| 1 | 3,38s/SP | — |
| 4 | 4,04s/SP | chậm hơn 16% |
| 8 | 5,77s/SP | chậm hơn 41% + timeout → **mất sản phẩm** |

Server đối thủ bóp băng thông theo số kết nối đồng thời. Máy mình (12 core) hoàn
toàn rảnh — nút thắt nằm ở phía họ.

**Gọi LLM song song thì có ăn thật** (phía Google):

| Luồng LLM | Throughput |
|---:|---:|
| 1 | 16,6 SP/phút |
| 3 | 28,8 SP/phút |
| 6 | 39,5 SP/phút |

Nên kiến trúc là: **fetch tuần tự 1 luồng, xử lý song song N luồng, hai phần
chồng lên nhau**. Trong lúc worker gọi LLM cho sản phẩm N thì main thread đã
fetch sản phẩm N+1 — thời gian LLM bị "giấu" sau thời gian fetch. Đo được
**1,85×** nhanh hơn với `CRAWL_WORKERS=4`.

Trần còn lại chính là phần fetch tuần tự, và đó là trần **không nên** phá thêm:
phá nó đồng nghĩa với làm phiền server đối thủ và tự chuốc timeout.

> **Lưu ý về quota Vertex:** `429 RESOURCE_EXHAUSTED` xảy ra thường xuyên. Provider
> đã có **retry + backoff mũ (6 lần, tối đa ~62s)**, đủ nuốt phần lớn lỗi thoáng
> qua. Nhưng khi quota bị bào mòn (chạy nhiều đợt liên tiếp), nghỉ 100s cũng
> không cứu được → giới hạn là theo **giờ/ngày**, không phải theo phút.
>
> Quan trọng: **credit $300 free trial KHÔNG nâng quota** — đó là hạn mức *tiền*,
> còn 429 là hạn mức *tốc độ*. Tài khoản đang ở trạng thái Free trial thì **không
> được phép xin nâng quota**; phải nâng cấp lên Paid billing account (vẫn giữ
> nguyên credit chưa dùng) mới mở được quyền đó.

### Tự giới hạn theo trần thật (adaptive throttle)

Trần của site đối thủ **không biết trước và thay đổi theo tải của họ** — thực tế
đã gặp: sau nhiều đợt fetch liên tiếp, `tlclighting.com.vn` bắt đầu trả
`ERR_CONNECTION_REFUSED` và timeout 30s. Hardcode một con số cố định vì thế
không giải quyết được vấn đề.

`StealthFetcher` tự điều chỉnh nhịp:

| Sự kiện | Hành vi |
|---|---|
| Fetch lỗi (timeout, refused, 403/406/429) | cooldown ×2 (tối thiểu 1s), trần `FETCH_MAX_COOLDOWN`=15s |
| Fetch thành công | cooldown ÷2, về 0 khi đủ nhỏ |
| Mọi thứ bình thường | cooldown = 0 → **không trễ gì cả** |

Nghĩa là: chạy nhanh hết mức khi server còn khoẻ, tự giãn ra khi nó bắt đầu từ
chối, rồi tự siết lại khi ổn. Giảm dần bằng cách chia đôi (không reset thẳng về
0) để tránh dao động — lao lại vào trần rồi lại bị chặn.

Chỉnh tay qua `FETCH_MIN_INTERVAL` (giãn cách tối thiểu, mặc định 0) nếu gặp site
nhạy cảm hơn TLC.

### Công cụ đo trần: `scripts/tune_crawl.py`

```bash
.venv/bin/python scripts/tune_crawl.py 16     # 16 sản phẩm cho mỗi mức
```

Quét các mức worker (1/2/4/8) và chấm **cả tốc độ lẫn chất lượng**, vì nhanh mà
hỏng dữ liệu thì không tính là tối ưu:

| Chỉ số | Ý nghĩa |
|---|---|
| giây/SP | tốc độ |
| tỷ lệ lỗi | % sản phẩm không đạt trạng thái `ok` |
| tag TB | số thuộc tính trung bình — tụt là dấu hiệu chất lượng giảm |
| **có căn cứ** | % giá trị tag **thực sự xuất hiện trong text nguồn** — thước đo chống bịa |

Script tự đề xuất mức **nhanh nhất trong số các mức giữ được chất lượng** (lỗi
≤5% và tag ≥95% mức tốt nhất), không phải mức nhanh nhất tuyệt đối.

Mỗi mức dùng sản phẩm khác nhau và nghỉ 45s giữa các mức, để mức đo sau không bị
thiệt vì mức trước vừa vét quota.

> **Đo lại khi nào:** khi onboard site mới, khi đổi model/provider, hoặc khi thấy
> tỷ lệ lỗi tăng. Đừng đo ngay sau một đợt crawl lớn — quota chưa hồi, số liệu sẽ
> sai lệch.

---

## Chạy toàn site KingLED

```bash
.venv/bin/python scripts/crawl_site.py https://kingled.com.vn
```

Số liệu lần chạy thật **21/08/2026** (chạy lại sau khi bật nhánh cụm ở tầng
1.6), `kingled.com.vn`, Vertex AI `gemini-2.5-flash`:

| | Kết quả | Lần 20/08 |
|---|---:|---:|
| URL sản phẩm (sitemap `?page=Product`) | 557 mục → **549 URL riêng biệt** | = |
| Bản ghi ghi ra | 549 (**24 sheet** theo loại sản phẩm) | = |
| Thời gian | **65,5 phút** (7,16 s/sản phẩm, 4 luồng) | 65,8 phút |
| Fetch lỗi / LLM lỗi | **0 / 0** | 0 / 0 |
| Trạng thái OK | 403/549 (**73,4%**) | 404/549 |
| Tag trung bình | 9,2/sản phẩm (5.078 giá trị) | 9,6 (5.252) |
| `Tóm tắt ưu điểm, tính năng` có dữ liệu | **65,6%** (360/549) | 58,3% |
| `Nội dung Ưu điểm SP` có dữ liệu | **68,1%** (374/549) | 60,5% |

Hai lần chạy lệch nhau ~170 giá trị tag (9,6 → 9,2) dù prompt, model và trang
nguồn đều không đổi — đó là **dao động giữa các lần gọi LLM**, không phải hồi
quy. Đừng dùng chênh lệch cỡ này để nghiệm thu bất cứ thay đổi nào.

Chuyện đáng ghi của lần chạy này: `429 RESOURCE_EXHAUSTED` từ Vertex AI nổ 27
lần, cơ chế thử lại nuốt hết; **2 lần** phải rơi hẳn xuống DeepSeek (`Connection
reset by peer`) và cả 2 đều trả về bình thường. Đường dự phòng nhiều provider đã
chứng minh có tác dụng trong chạy thật, không chỉ trong test.

> **Đợt chạy 20/08 chết giữa chừng ở sản phẩm 80/549** (phiên làm việc đứt, log
> dừng không có dòng kết thúc). Chạy lại chỉ tái sử dụng được **58/80** bản ghi
> cũ — 22 cái còn lại mang cờ `partial-missing-fields` nên vào lại hàng đợi. Cơ
> chế checkpoint đã làm đúng việc của nó: không mất gì, chỉ tốn thêm ~3 phút.

**146 bản ghi "cần review" hầu hết KHÔNG phải lỗi crawl.** 142/146 thiếu **đúng
một** cột `Giá`, và đó là do site không niêm yết giá cho nhóm phụ kiện / một số
dòng đèn — đã kiểm chứng bằng **đường độc lập với pipeline** (quét text đã render
tìm số tiền + đọc lại `meta itemprop="price"`) trên 12 mẫu ngẫu nhiên: **12/12**
đều không có khối `div.price`, không có chuỗi tiền nào, `meta price=0`.

4 bản ghi còn lại cũng đã soi tay và đều đúng với nguồn:

| Sản phẩm | Thiếu | Vì sao đúng |
|---|---|---|
| `phu-kien-lap-rap` | mã SP + giá | trang không có mã SP |
| `dieu-khien-smart-9-kenh` | tags | bảng thông số chỉ đúng 1 dòng "Mã SP" |
| `den-led-gan-tuong-gmd-f328` | giá + tags | khối thông số **rỗng** trên chính site (fetch lại 2 lần đều rỗng — không phải đua tranh với JS) |
| `khop-noi-2-thanh-ray-chu-l` | tags | phụ kiện cơ khí, không có thông số điện |

> **Hệ quả cần biết:** 144 bản ghi thiếu `Giá` sẽ là ứng viên crawl lại ở **mọi
> lần chạy sau**, dù kết quả không bao giờ đổi. Xem [todo.md](todo.md) mục 2.

### Bẫy "khối sản phẩm liên quan" — và giới hạn của thước đo groundedness

Khoanh vùng `spec_root_selector` cứu được cột `Thông số kỹ thuật` nhưng **không**
cứu cột `Tags`: `clean_html_for_llm` có chủ đích kèm cả text mô tả, và phần đó
mang theo thông số của các sản phẩm liên quan. Đo được trên `bo-nguon-150w`:
khối thông số riêng chỉ 4 dòng và **không có dòng bảo hành**, thế mà bản ghi vẫn
ra `bao_hanh="Đổi mới 2 năm"` — nhặt từ một phụ kiện ở cuối trang (phần text đưa
cho LLM chứa thêm 5 "Mã SP" + 5 "Bảo Hành" của phụ kiện khác).

Trang **ngắn** mới là trang nguy hiểm: trang dài thì giới hạn 12.000 ký tự tự nó
đã cắt mất khối liên quan, còn trang thông số thưa — đúng loại cần tầng 2 nhất —
thì khối đó lọt trọn vào prompt.

Sau khi gỡ `div.item`: `"Bảo Hành"` 5 lần → **0**, thông số của chính sản phẩm
còn nguyên.

> **Đừng dùng tỷ lệ "tag có căn cứ" để nghiệm thu sửa lỗi này.** So sánh 2 lần
> chạy trên **cùng 240 URL**: 94,7% → 94,1% — gần như không đổi, dù lỗi đã được
> sửa thật. Lý do: thước đo đối chiếu với *bảng thông số*, mà phần lớn giá trị
> "không có căn cứ" lại là thuộc tính **thật nhưng chỉ được nói trong phần mô
> tả** (IP44, CRI, quang hiệu…). Nó đo "giá trị nằm ngoài bảng thông số", không
> đo "giá trị của sản phẩm khác". Muốn nghiệm thu thì phải soi đúng trang đã lỗi.

## Thêm một site đối thủ mới

**Không thêm file .py nào cả.** Mặc định là chạy thẳng:

```bash
.venv/bin/python scripts/crawl_site.py https://<domain-doi-thu>
.venv/bin/python scripts/crawl_site.py https://<domain-doi-thu> --limit 15
```

Script này dùng chung cho mọi site: site-probing tìm nguồn URL sản phẩm, tầng 1
đọc structured data, tầng 2 chuẩn hoá thông số, kết quả ra
`output/<domain>.xlsx`. Nếu đo trên trang thật mà thấy thiếu, phần riêng của
site được khai là **một dòng dữ liệu** trong registry theo domain, không phải
một module:

| Registry | Trả lời câu hỏi | Ví dụ |
|---|---|---|
| `sites/registry.py` | Tìm và tải trang sản phẩm thế nào | `product_url_pattern` (TLC), `wait_selector` (KingLED) |
| `extraction/css_fallback.py` | Đọc nội dung một trang đã tải thế nào | `DOMAIN_FALLBACK_RULES` (Roman), `DOMAIN_SPEC_ROOT_SELECTORS` + `DOMAIN_PLACEHOLDER_PRICES` (KingLED) |

> `sites/tlc.py` **không** phải khuôn mẫu để nhân bản cho site mới: đó là logic
> phân trang qua **một category cụ thể** phục vụ bản pilot, không phải cấu hình
> để crawl toàn site. Script `crawl_tlc_all.py` cũ đã bị xoá vì trùng hoàn toàn
> với `crawl_site.py` — bộ dữ liệu `output/tlclighting_all.xlsx` dựng lại bằng:
>
> ```bash
> .venv/bin/python scripts/crawl_site.py https://tlclighting.com.vn \
>     --output output/tlclighting_all.xlsx
> ```

Kiến trúc được thiết kế để **không phải sửa tầng 1/1.5/2**. Việc cần làm:

0. **Xác nhận đúng domain trước đã.** KingLED có **hai site cùng sống**:
   `kingled.vn` là site giới thiệu — "trang sản phẩm" của nó thực chất là trang
   dòng sản phẩm, và structured data trên đó là 25 block
   `schema.org/SomeProducts` mô tả **menu danh mục** (`price=0`, `sku` rỗng) chứ
   không phải sản phẩm đang xem. Crawl nhầm domain đó ra **123 bản ghi rỗng mà
   không báo lỗi gì**. Catalogue thật nằm ở `kingled.com.vn`: 557 sản phẩm,
   microdata `schema.org/Product` đầy đủ. Bài kiểm tra rẻ nhất: mở 1 trang sản
   phẩm bất kỳ, xem tầng 1 có trả về đúng tên + giá + mã của **chính sản phẩm
   đó** không.
1. Chạy site-probing cho domain mới → xác định nguồn URL sản phẩm.
2. Kiểm tra tầng 1 có lấy đủ field không. Nếu thiếu, thêm vài `SelectorRule` vào
   `DOMAIN_FALLBACK_RULES` cho domain đó (tầng 1.5).
3. Nếu trang cần JS mới hiện thông số (case KingLED), thêm `wait_selector` vào
   `SITE_PROFILES`.
4. Nếu site không trình bày thông số bằng `<table>` (case KingLED), đăng ký
   `DOMAIN_SPEC_ROOT_SELECTORS` — và **kiểm tra selector đó không bao trùm khối
   "sản phẩm liên quan"**.
5. Chạy thử `--limit` nhỏ (10–15 sản phẩm) rồi soi bằng
   `scripts/report_crawl.py` **trước khi** chạy cả site — lỗi khoanh vùng sai
   chỉ lộ ra khi nhìn dữ liệu, không lộ ra qua tỷ lệ lỗi.

Tầng 2 (LLM) không cần đụng tới — prompt và schema đã là tổng quát.

---

## Kiểm thử

```bash
.venv/bin/python -m pytest tests/
```

Test dùng **fixture HTML thật** lưu ở `tests/fixtures/` (không gọi mạng, không
cần credential):

| File test | Nội dung kiểm tra |
|---|---|
| `test_detection.py` | Phân biệt landing rỗng vs lưới sản phẩm thật (fixture Roman) |
| `test_structured_data.py` | JSON-LD (TLC), Microdata (KingLED), fallback OpenGraph (Roman) |
| `test_price.py` | Giá tri-state: số / "Liên hệ" / null |
| `test_llm_fallback.py` | Chuyển provider khi provider chính lỗi (dùng provider giả) |
| `test_html_cleaner.py` | Field "Thông số kỹ thuật" sạch: bảng TLC, bảng Roman sống sót qua strip `<form>`, và bố cục `<label>`/`<span>` của KingLED **không lẫn sản phẩm liên quan** |
| `test_sitemap.py` | Chọn đúng sub-sitemap sản phẩm (2 kiểu đặt tên taxonomy) + phục hồi sitemap XML sai chuẩn mà vẫn từ chối trang HTML |
| `test_advantages.py` | Mục "Ưu điểm" trên các hình dạng khác nhau (TLC `<li>`, KingLED/Roman `<h3>`, cụm đề mục không có tiêu đề) + không lấy nhầm chữ "ưu điểm" trong mega-menu, nhãn tab rỗng, cụm dưới tiêu đề mẹ mang tín hiệu âm |
| `test_prompt.py` | Prompt tầng 2 nêu đủ cơ chế chống bịa, và ngoặc trong ví dụ JSON không bị nhân đôi |
| `test_validate.py` | Loại giá trị không có trong nguồn, nhưng KHÔNG xoá nhầm giá trị chỉ đổi cách trình bày |
| `test_site_registry.py` | Domain **chưa đăng ký** vẫn crawl được bằng hành vi mặc định — tính chất giữ cho "thêm đối thủ mới" không đẻ thêm file .py |
| `test_pipeline_checkpoint.py` | Ghi tạm **giữa chừng** đợt crawl, không phải ở những giây cuối |
| `test_store_db.py` | Nén/giải nén HTML, và VIEW `products` chọn đúng bản mới nhất khi snapshot/extraction đan xen |
| `test_store_pipeline.py` | Snapshot ghi **trước** khi trích xuất; nhiều worker cùng xong không mất bản ghi, không `database is locked` |
| `test_reextract.py` | Chạy lại trên HTML đã lưu **không chạm mạng**; la bàn sống sót qua lần chạy lại (có test đối chứng khi không lưu la bàn) |
| `test_store_export.py` | Khuôn 20 cột không đổi, sheet cảnh báo tách riêng, và **không ô nào bị cắt âm thầm** ở giới hạn 32.767 ký tự của Excel |

Fixture `tlc_blog_post.html` và `tlc_static_page.html` là 2 trang thật lấy từ
chính `post-sitemap.xml` / `page-sitemap.xml` của TLC — dùng làm mẫu "rác" đại
diện cho thứ lọt vào sitemap, để chỉnh ngưỡng của bộ phát hiện trang sản phẩm.

Có **hai** fixture KingLED và chúng không thay thế nhau:
`kingled_product.html` là bản HTML tĩnh (dùng cho test structured data), còn
`kingled_product_rendered.html` là **cùng trang đó sau khi JS chạy** — chỉ bản
sau mới có nội dung trong khối thông số, và chỉ bản sau mới thể hiện được bẫy
"sản phẩm liên quan dùng chung bố cục".

> **Chưa có test cho:** (a) bản ghi lỗi tầng 2 bị gắn cờ và sống sót qua vòng
> ghi/đọc Excel, (b) bộ phát hiện từ chối 2 fixture "rác" ở trên. Cả hai hành vi
> đều đã được kiểm chứng thủ công khi sửa, nhưng chưa được khoá lại bằng test tự
> động — nên thêm khi có dịp.
