## ADDED Requirements

### Requirement: Xuất một tập chọn cắt ngang nhiều domain
Hệ thống SHALL xuất ra một file `.xlsx` cho một tập sản phẩm chọn theo phạm vi tìm kiếm, kể cả khi tập đó trải trên nhiều domain. Đường xuất theo từng domain hiện có SHALL tiếp tục hoạt động không đổi.

#### Scenario: Xuất phạm vi theo danh mục trải nhiều đối thủ
- **WHEN** người dùng xuất một phạm vi danh mục khớp trên nhiều domain
- **THEN** file kết quả chứa sản phẩm của mọi domain trong phạm vi, trong một file duy nhất

#### Scenario: Xuất phạm vi một nhãn hiệu
- **WHEN** người dùng xuất phạm vi của đúng một nhãn hiệu
- **THEN** file kết quả tương đương với file sinh bởi đường xuất theo domain hiện có

#### Scenario: Xuất khi phạm vi mới crawl một phần
- **WHEN** người dùng xuất một phạm vi còn sản phẩm chưa crawl
- **THEN** file được sinh với phần dữ liệu đang có, và số sản phẩm còn thiếu được báo cho người dùng

### Requirement: Khuôn 20 cột giữ nguyên tuyệt đối
File xuất ra SHALL giữ đúng 20 cột của khuôn tham chiếu: đúng tên (kể cả khoảng trắng thừa trong tên cột gốc), đúng thứ tự. Hệ thống SHALL KHÔNG thêm cột mới cho nhãn hiệu, ngành hàng hay bất kỳ chiều phân loại nào.

Cột `category 1/2/3` SHALL tiếp tục mang giá trị nguyên văn của site nguồn, không bị thay bằng danh mục chuẩn hoá nào.

#### Scenario: Đối chiếu header với khuôn tham chiếu
- **WHEN** so hàng header của một sheet dữ liệu với khuôn tham chiếu
- **THEN** tên và thứ tự cột khớp tuyệt đối, không thừa không thiếu cột nào

#### Scenario: Sản phẩm từ đối thủ đặt tên danh mục riêng
- **WHEN** một sản phẩm thuộc danh mục mà đối thủ tự đặt tên
- **THEN** ô `category 1` mang đúng tên đối thủ đặt, không mang tên danh mục dùng để tìm kiếm

#### Scenario: Cột không có dữ liệu tương đương
- **WHEN** một cột của khuôn tham chiếu không có dữ liệu tương đương từ site đối thủ
- **THEN** ô đó để trống và cột vẫn xuất hiện trong file

### Requirement: Chiều phân loại mới nằm ở tên file và tên sheet
Vì khuôn 20 cột không còn chỗ, hệ thống SHALL biểu đạt chiều phân loại của tập chọn bằng tên file và cách chia sheet.

#### Scenario: Phạm vi theo danh mục
- **WHEN** xuất một phạm vi chọn theo danh mục trải nhiều đối thủ
- **THEN** mỗi đối thủ là một sheet riêng, và tên file mang tên danh mục đã tìm

#### Scenario: Phạm vi theo nhãn hiệu
- **WHEN** xuất một phạm vi chọn theo một nhãn hiệu
- **THEN** sheet được chia theo `category 1` của chính site nguồn, như hành vi xuất theo domain hiện có

#### Scenario: Tên sheet vượt giới hạn hoặc trùng nhau
- **WHEN** tên dùng cho sheet vượt giới hạn ký tự của Excel hoặc trùng với sheet khác
- **THEN** tên được rút gọn giữ được cả phần đầu lẫn phần đuôi và được làm cho duy nhất, không nhóm nào bị ghi đè lên nhóm khác

### Requirement: Thứ tự sheet biểu đạt thứ hạng đối thủ
Khi một file chứa nhiều đối thủ, thứ tự sheet SHALL phản ánh thứ hạng đối thủ. Mặc định SHALL xếp theo số sản phẩm đo được trong phạm vi đó. Người dùng SHALL đổi được thứ tự này tại thời điểm xuất file.

Thứ hạng SHALL KHÔNG ảnh hưởng tới việc crawl đối thủ nào: đổi thứ hạng chỉ sinh lại file, không sinh ra lượt crawl nào.

#### Scenario: Thứ tự mặc định
- **WHEN** xuất một phạm vi nhiều đối thủ mà không chỉ định thứ tự
- **THEN** sheet xếp giảm dần theo số sản phẩm của mỗi đối thủ trong phạm vi

#### Scenario: Người dùng đổi thứ tự
- **WHEN** người dùng đổi thứ tự đối thủ rồi xuất lại
- **THEN** file mới có thứ tự sheet theo đúng lựa chọn, và không lượt crawl nào được kích hoạt

### Requirement: Sản phẩm cần xử lý tay xuất hiện ở sheet cảnh báo
File xuất ra SHALL kèm một sheet cảnh báo liệt kê các sản phẩm cần người xử lý tay, kèm lý do. Sheet này nằm **ngoài** khuôn 20 cột. Trên sheet dữ liệu, các ô không lấy được SHALL để trống thay vì điền dữ liệu suy đoán.

#### Scenario: Có sản phẩm cần xử lý tay
- **WHEN** tập chọn chứa sản phẩm không lấy được mục ưu điểm hoặc lấy bằng nhánh độ tin cậy thấp
- **THEN** sản phẩm đó xuất hiện trên sheet cảnh báo kèm lý do, đồng thời vẫn có mặt trên sheet dữ liệu với các ô tương ứng để trống

#### Scenario: Không có sản phẩm nào cần xử lý tay
- **WHEN** mọi sản phẩm trong tập chọn đều đầy đủ
- **THEN** file không có sheet cảnh báo
