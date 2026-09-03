## Context

Pipeline hiện tại (`competitor-product-crawler` + `site-wide-parallel-crawl`) chạy được toàn site và đã cho ra dữ liệu thật:

| Site | Sản phẩm | HTML/trang | gzip | Tổng nén |
|---|---|---|---|---|
| kingled.com.vn | 549 | 152 KB | 17 KB (8,8×) | 9,3 MB |
| tlclighting.com.vn | 485 | 222 KB | 47 KB (4,8×) | 22,8 MB |
| roman.vn | chưa crawl | 549 KB | 140 KB (3,9×) | ~70 MB (ước) |

Nhưng HTML bị vứt ngay sau khi trích xuất, và toàn bộ trạng thái nằm trong file `.xlsx`. Tầng 1.6 (`extraction/advantages.py`) — tầng non nhất, thuần heuristic, độ phủ 65,6%/68,1% với 6/360 ô lấy nhầm — vì thế không có vòng lặp thí nghiệm nào rẻ hơn 35 phút.

## Goals / Non-Goals

**Goals:**
- Một kho HTML để chạy lại bộ trích xuất **nhanh hơn một bậc** so với crawl lại, và để **so sánh hai lần trích xuất** trên cùng dữ liệu (biết mình vá được mấy ô và làm hỏng mấy ô). Đo thật sau khi cài đặt: **203 giây cho 549 trang** (370 ms/trang) so với ~35 phút của một lượt crawl — **10×**, và tốn 0 request mạng, 0 quota LLM. Con số này thấp hơn kỳ vọng ban đầu ("vài giây"): mỗi trang bị BeautifulSoup phân tích lại **bốn lần** — `extract_structured_data`, `apply_css_fallback`, `extract_advantages`, `extract_spec_text` mỗi hàm tự dựng `soup` riêng. Gộp lại thành một lần phân tích là tối ưu hiển nhiên nhưng nằm ngoài phạm vi change này.
- Phân biệt được thay đổi đến từ site với thay đổi đến từ code mình.
- Giữ nguyên tuyệt đối hợp đồng đầu ra Excel — bên nhận không phải chỉnh gì.
- Đưa được HTML/text của trang tới tay người xử lý tay, trong đúng file họ đang mở.

**Non-Goals:**
- Không dựng service/API. Đây là một file SQLite cạnh dự án, một tiến trình dùng.
- Không làm giao diện xem dữ liệu. Truy vấn bằng SQL là đủ ở quy mô này.
- Không đổi thuật toán trích xuất trong change này — chỉ dựng hạ tầng để lần sau sửa nó có căn cứ.
- Không lưu ảnh/tài nguyên của trang, chỉ lưu tài liệu HTML.

## Decisions

### 1. SQLite, một file, không phải Postgres

Quy mô đầy đủ ~1500 sản phẩm và ~100 MB blob. Một tiến trình crawl duy nhất ghi. SQLite trong thư viện chuẩn Python, không cài đặt gì, backup bằng `cp`. Postgres chỉ đáng khi có nhiều tiến trình ghi đồng thời hoặc nhiều người dùng — không phải tình huống ở đây.

**Ràng buộc kèm theo**: `pipeline.py` chạy nhiều worker song song. Bật `PRAGMA journal_mode=WAL` và **chỉ một luồng được ghi**. Kiến trúc hiện tại đã sẵn sàng cho việc đó, nhưng **không** theo mô hình `asyncio` — change `site-wide-parallel-crawl` mới chỉ là đề xuất (0/34 task). Thực tế `_crawl_pipelined` chạy bất đối xứng: **fetch tuần tự trên main thread**, `ThreadPoolExecutor` chỉ lo tầng 1/1.5/2. Điểm ghi đơn luồng vì thế là hàm `harvest()` — nó chạy duy nhất trên main thread, thu hoạch future theo đúng thứ tự submit, và đang là nơi gọi `write_records_to_excel`. Việc ghi DB đặt đúng vào đó. Snapshot thì ghi sớm hơn, ngay sau `fetcher.fetch()` — cũng trên main thread.

### 2. Hai lịch sử, hai bảng — không gộp vào một cột `crawled_at`

