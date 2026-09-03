## 1. Schema & lớp truy cập

- [x] 1.1 Viết `src/crawler/store/schema.sql` (DDL): `sites`, `page_snapshots`, `extractions`, `product_tags`, và VIEW `products` = bản trích xuất mới nhất trên snapshot mới nhất mỗi URL
- [x] 1.2 Ghi ngay tại DDL chú thích vì sao `url` **không** được chuẩn hoá dấu `/` cuối (dẫn `sites/registry.py:78-88`) — đây là thứ dễ bị "dọn cho gọn" về sau
- [x] 1.3 Viết `src/crawler/store/db.py`: mở kết nối, bật `PRAGMA journal_mode=WAL` + `foreign_keys=ON`, tạo schema nếu chưa có, đường dẫn DB lấy từ `config.py`
- [x] 1.4 Viết hàm nén/giải nén HTML (zlib) kèm test round-trip trên fixture thật, xác nhận tỉ lệ nén nằm trong khoảng đã đo (3,9×-8,8×)
- [x] 1.5 Viết test: VIEW `products` trả đúng bản mới nhất khi một URL có nhiều snapshot và nhiều extraction đan xen

## 2. Ghi dữ liệu từ pipeline

- [x] 2.1 Ghi snapshot ngay sau khi fetch thành công, **trước** khi trích xuất — để trang trích xuất hỏng vẫn có HTML
- [x] 2.2 Ghi `extractions` + `product_tags` sau khi chạy xong tầng 1/1.5/1.6/2, gắn `snapshot_id` và `extractor_version`
- [x] 2.3 Đặt việc ghi DB vào đúng chỗ đang gọi checkpoint (một luồng/coroutine writer duy nhất), không ghi từ worker
- [x] 2.4 Fetch thất bại: ghi `extractions` trạng thái lỗi kèm lý do, **không** tạo snapshot rỗng
- [x] 2.5 Viết test chạy nhiều worker giả hoàn thành đồng thời → không mất bản ghi, không `database is locked`
- [x] 2.6 Viết test: dừng giữa chừng rồi chạy lại → bản ghi đã ghi còn nguyên, chỉ crawl phần thiếu

## 3. Nguồn gốc trích xuất cho hai cột ưu điểm

- [x] 3.1 Sửa `extraction/advantages.py` để trả về **nhánh thắng cuộc** cùng với 2 chuỗi (`keyword` / `anchor` / `cluster` / `none`) — thông tin này đã có sẵn trong `extract_advantages`, chỉ đang bị bỏ đi
- [x] 3.2 Không đổi thuật toán chấm điểm trong task này; mọi test hiện có ở `tests/test_advantages.py` phải xanh nguyên
- [x] 3.3 Ghi giá trị đó vào cột `uu_diem_nguon` của `extractions`
- [x] 3.4 Viết test: mỗi nhánh định vị cho ra đúng giá trị nguồn gốc tương ứng (dùng lại fixture của các test nhánh đã có)

## 4. Nhập dữ liệu đã có

- [x] 4.1 Đổi tên `excel_reader.load_existing_records` → `import_legacy_xlsx`, để nó không còn đọc như một API trạng thái dùng chung
- [x] 4.2 Nhập vào kho dạng `extractions` với `snapshot_id = NULL`, `extractor_version = 'imported-xlsx'`
- [x] 4.3 Chạy nhập thật `output/kingled.com.vn.xlsx` (549) + `output/tlclighting_all.xlsx` (485), xác nhận đủ 1034 bản ghi và tags giải mã đúng
- [x] 4.4 Bộ chạy lại trích xuất bỏ qua bản ghi không có snapshot, báo rõ số lượng bị bỏ qua thay vì lỗi

## 5. Chạy lại trích xuất trên snapshot đã lưu

- [x] 5.1 Viết `scripts/reextract.py <domain>`: đọc mọi snapshot mới nhất của domain → chạy lại tầng 1/1.5/1.6 (không gọi LLM, dùng lại `muc_uu_diem` đã lưu làm la bàn) → ghi `extractions` mới
- [x] 5.2 Xác nhận không phát sinh request mạng nào (test chặn tầng fetch, gọi tới là fail)
- [x] 5.3 Viết `scripts/diff_extractions.py`: so hai `extractor_version` trên cùng tập snapshot, báo số ô **vá được** và số ô **làm hỏng** cho từng cột
- [x] 5.4 Đo thời gian chạy lại thật trên 549 snapshot KingLED — mục tiêu là giây/phút, đối chiếu với baseline 35 phút của một lượt crawl lại

## 6. Kết xuất Excel từ kho dữ liệu

- [x] 6.1 Viết `scripts/export_excel.py <domain>`: đọc VIEW `products` → dựng `ProductRecord` → gọi `write_records_to_excel`
- [x] 6.2 Giữ nguyên `COLUMNS` làm lớp ánh xạ; DB dùng tên sạch, không mang khoảng trắng thừa của khuôn tham chiếu vào schema
- [x] 6.3 Gộp ngược `product_tags` thành chuỗi JSON cho cột `Tags`, khớp đúng định dạng hiện hành
- [x] 6.4 Viết test round-trip: nhập một file `.xlsx` vào kho rồi xuất lại → hai file khớp từng ô trên mọi sheet sản phẩm

