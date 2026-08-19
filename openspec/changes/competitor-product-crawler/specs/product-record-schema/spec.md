## ADDED Requirements

### Requirement: Field chuẩn của bản ghi sản phẩm
Bản ghi sản phẩm đầu ra SHALL giữ ĐẦY ĐỦ khuôn field của `product_Metadata (1).xlsx` (sheet "2. LED Downlight"), gồm cả cột mà site đối thủ không có dữ liệu tương đương: STT, Product_ID, Tên sản phẩm, Mã Sản Phẩm, Mã SAP, category 1, category 2, category 3, Tags, Giá, Giá đối chiếu, Link sản phẩm, Link ảnh sản phẩm, Link mua hàng online, Tóm tắt TSKT, Tóm tắt ưu điểm/tính năng, Thông số kỹ thuật, Link file HDSD, VD HDSD, Nội dung Ưu điểm SP. Cột không lấy được dữ liệu SHALL để trống, KHÔNG được loại khỏi khuôn.

#### Scenario: Tạo 1 bản ghi từ kết quả crawl
- **WHEN** pipeline crawl hoàn tất trích xuất cho 1 sản phẩm
- **THEN** bản ghi sinh ra chứa đúng và đủ tập field nêu trên, theo đúng thứ tự của khuôn tham chiếu

#### Scenario: Site nguồn không có dữ liệu cho 1 cột của khuôn tham chiếu
- **WHEN** site đối thủ không công bố gì tương ứng với 1 cột (vd `Giá đối chiếu`, `VD HDSD`)
- **THEN** cột đó vẫn xuất hiện trong file kết quả với ô để trống, và việc để trống KHÔNG bị coi là crawl lỗi/thiếu sót

### Requirement: Giá có 3 trạng thái
Field `Giá` SHALL hỗ trợ 3 trạng thái: giá trị số cụ thể, chuỗi literal `"Liên hệ"`, hoặc null — 3 trạng thái này mang ý nghĩa khác nhau và không được gộp lẫn nhau.

#### Scenario: Trang nguồn hiển thị giá cụ thể
- **WHEN** trang sản phẩm nguồn hiển thị 1 mức giá bằng số
- **THEN** field `Giá` lưu giá trị số đó

#### Scenario: Trang nguồn không công khai giá
- **WHEN** trang sản phẩm nguồn hiển thị rõ ràng rằng giá chỉ cung cấp khi liên hệ (vd chữ "Liên hệ" thay cho số tiền)
- **THEN** field `Giá` lưu chuỗi literal `"Liên hệ"`

#### Scenario: Không xác định được giá do lỗi crawl
- **WHEN** việc trích xuất giá cho 1 sản phẩm thất bại vì lỗi kỹ thuật (không phải do site không công khai giá)
- **THEN** field `Giá` lưu null, phân biệt với trường hợp `"Liên hệ"`

### Requirement: Field optional theo từng site
Các field `Mã SAP`, `Link mua hàng online`, `Link file HDSD`, `Giá đối chiếu`, `VD HDSD` SHALL cho phép null khi site nguồn không có tương đương, và việc null ở các field này KHÔNG được coi là crawl lỗi/thiếu sót.

#### Scenario: Site không có link sàn TMĐT khác
- **WHEN** sản phẩm trên site nguồn không có liên kết tới sàn TMĐT khác (vd Shopee)
- **THEN** field `Link mua hàng online` lưu null và bản ghi KHÔNG bị gắn cờ là thiếu dữ liệu/lỗi

### Requirement: Category giữ nguyên theo site nguồn
Các field `category 1`, `category 2`, `category 3` SHALL lưu nguyên breadcrumb/danh mục của chính site nguồn, không được ánh xạ sang bất kỳ taxonomy nào khác (kể cả taxonomy tham chiếu từ rangdong).

#### Scenario: Site nguồn chỉ có 2 cấp category
- **WHEN** breadcrumb của site nguồn chỉ có 2 cấp danh mục (không có cấp thứ 3)
- **THEN** `category 1` và `category 2` lưu đúng 2 cấp đó, `category 3` lưu null, và không có việc ánh xạ hay suy diễn thêm cấp thứ 3 từ taxonomy khác

### Requirement: Xuất ra 1 file Excel riêng theo từng site, mỗi loại sản phẩm 1 sheet
Hệ thống SHALL xuất bản ghi sản phẩm ra 1 file `.xlsx` riêng cho mỗi site đối thủ, chia thành NHIỀU SHEET — mỗi sheet là 1 loại sản phẩm — mô phỏng cách tổ chức của `product_Metadata (1).xlsx`. Loại sản phẩm SHALL lấy theo `category 1` của chính site nguồn. Mọi sheet SHALL dùng cùng khuôn cột (tên và thứ tự) theo sheet "2. LED Downlight" của file tham chiếu, với điều chỉnh duy nhất đã chốt là thêm khả năng "Liên hệ" cho Giá. Dữ liệu của các site khác nhau SHALL không bị gộp chung vào 1 file.

#### Scenario: Xuất dữ liệu sau khi crawl xong 1 site
- **WHEN** crawl hoàn tất cho toàn bộ sản phẩm của 1 site đối thủ
- **THEN** hệ thống tạo 1 file `.xlsx` riêng cho site đó, mỗi loại sản phẩm nằm ở 1 sheet riêng, mọi sheet cùng khuôn cột đã chốt, không lẫn dữ liệu của site khác trong cùng file

#### Scenario: Bản ghi không xác định được loại sản phẩm
- **WHEN** 1 bản ghi không có `category 1` (vd fetch thất bại nên chưa trích xuất được)
- **THEN** bản ghi vẫn được ghi vào file, gom ở 1 sheet riêng cuối file thay vì bị bỏ đi, để lần chạy sau còn crawl lại được

#### Scenario: Crawl nhiều site
- **WHEN** hệ thống đã crawl từ 2 site đối thủ trở lên
- **THEN** mỗi site có 1 file `.xlsx` độc lập, không có file nào chứa dữ liệu trộn lẫn giữa các site

### Requirement: Trạng thái crawl per-record để hỗ trợ crawl lại có chọn lọc
Mỗi bản ghi SHALL có 1 trạng thái crawl nội bộ (thành công / lỗi / thiếu 1 phần field) không nằm trong các cột xuất ra file Excel, dùng để xác định bản ghi nào cần crawl lại khi chạy lại pipeline, vì hệ thống chỉ crawl 1 lần duy nhất và chỉ crawl lại các bản ghi lỗi/thiếu thay vì crawl lại toàn bộ.

#### Scenario: Một sản phẩm trích xuất thiếu field bắt buộc
- **WHEN** pipeline crawl xong 1 sản phẩm nhưng thiếu giá trị ở 1 field không thuộc nhóm optional (vd không lấy được Tên sản phẩm)
- **THEN** bản ghi được đánh dấu trạng thái thiếu field, và trở thành ứng viên cho lần crawl lại kế tiếp

#### Scenario: Chạy lại pipeline sau lần crawl đầu
- **WHEN** người vận hành chạy lại pipeline cho 1 site đã crawl trước đó
- **THEN** chỉ các bản ghi có trạng thái lỗi hoặc thiếu field được crawl lại; các bản ghi đã ở trạng thái thành công không bị crawl lại
