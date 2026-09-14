## Why

Hiện tại file `.xlsx` vừa là **bản giao nộp** vừa là **nơi lưu trữ duy nhất**. Việc gộp hai vai trò đó vào một định dạng bảng tính đang chặn ba việc, cả ba đều đo được:

**1. Không thí nghiệm được.** HTML crawl về bị vứt ngay sau khi trích xuất. Muốn thử một chỉnh sửa trong `extraction/advantages.py` thì phải crawl lại toàn site — **~35 phút/site** (`docs/todo.md` mục 2). Với một module mà bản chất là chỉnh heuristic theo dữ liệu thật, vòng lặp 35 phút là quá đắt để lặp.

**2. Không đo được cái sai.** Hai cột ưu điểm đạt độ phủ 65,6% / 68,1% trên KingLED, và **6/360 ô là mục lấy nhầm** (danh sách phụ kiện, mục "Cấu tạo đèn"). Con số 6 đó có được bằng cách mở tay từng ô. Không có HTML lưu lại thì không đối chiếu lại được, và quan trọng hơn: sửa heuristic xong **không biết mình vừa làm hỏng bao nhiêu ô đang đúng** — ô sai trông y hệt ô đúng, `_score_candidate` chỉ trả về ứng viên điểm cao nhất chứ không tự khai là sai.

**3. Không phân biệt được "đối thủ đổi" với "code mình đổi".** Excel chỉ giữ trạng thái mới nhất. Khi giá một sản phẩm khác đi so với lần chạy trước, không có cách nào biết đó là đối thủ hạ giá hay là mình vừa sửa `css_fallback` nên đọc ra số khác. Với một dự án tên `rivals_crawl`, đây là dữ liệu có giá trị nhất mà lại **không tái tạo lại được** nếu đã mất.

Ngoài ra, cơ chế crawl-lại-có-chọn-lọc đang dựa vào việc đọc ngược file Excel (`excel_reader.load_existing_records`) và kèm một cái bẫy đã phải ghi vào tài liệu: *"xoá file .xlsx trước khi chạy lại, nếu không sẽ không có gì thay đổi"* — vì 2 cột ưu điểm không nằm trong `REQUIRED_FIELDS` nên bản ghi cũ vẫn mang trạng thái OK.

## What Changes

- **Thêm một CSDL SQLite làm nguồn sự thật** (`crawl.db`, 1 file), thay thế vai trò *lưu trữ* của Excel. Excel **không bị bỏ** — nó trở thành bước cuối của pipeline: kết xuất từ DB ra đúng khuôn 20 cột hiện hành.
- **Tách hai lịch sử khác bản chất thành hai bảng**: `page_snapshots` (1 dòng / 1 lần **fetch**, kèm HTML nén) và `extractions` (1 dòng / 1 lần **trích xuất** trên một snapshot, kèm `extractor_version`). `products` là một VIEW "bản trích xuất mới nhất trên snapshot mới nhất". Nhờ vậy phân biệt được *site đổi* với *code mình đổi*, và chạy lại bộ trích xuất trên HTML đã lưu mà không cần fetch.
- **Lưu HTML của MỌI trang** (không chỉ trang trích xuất hỏng), nén zlib. Đo thật: tỉ lệ nén 8,8× (KingLED) / 4,8× (TLC) / 3,9× (Roman) → ~32 MB cho 1034 sản phẩm đã có, ~100 MB nếu tính cả Roman.
- **Ghi lại nguồn gốc của 2 cột ưu điểm** (`uu_diem_nguon`: `keyword` / `anchor` / `cluster` / `none`). `extract_advantages` hiện **đã biết** nhánh nào thắng rồi vứt đi. Giữ lại thì câu hỏi "6 ô sai nằm đâu" thành một câu truy vấn thay vì một buổi mở tay 360 ô.
- **Tags tách thành bảng key-value** (`product_tags`) thay vì `json.dumps` vào một ô, để trả lời được chính câu hỏi cuối của dự án: đối thủ công bố những thuộc tính nào, phân bố ra sao.
- **Sản phẩm không trích được mục ưu điểm** xuất hiện ở **cả hai chỗ** trong file Excel: trên sheet danh mục với 2 ô ưu điểm **để trống** (file vẫn ghép thẳng được vào khuôn tham chiếu), và trên một sheet mới `⚠ Cần xử lý tay` kèm **toàn văn text trang** + đường dẫn tới file `.html` nguyên bản để mở bằng trình duyệt.
- **Nhập dữ liệu đã có** từ `output/*.xlsx` (1034 sản phẩm) vào DB để không phải crawl lại từ đầu.
- **BREAKING**: `excel_reader.load_existing_records` không còn là cơ chế xác định "bản ghi nào cần crawl lại" — DB đảm nhận. File Excel trở thành đầu ra một chiều.

## Capabilities

### New Capabilities
- `crawl-data-store`: CSDL SQLite lưu snapshot HTML, kết quả trích xuất có phiên bản, tags dạng key-value và nguồn gốc trích xuất; là nguồn sự thật cho crawl-lại-có-chọn-lọc và cho việc chạy lại bộ trích xuất trên HTML đã lưu.
- `excel-export-from-store`: Bước cuối pipeline — kết xuất từ DB ra file `.xlsx` giữ nguyên khuôn 20 cột, kèm sheet cảnh báo và file HTML đính kèm cho các sản phẩm cần xử lý tay.

### Modified Capabilities
(không có — `product-record-schema` thuộc change `competitor-product-crawler` chưa archive nên chưa tồn tại như spec chính thức trong `openspec/specs/` để tạo delta. Thay đổi vai trò của `excel_reader` được mô tả trong capability mới `excel-export-from-store`.)

## Impact

- **File mới**: `src/crawler/store/` (schema DDL, lớp truy cập, import từ Excel), `scripts/export_excel.py`, `scripts/reextract.py` (chạy lại trích xuất trên snapshot đã lưu).
- **File bị ảnh hưởng**: `src/crawler/pipeline.py` (ghi vào DB thay vì gom list trong bộ nhớ; checkpoint thành commit), `src/crawler/record/excel_writer.py` (nhận dữ liệu từ DB, thêm sheet cảnh báo), `src/crawler/record/excel_reader.py` (thôi vai trò nguồn trạng thái, giữ lại cho việc import một lần), `src/crawler/extraction/advantages.py` (trả về thêm nhánh thắng cuộc).
- **Không đổi khuôn đầu ra**: 20 cột, đúng tên (kể cả khoảng trắng thừa `" category 1 "`), đúng thứ tự, mỗi loại sản phẩm 1 sheet — giữ nguyên như hiện tại.
- **`.gitignore`**: `crawl.db` (~100 MB) và thư mục HTML đính kèm phải nằm ngoài git. `output/*.xlsx` giữ nguyên hiện trạng.
- **Giới hạn cứng đã đo và phải thiết kế quanh nó**: 1 ô Excel tối đa **32.767 ký tự**; HTML một trang KingLED là **146.199 ký tự**; `openpyxl` ghi vượt hạn mà **không báo lỗi**, đọc lại được 32.767 ký tự như thể bình thường. Vì vậy HTML **không thể** nằm trong ô Excel.