Đây là quyết định trung tâm của change này.

```
      đối thủ đổi trang                      MÌNH đổi code
            │                                      │
            ▼                                      ▼
   ┌──────────────────┐                  ┌────────────────────┐
   │  page_snapshots  │  1:N             │    extractions     │
   │  1 dòng / FETCH  │─────────────────▶│  1 dòng / TRÍCH    │
   │  html_gz BLOB    │                  │  extractor_version │
   └──────────────────┘                  └────────────────────┘
                                                   │ 1:N
                                          ┌────────────────────┐
                                          │   product_tags     │
                                          └────────────────────┘
```

Nếu chỉ có một bảng `products` ghi đè, thì khi một giá trị khác đi so với lần trước, **không phân biệt được** "đối thủ hạ giá" với "mình vừa sửa parser". Tách ra thì phân biệt được ngay: snapshot đổi → họ đổi; snapshot y nguyên mà extraction đổi → mình đổi.

Và đây chính là thứ khiến "xử lý sau" khả thi: *xử lý sau* nghĩa là chạy lại bộ trích xuất trên HTML đã lưu, tức trích xuất phải là **một thao tác riêng, chạy lại được, có phiên bản**.

`products` **là một VIEW**, không phải bảng: "bản trích xuất mới nhất trên snapshot mới nhất của mỗi URL". View luôn đúng theo định nghĩa, không có nguy cơ lệch với bảng nguồn như một bảng vật chất hoá.

**Alternative đã loại**: một bảng `products` ghi đè + một bảng `html_snapshots` phụ. Rẻ hơn nhưng mất khả năng chạy lại-so-sánh trích xuất, tức mất đúng lý do chính của change.

### 3. Lưu HTML mọi trang, không chỉ trang hỏng

Phương án "chỉ lưu khi trích xuất hỏng" tiết kiệm được ~2/3 dung lượng nhưng bỏ mất hai khả năng:
- Ô **sai mà tưởng đúng** không tự khai báo — pipeline coi nó là thành công nên sẽ không lưu HTML, đúng ca cần soi nhất lại là ca không có dữ liệu để soi.
- Không có đối chứng cho hồi quy: sửa heuristic xong không biết 1034 ô đang đúng có bị hỏng cái nào không.

Giá phải trả là ~70 MB thêm. Chấp nhận.

### 4. Khoá chính là `url` nguyên văn — không chuẩn hoá

`sites/registry.py:78-88` đã ghi rõ vì sao không được cắt dấu `/` cuối: đó là quy ước riêng của từng site (486/486 URL của TLC có, 0 URL của KingLED có), và cắt nó đi là **đổi danh tính bản ghi** khiến cơ chế crawl-lại-có-chọn-lọc mất khớp. Ràng buộc đó đi thẳng vào DB, kèm chú thích ngay tại DDL — vì đây đúng loại thứ mà sáu tháng nữa sẽ có người "dọn dẹp cho gọn".

### 5. DB dùng tên sạch; `COLUMNS` giữ nguyên vai trò lớp kết xuất

20 cột trong `record/schema.py` là **định dạng bàn giao**, không phải mô hình dữ liệu — bằng chứng là `" category 1 "` và `"Thông số kỹ thuật "` mang cả khoảng trắng thừa của file gốc, chép nguyên văn *có chủ đích*. Bê thẳng vào SQL là nhập khẩu vĩnh viễn tật của một file Excel người khác làm. `ProductRecord` đã là mô hình sạch; DB nằm **dưới** nó, `COLUMNS` vẫn là bảng ánh xạ khi ghi ra file.

### 6. Tags: bảng key-value, không phải một cột JSON

Spec `llm-attribute-normalization` đã chốt "schema thuộc tính linh hoạt theo site/category" — số lượng và tên key khác nhau giữa các sản phẩm. Dạng key-value giữ nguyên tính linh hoạt đó mà vẫn truy vấn được ("bao nhiêu SP công bố CRI?", "phân bố nhiệt độ màu của đối thủ"). Cột JSON + `json_extract` cũng chạy nhưng khó dùng hơn hẳn, và phân tích thuộc tính đối thủ chính là mục đích cuối của dự án. Khi ghi ra Excel thì gộp ngược lại thành `json.dumps` như hiện nay.