## 7. Sheet cảnh báo & file HTML đính kèm

- [x] 7.1 Thêm sheet `⚠ Cần xử lý tay`: url │ lý do │ text toàn trang │ đường dẫn file `.html`
- [x] 7.2 Sản phẩm cần xử lý tay vẫn có mặt ở sheet danh mục với 2 ô ưu điểm **để trống** — không ghi text/HTML/ghi chú vào 2 cột đó
- [x] 7.3 Sinh text trang bằng cách bỏ `script/style/nav/aside/footer/header/noscript`, cắt ở **32.000** ký tự kèm hậu tố `[... đã cắt, xem file .html đính kèm]`
- [x] 7.4 Ghi HTML nguyên bản ra `output/<domain>_html/<slug>.html`, ô đường dẫn trỏ tới đó; bản ghi nhập từ file cũ (không snapshot) để ô đường dẫn trống
- [x] 7.5 Cho `import_legacy_xlsx` bỏ qua sheet cảnh báo — hiện nó gộp phẳng **mọi** sheet theo URL (`excel_reader.py:36-38`)
- [x] 7.6 Viết test bảo vệ giới hạn ô: dựng bản ghi có text dài hơn 32.767 ký tự → file sinh ra không có ô nào chạm giới hạn, và ô bị cắt mang dấu hiệu nhìn thấy được
- [x] 7.7 Viết test cho ca ngoại lệ đã đo: trang cho ra 691.236 ký tự text (`kingled_product.html` bản chưa render) không làm hỏng file xuất

## 8. Chuyển nguồn trạng thái sang DB

- [x] 8.1 Chuyển việc xác định "URL nào cần crawl lại" từ `import_legacy_xlsx` sang truy vấn kho dữ liệu
- [x] 8.2 Viết test: xoá file `.xlsx` khỏi output → lượt crawl tiếp theo vẫn nhận ra sản phẩm đã xong, không crawl lại
- [x] 8.3 Bỏ khỏi `docs/todo.md` cái bẫy "xoá file .xlsx trước khi chạy lại" — nó biến mất cùng cơ chế cũ
- [x] 8.4 `write_records_to_excel` chỉ còn được gọi từ bước kết xuất, không còn là checkpoint giữa lượt crawl

## 9. Kiểm chứng thật

- [x] 9.1 **Chạy song song hai đường** một lượt: ghi cả DB lẫn Excel theo cách cũ, đối chiếu file sinh từ DB với file sinh theo đường cũ — phải khớp từng ô. Không qua bước này thì không sang bước 8
      *(XONG trên dữ liệu thật: crawl 485 SP TLC ghi cả hai đường → file từ kho vs file đường cũ **khớp 521/521 dòng, 36/36 sheet, 0 lệch**.)*
- [x] 9.2 Crawl lại thật `tlclighting.com.vn` (485 SP, đang nợ ở `docs/todo.md` mục 2) qua đường mới, xác nhận kho có đủ 485 snapshot
      *(crawl thật 03/09: 485 SP / 32,8 phút / 485 snapshot.)*
- [x] 9.3 Đo dung lượng DB thật sau 2 site, đối chiếu với ước tính 32 MB
      *(đo thật: 485 snapshot TLC = **22,5 MB** HTML nén (4,7×), file `crawl.db` **25,4 MB**. Ước tính cho TLC là 22,8 MB — khớp.)*
- [x] 9.4 Chạy `reextract` + `diff_extractions` trên KingLED để lấy con số nền: hiện có bao nhiêu ô ưu điểm, nguồn gốc phân bố ra sao — đây là baseline cho mọi chỉnh sửa `advantages.py` về sau
      *(chạy trên **TLC** chứ không phải KingLED — KingLED chưa có snapshot nào, bản ghi của nó nhập từ .xlsx cũ. Kết quả: 485 snapshot, diff v1 vs v1-rerun = **0 đổi** → đường chạy lại tái tạo chính xác lượt crawl, kể cả nhánh `anchor`. Baseline nguồn gốc: anchor 366 / keyword 109 / cluster 1 / none 9.)*
- [x] 9.5 Mở tay 10 sản phẩm trên sheet cảnh báo, xác nhận text trong ô đủ để tìm ra mục ưu điểm mà không cần mở file `.html`
      *(soi 10/10 dòng: text trong ô 6.513–8.959 ký tự, đủ đọc. **Phát hiện ngay 1 ca bắt trượt thật** — tiêu đề mục nằm trong `<p>`; 8/9 ca còn lại site thật sự không có mục. Ghi vào docs/todo.md.)*

## 10. Dọn dẹp

- [x] 10.1 Thêm `crawl.db*` (kể cả `-wal`/`-shm`) và `output/*_html/` vào `.gitignore`
- [x] 10.2 Ghi vào README cách dựng lại DB từ `output/*.xlsx` (vì DB không nằm trong git)
- [x] 10.3 Cập nhật `docs/pipeline.md`: thêm mục kho dữ liệu, sửa mô tả bước cuối từ "ghi Excel" thành "kết xuất Excel từ kho"
