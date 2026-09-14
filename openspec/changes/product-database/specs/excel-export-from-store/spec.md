## ADDED Requirements

### Requirement: Kết xuất Excel là bước cuối của pipeline, đọc từ kho dữ liệu
Hệ thống SHALL sinh file `.xlsx` cho một domain bằng cách đọc từ kho dữ liệu, như một bước riêng chạy được độc lập với việc crawl.

#### Scenario: Xuất lại mà không crawl
- **WHEN** người dùng yêu cầu xuất file `.xlsx` cho một domain đã có dữ liệu trong kho
- **THEN** file được sinh ra từ dữ liệu đã lưu, không có request nào tới site đối thủ

#### Scenario: Xuất phản ánh bản trích xuất mới nhất
- **WHEN** một URL có nhiều bản ghi trích xuất từ nhiều lần chạy khác nhau
- **THEN** file xuất ra dùng bản trích xuất mới nhất trên snapshot mới nhất của URL đó

### Requirement: Khuôn 20 cột giữ nguyên tuyệt đối
File xuất ra SHALL giữ đúng 20 cột của khuôn tham chiếu, đúng tên (kể cả khoảng trắng thừa trong tên cột gốc), đúng thứ tự, và SHALL chia sheet theo loại sản phẩm như hiện hành. Cột không có dữ liệu tương ứng SHALL để trống chứ không bị loại khỏi file.

#### Scenario: So khớp với đường xuất cũ
- **WHEN** cùng một tập bản ghi được xuất bằng cơ chế mới và bằng cơ chế cũ
- **THEN** hai file có cùng tập sheet sản phẩm, cùng hàng tiêu đề, và cùng giá trị trên từng ô

#### Scenario: Sản phẩm không xác định được loại
- **WHEN** một bản ghi không có giá trị category
- **THEN** nó vẫn xuất hiện trong file, ở sheet dành cho bản ghi chưa phân loại, không bị bỏ đi

### Requirement: Sản phẩm không trích được mục ưu điểm vẫn để trống trên sheet danh mục
Với sản phẩm mà hệ thống không định vị được mục ưu điểm, hai cột ưu điểm trên sheet danh mục SHALL để trống. Hệ thống SHALL KHÔNG ghi nội dung thay thế (toàn văn trang, HTML, ghi chú) vào hai cột đó.

#### Scenario: Không tìm thấy mục ưu điểm
- **WHEN** một sản phẩm có nguồn gốc trích xuất là "không tìm thấy"
- **THEN** hai ô ưu điểm của sản phẩm đó trên sheet danh mục để trống, và sản phẩm vẫn có mặt đầy đủ ở các cột còn lại

### Requirement: Sheet cảnh báo liệt kê sản phẩm cần xử lý tay
File xuất ra SHALL có thêm một sheet liệt kê các sản phẩm không trích được mục ưu điểm, gồm URL, lý do, toàn văn text của trang, và đường dẫn tới file HTML nguyên bản đính kèm.

#### Scenario: Có sản phẩm cần xử lý tay
- **WHEN** một domain có sản phẩm không trích được mục ưu điểm
- **THEN** file xuất ra chứa sheet cảnh báo với một dòng cho mỗi sản phẩm đó, và mỗi dòng có đủ URL, lý do, text trang và đường dẫn file HTML

#### Scenario: Không có sản phẩm nào cần xử lý tay
- **WHEN** mọi sản phẩm của domain đều trích được mục ưu điểm
- **THEN** file xuất ra không chứa sheet cảnh báo, hoặc chứa một sheet rỗng có tiêu đề — không gây lỗi ở cả hai cách

#### Scenario: Lý do lấy từ nguồn gốc trích xuất
- **WHEN** một sản phẩm được đưa vào sheet cảnh báo
- **THEN** cột lý do phản ánh đúng nguồn gốc trích xuất đã lưu, phân biệt được "không tìm thấy mục nào" với các trường hợp độ tin cậy thấp

### Requirement: Nội dung quá dài bị cắt phải được báo rõ trong chính ô đó
Khi một giá trị vượt quá giới hạn ký tự của một ô Excel, hệ thống SHALL cắt nó ở ngưỡng dưới giới hạn và SHALL gắn dấu hiệu nhìn thấy được ngay trong ô cho biết nội dung đã bị cắt và tìm bản đầy đủ ở đâu.

#### Scenario: Text trang vượt giới hạn ô
- **WHEN** toàn văn text của một trang dài hơn ngưỡng cắt đã cấu hình
- **THEN** ô chứa phần đầu của text kèm dấu hiệu cho biết đã bị cắt và trỏ tới file HTML đính kèm, và độ dài ô không vượt quá giới hạn của Excel

#### Scenario: Không ô nào bị cắt âm thầm
- **WHEN** file `.xlsx` được sinh ra
- **THEN** không có ô nào bị thư viện ghi Excel tự cắt cụt mà không có dấu hiệu nào trong file

### Requirement: HTML nguyên bản xuất ra file đính kèm, không vào ô Excel
Hệ thống SHALL ghi HTML nguyên bản của các sản phẩm cần xử lý tay ra các file `.html` riêng đặt cạnh file `.xlsx`. Hệ thống SHALL KHÔNG ghi HTML vào bất kỳ ô nào của file `.xlsx`.

#### Scenario: Mở lại trang như lúc crawl
- **WHEN** người xử lý tay mở file `.html` được trỏ tới từ sheet cảnh báo
- **THEN** nội dung file là HTML đã lưu trong snapshot của đúng URL đó

#### Scenario: Sản phẩm cần xử lý tay không có snapshot
- **WHEN** một sản phẩm cần xử lý tay đến từ dữ liệu nhập từ file cũ và không có snapshot HTML
- **THEN** nó vẫn xuất hiện trên sheet cảnh báo, với ô đường dẫn file để trống và lý do cho biết chưa có HTML lưu lại

### Requirement: Đọc lại file đã xuất phải bỏ qua sheet cảnh báo
Khi một file `.xlsx` đã xuất được đọc lại để nhập vào kho dữ liệu, hệ thống SHALL bỏ qua sheet cảnh báo và chỉ đọc các sheet sản phẩm.

#### Scenario: Nhập lại file có sheet cảnh báo
- **WHEN** một file `.xlsx` có cả sheet sản phẩm lẫn sheet cảnh báo được nhập vào kho
- **THEN** chỉ các dòng ở sheet sản phẩm trở thành bản ghi, và không dòng nào của sheet cảnh báo bị hiểu nhầm thành sản phẩm