### 7. HTML **không** vào ô Excel — text trang thì có

Đo thật:

```
  HTML 1 trang KingLED  = 146.199 ký tự
  Giới hạn 1 ô Excel    =  32.767 ký tự
  openpyxl khi ghi vượt : "thành công", KHÔNG cảnh báo
  đọc lại               : 32.767 ký tự — mất 78% trong im lặng
```

Ô cắt cụt trông y hệt ô lành, nên đây là lỗi âm thầm — đúng loại lỗi repo này đã gặp. Nhưng **text** của trang, sau khi bỏ `script/style/nav/footer`, thì lọt:

| | HTML | text đã dọn |
|---|---|---|
| kingled (rendered) | 146.199 | **16.582** ✓ |
| tlc_product | 217.007 | **9.472** ✓ |
| roman_product | 544.985 | **6.244** ✓ |

Và text mới là thứ người xử lý tay cần — họ cần *đọc* để tìm mục ưu điểm rồi copy, không ai dò mục ưu điểm trong 146 KB mã HTML nằm trong một ô bảng tính.

**Quyết định**: ô chứa text đã dọn, cắt ở **32.000 ký tự** kèm hậu tố `[... đã cắt, xem file .html đính kèm]` — cắt **có báo**, ngược hẳn với cắt im lặng của openpyxl. HTML nguyên bản xuất ra file `.html` cạnh file Excel, ô có thêm cột đường dẫn để mở bằng trình duyệt và xem đúng trang như lúc crawl.

**Ngoại lệ đã đo**: `kingled_product.html` (bản *chưa* render) cho ra **691.236 ký tự** text — có khối dữ liệu lớn không nằm trong `<script>`. Ngưỡng cắt vì thế là bắt buộc, không phải phòng xa.

### 8. Sheet riêng, không phải cột riêng

Nhét text toàn trang vào ô `Nội dung Ưu điểm SP` thì bên nhận không phân biệt được *"đây là mục ưu điểm thật"* với *"đây là cả trang, tự tìm lấy"* — đúng loại lỗi vừa vá tuần trước (bảng thông số bị ghi vào cột ưu điểm). Thêm cột mới thì phá vỡ hợp đồng 20 cột khớp tuyệt đối.

```
 kingled.com.vn.xlsx
 ├── Đèn LED âm trần        ┐
 ├── Đèn LED panel          ├─ 20 cột, đúng khuôn, GHÉP THẲNG được
 ├── ... (24 sheet)         ┘   SP hỏng vẫn có mặt, 2 ô ưu điểm ĐỂ TRỐNG
 │                              (để trống mới đúng — không bịa dữ liệu)
 └── ⚠ Cần xử lý tay        ── url │ lý do │ text toàn trang │ file .html

 kingled.com.vn_html/
 └── den-panel-onyx-48w.html
```

Sản phẩm hỏng có mặt ở **cả hai chỗ**: trên sheet danh mục để file vẫn là bản giao nộp hoàn chỉnh, trên sheet cảnh báo kèm nguyên liệu để xử lý. Cột `lý do` lấy thẳng từ `uu_diem_nguon` — người xử lý biết ngay nên soi kỹ hay chỉ liếc.

`excel_reader` hiện gộp phẳng **mọi** sheet theo URL (`excel_reader.py:36-38`), nên phải biết bỏ qua sheet cảnh báo.

### 9. `uu_diem_nguon` — nguồn gốc trích xuất, gần như miễn phí

`extract_advantages` đã biết nhánh nào thắng (từ khoá / la bàn LLM / cụm đề mục) rồi vứt đi, chỉ trả 2 chuỗi. Giữ lại thì:
- "6 ô sai nằm đâu" thành `WHERE uu_diem_nguon = 'cluster'` thay vì mở tay 360 ô.
- Món nợ kỹ thuật có ý thức ở nhánh cụm (`docs/todo.md` mục 3) trở nên **đo đếm được**.
- Cột `lý do` của sheet cảnh báo có sẵn nội dung.

