# Danh sách nhãn hiệu cần crawl

Web root là **web chính hãng của nhãn**, không phải trang đại lý — số liệu chỉ
tin được khi lấy từ nhà sản xuất. Cột ghi chú nói **nguồn URL sản phẩm** của
site đó, vì đây là thứ quyết định crawl được ngay hay phải viết thêm.

- [x] TLC — https://tlclighting.com.vn — sitemap `product-sitemap.xml`, 485 SP
- [x] dienquang — https://dienquang.com — Haravan, `/products/`, 741 SP
- [x] vinaled — https://denvinaled.vn — WooCommerce, `/san-pham/`, 668 SP
- [x] KingLED — https://kingled.com.vn — `sitemap.xml?page=Product`, 549 SP
- [x] Roman — https://roman.vn — sitemap 2021 chết 44% URL → dò qua trang danh mục, **192 SP**
- [x] Panasonic — https://panasonic.net/electricworks/lighting/vn — không sitemap (robots.txt 404) → `wlist.php` → `plist.php?lay3=` → `pspec.php?id=`, **147 SP**
- [x] Philips — https://philipsvietnam.com/ — url mới có chứa giá bán sản phẩm chính hãng
- [x] MPE — https://www.mpe.com.vn — không sitemap → dò qua trang danh mục, **180 SP**
- [x] Asia — https://www.denasia.vn — WooCommerce, `/san-pham/`, **442 SP**
- [x] Nanuco — https://www.nanoco.com.vn — Next.js, sitemap hỏng → dò qua trang danh mục, **48 SP**
- [x] VNE — https://vne-led.vn — WordPress không bật sitemap → dò qua trang danh mục, **120 SP**
- [x] Duhal — https://duhal.com.vn — 7 sitemap trong robots.txt đều 404 → dò qua trang danh mục, **615 SP**

Tổng: **6.439 sản phẩm** trong `crawl.db`, **12/12 nhãn đã crawl**.

## Nhánh không-sitemap

5 site trước đây **không crawl được**: `crawl_site.py` dừng khi probe không trả
về URL sản phẩm, mà tầng 0 chỉ biết lấy URL sản phẩm từ sitemap. Đã bổ sung
`probing/product_discovery.py` — dò URL sản phẩm từ chính trang danh mục. Chi
tiết bốn pha: [docs/pipeline.md](docs/pipeline.md) mục "Nhánh không-sitemap".

Chạy y như site có sitemap, không cần cờ gì thêm:

```bash
.venv/bin/python scripts/crawl_site.py https://vne-led.vn
```

## Hai điều đo được khi crawl thật (đợt 07/09)

**1. Dò được URL không có nghĩa là đọc được nội dung.** Cả 4 site mới đều
không có structured data sản phẩm, nên tầng 1 trả về gần như rỗng. Mỗi site
cần đúng vài dòng selector trong `extraction/css_fallback.py` — không file .py
nào mới:

| Site | Trước | Sau khi đăng ký selector |
|---|---|---|
| VNE | 120/120 mất tên và ảnh | đủ tên, ảnh, danh mục |
| Nanoco | 48/48 mất giá, 14 mất tên | **43/48 OK** |
| MPE | 90/90 mất giá và danh mục | selector đo 90/90, chờ crawl xong |
| Asia | 442/442 mất danh mục | 441/442 có danh mục thật |
| Philips | 2091/2091 mất danh mục | selector đo 300/300 |

Trong lúc làm còn phát hiện tầng 1.5 **chưa bao giờ được nối cho `ten_san_pham`**
— site nào không có structured data và không có OpenGraph thì mất tên dù tên
hiện rõ trong `<h1>`. Đã sửa, bộ trích xuất lên `v3`.

**2. Trang phẳng thì tầng dò vơ cả bài blog.** Roman và Duhal để mọi trang ở
`/<slug>.html` — sản phẩm, danh mục và bài viết cùng một hình URL. Ngưỡng 5
trường thông số cho lọt bài kỹ thuật: bài "10 thông số đèn LED cần biết" nhắc
đủ công suất, quang thông, điện áp, nhiệt độ màu, CRI.

Đã đo 7 luật lọc trên 80 trang Roman, **không luật nào sạch**:

| Luật | Giữ sản phẩm | Lọt rác |
|---|---|---|
| spec≥5 (đang dùng) | 62/62 | 18/18 |
| spec≥5 và `looks_like_single_product_page` | 62/62 | 11/18 |
| có mã model trong h1 | 41/62 | 2/18 |

Một luật trông hợp lý — "không mã **và** không giá thì không phải sản phẩm" —
đã bị loại sau khi kiểm tra: nó vứt cả `tlclighting.com.vn/san-pham/
den-duong-led-tlc-100w/` và 422 URL Philips, đều là sản phẩm thật.

Cái tách được là **cấu trúc**: sản phẩm thật chỉ nằm dưới cây danh mục. Đã trỏ
`listing_seed_urls` thẳng vào hub danh mục cho hai site này (một dòng dữ liệu
trong registry, giống Nanoco).

## Chuyện giá

Ô giá trống có hai nghĩa khác hẳn nhau, và đã đo để phân biệt:

| Site | Trang có hiện giá |
|---|---|
| VNE, Asia, Philips | **0/40** — site không niêm yết giá, ô trống là đáp án đúng |
| Nanoco | 29/30 — đọc hụt thật, đã sửa |
| MPE | 25/25 — đọc hụt thật, đã sửa |
| TLC, Roman | 0 ca hụt thật (giá thấy được là của thẻ sản phẩm liên quan) |

**Cảnh báo khi so giá giữa các đối thủ:** Nanoco niêm yết "Giá bán lẻ (**chưa
VAT**)", các site còn lại đều niêm yết giá đã gồm VAT. Cột Giá ghi nguyên con
số site công bố — tool không tự cộng 10% vào, vì cộng vào là bịa ra một con số
không site nào nói. Ai so sánh ngang hàng thì phải tự quy đổi cột này.

Nhưng `gia` nằm trong `REQUIRED_FIELDS`, nên site không niêm yết giá **không
bao giờ đạt `ok`** và mỗi lần chạy lại sẽ fetch + gọi LLM lại toàn bộ. Đây là
việc cần quyết: hiện chưa phân biệt được "site không công bố giá" với "chưa
lấy được giá".

## Hạ tầng

- **DeepSeek hết tiền** (`402 Insufficient Balance`) — không còn đường dự phòng.
  Vertex chỉ bị chặn theo phút nên retry vẫn qua, nhưng khi cạn 6 lần thử là
  mất hẳn `tags` của bản ghi đó (Roman 7 ca, VNE 1 ca).
- Sửa xong selector thì **không phải crawl lại**: `scripts/reextract.py` chạy
  trên HTML đã lưu, 0 request mạng, 0 quota LLM.

## Notes
- xử lý vấn đề retry thì nên tăng timeout lên vì chỉ muốn sử dụng mỗi vertex thôi. Tạm gỡ deepseek
- Tìm phương hướng xử lý cho tất cả các web trong trường hợp có và không có sitemap, tìm hiểu crawl4ai có áp dụng được không