# Việc cần làm

Ghi lại những thứ đã xác định được nhưng CHƯA làm, kèm số liệu đo trên trang
thật để lần sau không phải khảo sát lại từ đầu.

---

## 1. ~~Hai cột "Ưu điểm" đang bỏ trống dù trên web có dữ liệu~~ — ĐÃ LÀM

Cài đặt ở `src/crawler/extraction/advantages.py`, mô tả đầy đủ ở
[pipeline.md](pipeline.md) mục **"Tầng 1.6"** (cả bằng chứng khảo sát lẫn các
bẫy đã gặp đều nằm ở đó, không nhân bản lại ở đây).

Kết quả trên `kingled.com.vn` (549 sản phẩm, chạy 21/08/2026):
`Tóm tắt ưu điểm, tính năng` **65,6%**, `Nội dung Ưu điểm SP` **68,1%**.

**Hai điều ghi chú ban đầu hoá ra sai, giữ lại để không đi lại vết cũ:**

- *"Tìm theo từ khoá «ưu điểm» rồi nhảy tới đó"* — **không dùng được**. Trên
  trang thật mục này hầu như không tự xưng tên: KingLED gọi là "Đặc điểm nổi
  bật", TLC có trang đặt tên "Tại sao nên sử dụng phích cắm cái chịu tải", trang
  đèn COB thì **không có tiêu đề nào cả**. Cách đang chạy là gom ứng viên theo
  cấu trúc rồi chấm điểm.
- *"Roman: 0 lần xuất hiện chữ «ưu điểm» → để trống là ĐÚNG với Roman"* —
  **sai**. Roman có mục này, gọi là "Đặc điểm nổi bật của…", 5 ý thật. Kết luận
  cũ rút ra từ việc đếm đúng một cụm từ trên một trang.

---

## 2. Chưa crawl lại TLC và Roman với tầng 1.6 bản mới

Đợt 21/08 **chỉ chạy KingLED** (site có nhiều ô trống nhất). Hai site còn lại:

- `output/tlclighting_all.xlsx` (485 sản phẩm) đang là kết quả của bản tầng 1.6
  **chưa bật nhánh cụm** → 2 cột ưu điểm còn thiếu ở các trang không có tiêu đề
  mục. Chạy lại ~35 phút.
- **Roman chưa từng crawl toàn site.** Mới chỉ dùng làm fixture cho test.

> Xoá file .xlsx trước khi chạy lại, **nếu không sẽ không có gì thay đổi**: 2 cột
> ưu điểm không nằm trong `REQUIRED_FIELDS`, nên bản ghi cũ vẫn mang trạng thái
> OK và được tái sử dụng nguyên vẹn. Đây là hành vi đúng của cơ chế crawl lại có
> chọn lọc, chỉ là dễ quên.

---

## 3. Việc nhỏ hơn, chưa làm

- `scripts/verify_missing_fields.py` mới chỉ kiểm định được WooCommerce/JSON-LD
  (TLC). Chạy nó trên file KingLED sẽ báo sai vì KingLED dùng Microdata và
  không có `div.summary` — cần bổ sung đường kiểm tra cho Microdata.
- ~~Sản phẩm không niêm yết giá: cân nhắc trạng thái riêng~~ — **đã chốt: để ô
  trống, không làm gì thêm.** 144 bản ghi này thiếu giá vì site thật sự không
  niêm yết (đã kiểm chứng độc lập 12/12 mẫu), đó không phải lỗi crawl. Chấp nhận
  việc chúng bị crawl lại ở các lần chạy sau.
- Chưa có test cho: bản ghi lỗi tầng 2 sống sót qua vòng ghi/đọc Excel, và bộ
  phát hiện từ chối 2 fixture "rác" của TLC.
- 6/360 ô "Tóm tắt ưu điểm" của KingLED là mục lấy nhầm (danh sách phụ kiện,
  hoặc mục quá mỏng chỉ 1 dòng). Đã chấp nhận đánh đổi để lấy độ phủ — xem
  [pipeline.md](pipeline.md) mục "Nhánh cụm đề mục". Nếu sau này muốn siết,
  hướng khả dĩ là **loại ô chỉ có 1 dòng** (3/6 ca), rẻ và không đụng ca đúng.