### 10. Lưu cả LA BÀN, không chỉ nguồn gốc

*(Phát hiện khi cài đặt, không có trong bản thiết kế đầu.)* Ghi lại `uu_diem_nguon` là chưa đủ để chạy lại trích xuất trung thực. Nhánh `anchor` phụ thuộc vào **một dòng** do tầng 2 (LLM) chỉ ra (quy tắc 9 của prompt), và dòng đó chỉ tồn tại trong bộ nhớ suốt lượt crawl rồi biến mất.

Không lưu nó thì mỗi lần chạy lại — vốn **không gọi LLM** — sẽ mất sạch nhánh `anchor`, và `diff_extractions` báo hồi quy ở mọi ô từng tìm thấy nhờ la bàn, dù người ta chẳng sửa gì liên quan. Phép so mất ý nghĩa đúng ở chỗ nó cần có ý nghĩa nhất.

**Quyết định**: thêm cột `extractions.uu_diem_la_ban` (và field nội bộ cùng tên trên `ProductRecord`, đi cùng đường với `uu_diem_nguon` — dữ liệu vận hành, không xuất ra Excel).

## Risks / Trade-offs

- **Dữ liệu đã có không có snapshot.** 1034 sản phẩm trong `output/*.xlsx` được nhập vào DB dưới dạng `extractions` với `snapshot_id = NULL` và `extractor_version = 'imported-xlsx'`. Chúng **không** chạy lại trích xuất được (không có HTML). Kho HTML chỉ bắt đầu tích luỹ từ lần crawl kế tiếp. Chấp nhận: không mất dữ liệu cũ, và lần crawl lại đầu tiên sẽ lấp đầy.
- **`database is locked`** nếu vô ý ghi từ nhiều worker. Giảm thiểu bằng WAL + một luồng ghi duy nhất, và một test chạy nhiều worker giả để bắt sớm.
- **~100 MB không vào git.** Mất tính "clone về là có dữ liệu". Đổi lại repo không phình. Cần ghi rõ trong README cách dựng lại DB từ `output/*.xlsx`.
- **Hai nguồn sự thật trong giai đoạn chuyển tiếp.** Trong lúc `excel_reader` còn tồn tại cho việc import, có nguy cơ ai đó vẫn dùng nó làm nguồn trạng thái. Giảm thiểu bằng cách đổi tên hàm thành `import_legacy_xlsx` để không còn đọc như một API chung.
- **Nén zlib chứ không phải zstd.** zlib có sẵn trong thư viện chuẩn; zstd nén tốt hơn ~20-30% nhưng phải thêm phụ thuộc. Ở mức 100 MB thì không đáng đánh đổi.

## Migration Plan

1. Dựng schema DB (không đụng code đang chạy).
2. Nhập `output/kingled.com.vn.xlsx` + `output/tlclighting_all.xlsx` → 1034 dòng `extractions` với `snapshot_id = NULL`.
3. Đấu DB vào pipeline **song song** với đường ghi Excel hiện có — chạy một lượt, đối chiếu file Excel sinh từ DB với file sinh theo đường cũ, phải khớp từng ô.
4. Chuyển nguồn của crawl-lại-có-chọn-lọc từ `excel_reader` sang DB.
5. Bỏ đường ghi Excel cũ; `write_records_to_excel` chỉ còn được gọi bởi bước kết xuất.

Bước 3 là điểm không thể bỏ: nó biến "khuôn đầu ra không đổi" từ một lời hứa thành một phép so sánh.

## Open Questions

- Roman chưa từng crawl toàn site nên số 500 sản phẩm/70 MB chỉ là ước từ một trang mẫu. Con số thật có thể lệch đáng kể.
- Có nên lưu cả HTML của trang danh mục/sitemap (phục vụ gỡ lỗi khâu phát hiện URL), hay chỉ trang sản phẩm? Bản thiết kế này chỉ lưu trang sản phẩm.
- Ngưỡng dọn dẹp snapshot cũ: giữ tất cả, hay giữ N bản gần nhất mỗi URL? Chưa cần quyết cho tới khi DB thật sự lớn.
