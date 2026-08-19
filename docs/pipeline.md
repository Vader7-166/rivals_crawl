# Pipeline crawl dữ liệu sản phẩm đối thủ

Tài liệu mô tả cách hệ thống lấy dữ liệu sản phẩm từ website đối thủ (ngành đèn
LED chiếu sáng) và xuất ra file Excel.

Vấn đề gốc: mỗi site đối thủ dùng một nền tảng khác nhau, không site nào giống
site nào ở bất kỳ khâu nào. Khảo sát 3 site thật cho thấy:

| | TLC | Roman | KingLED |
|---|---|---|---|
| Nền tảng | WordPress + WooCommerce | ASP.NET WebForms | CMS tự viết |
| Structured data | JSON-LD `Product` | **Không có gì** | Microdata `Product` |
| Bảng thông số | Lộn xộn, gộp trong 1 `<td>` | `<table>` sạch | **Rỗng** — chỉ có sau khi JS chạy |
| Sitemap | `product-sitemap.xml` mới | Cũ từ 2021, thiếu SP | Sitemap động theo content-type |
| Bẫy cấu trúc | Không | Danh mục cha là landing rỗng | Không |
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
   taxonomy sản phẩm** (`product_cat`, `product_tag`, `product_brand`… —
   WooCommerce đặt tên taxonomy theo tiền tố `product_`). Đây là bài học thực tế
   từ TLC, phải học **hai lần**:
   - `sitemap_index.xml` gồm `post-sitemap.xml` + `page-sitemap.xml` +
     `product-sitemap.xml`, nếu gộp hết sẽ lẫn cả bài blog và trang tĩnh.
   - Nhưng lọc "có chữ product" thôi thì vẫn kéo theo `product_cat-sitemap.xml`
     — **73 trang danh mục** `/danh-muc/...` lọt vào danh sách "URL sản phẩm"
     (559 thay vì 486). Trang danh mục không có JSON-LD Product nên tốn lượt
     fetch + gọi LLM để rồi sinh ra bản ghi rỗng. Sau khi loại taxonomy:
     **486 URL = 485 sản phẩm + 1 trang `/shop/`**, độ tin cậy 100%.
4. **Chấm điểm độ tin cậy** (`prober.py`): lấy mẫu ngẫu nhiên N URL (mặc định
   10), fetch từng URL và chạy qua bộ phát hiện trang sản phẩm. Đạt **≥ 80%**
   thì sitemap được chấp nhận làm nguồn chính.
   `lastmod` **không** được dùng làm tiêu chí quyết định — đó là giá trị site tự
   khai báo, không đảm bảo URL còn hợp lệ (case Roman: sitemap trả HTTP 200
   bình thường nhưng thiếu hẳn sản phẩm đang bán).
5. **Fallback crawl menu** (`menu_crawl.py`) nếu không có sitemap đáng tin cậy:
   duyệt link trong menu điều hướng để tìm trang danh mục ứng viên, rồi lọc
   từng trang qua bộ phát hiện lưới sản phẩm.
6. **Cache kết quả** (`cache.py`) theo domain, TTL 30 ngày, lưu ở `.cache/probe/`.

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
   KingLED — bảng "Thông số kỹ thuật" rỗng trong HTML tĩnh, chỉ được JS điền vào
   sau khi trang tải xong.
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
`Link mua hàng online`, `Tóm tắt TSKT`, `Tóm tắt ưu điểm, tính năng`,
`Link file HDSD`, `VD HDSD`, `Nội dung Ưu điểm SP`.

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

## Thêm một site đối thủ mới

Kiến trúc được thiết kế để **không phải sửa tầng 1/1.5/2**. Việc cần làm:

1. Chạy site-probing cho domain mới → xác định nguồn URL sản phẩm.
2. Kiểm tra tầng 1 có lấy đủ field không. Nếu thiếu, thêm vài `SelectorRule` vào
   `DOMAIN_FALLBACK_RULES` cho domain đó (tầng 1.5).
3. Nếu trang cần JS mới hiện thông số (case KingLED), truyền `click_selectors` /
   `wait_selector` khi gọi `fetcher.fetch()`.
4. Viết script entry point tương tự `scripts/crawl_tlc_downlight.py` để lấy danh
   sách URL theo category của site đó.

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

Fixture `tlc_blog_post.html` và `tlc_static_page.html` là 2 trang thật lấy từ
chính `post-sitemap.xml` / `page-sitemap.xml` của TLC — dùng làm mẫu "rác" đại
diện cho thứ lọt vào sitemap, để chỉnh ngưỡng của bộ phát hiện trang sản phẩm.

> **Chưa có test cho:** (a) bản ghi lỗi tầng 2 bị gắn cờ và sống sót qua vòng
> ghi/đọc Excel, (b) bộ phát hiện từ chối 2 fixture "rác" ở trên. Cả hai hành vi
> đều đã được kiểm chứng thủ công khi sửa, nhưng chưa được khoá lại bằng test tự
> động — nên thêm khi có dịp.
