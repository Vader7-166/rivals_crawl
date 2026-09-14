## ADDED Requirements

### Requirement: Một ô tìm kiếm tự phân loại từ khoá
Hệ thống SHALL cung cấp một ô nhập từ khoá duy nhất. Từ khoá SHALL được tự phân loại thành một trong ba loại phạm vi mà người dùng không phải chọn loại trước: **nhãn hiệu**, **danh mục**, hoặc **tên sản phẩm**.

Việc phân loại SHALL dựa trên khớp chữ với hai tập đóng đã biết — danh sách nhãn hiệu đã đăng ký và tên danh mục trong chỉ mục — và SHALL KHÔNG gọi tầng LLM.

#### Scenario: Từ khoá là tên nhãn hiệu
- **WHEN** người dùng nhập một từ khoá khớp tên một nhãn hiệu đã đăng ký
- **THEN** phạm vi được hiểu là toàn bộ sản phẩm của nhãn hiệu đó, và loại phạm vi được hiển thị rõ cho người dùng thấy

#### Scenario: Từ khoá là tên danh mục
- **WHEN** người dùng nhập một từ khoá khớp tên danh mục trên một hoặc nhiều domain
- **THEN** phạm vi được hiểu là các danh mục khớp, gộp qua mọi domain có khớp, và loại phạm vi được hiển thị rõ

#### Scenario: Từ khoá vừa khớp nhãn hiệu vừa khớp danh mục
- **WHEN** một từ khoá khớp cả tên nhãn hiệu lẫn tên danh mục
- **THEN** hệ thống chọn một loại theo thứ tự ưu tiên cố định và định trước, đồng thời cho người dùng chuyển sang loại còn lại mà không phải gõ lại từ khoá

#### Scenario: Từ khoá không khớp tập đóng nào
- **WHEN** từ khoá không khớp nhãn hiệu nào và không khớp danh mục nào
- **THEN** hệ thống coi đó là tên sản phẩm và tìm trên tên sản phẩm đã có trong kho

#### Scenario: Không có kết quả nào
- **WHEN** từ khoá không cho ra phạm vi nào ở cả ba loại
- **THEN** hệ thống nói rõ là không khớp gì và không tạo job crawl nào

### Requirement: Tìm kiếm không phân biệt dấu và chữ hoa thường
Việc khớp từ khoá SHALL không phân biệt chữ hoa/thường và không phân biệt dấu tiếng Việt.

Ràng buộc này xuất phát từ dữ liệu thật: cùng một loại sản phẩm được các đối thủ viết là `ĐÈN DOWNLIGHT ÂM TRẦN`, `Đèn LED âm trần`, `Đèn LED âm trần khối đúc`.

#### Scenario: Gõ không dấu
- **WHEN** người dùng nhập `den am tran`
- **THEN** các danh mục viết có dấu như `Đèn LED âm trần` vẫn được khớp

#### Scenario: Gõ khác kiểu hoa thường
- **WHEN** người dùng nhập `downlight`
- **THEN** danh mục `ĐÈN DOWNLIGHT ÂM TRẦN` được khớp

### Requirement: Hiện đã có bao nhiêu, còn thiếu bao nhiêu trước khi crawl
Trước khi bắt đầu bất kỳ lượt crawl nào, hệ thống SHALL hiển thị cho phạm vi đang chọn: tổng số sản phẩm, số đã có bản trích xuất đầy đủ trong kho, và số còn thiếu — tách theo từng domain.

Lý do: một lượt crawl mất hàng chục phút; người dùng phải thấy trước mình sắp tiêu bao nhiêu.

#### Scenario: Phạm vi đã crawl đủ
- **WHEN** mọi sản phẩm trong phạm vi đã có bản trích xuất đầy đủ
- **THEN** hệ thống cho biết không cần crawl gì và cho phép xuất file ngay từ kho

#### Scenario: Phạm vi crawl một phần
- **WHEN** phạm vi có cả sản phẩm đã crawl lẫn chưa crawl
- **THEN** hệ thống hiển thị cả hai con số và cho phép xuất phần đang có mà không phải chờ crawl xong

#### Scenario: Domain trong phạm vi chưa từng probe
- **WHEN** phạm vi chạm tới một domain chưa có chỉ mục danh mục
- **THEN** hệ thống nói rõ domain đó chưa có chỉ mục và đề nghị dựng chỉ mục trước, thay vì báo là domain đó không có sản phẩm nào

### Requirement: Xác nhận phạm vi trước khi chạy, không lưu lại lựa chọn
Hệ thống SHALL liệt kê từng danh mục/domain đã khớp và cho phép người dùng bỏ chọn từng mục trước khi chạy crawl. Lựa chọn bỏ chọn này SHALL chỉ có hiệu lực cho lần chạy đó và SHALL KHÔNG được lưu thành cấu hình.

Đây là màn **xác nhận lúc dùng**, không phải quy trình phê duyệt: khớp chữ có thể trượt (danh mục `Eyecare Pro` của TLC là đèn âm trần nhưng không chứa chữ nào của từ khoá), và cách sửa là tick tại chỗ, không phải bảo trì một bảng ánh xạ.

#### Scenario: Bỏ chọn một danh mục khớp sai
- **WHEN** người dùng bỏ chọn một danh mục trong danh sách khớp rồi chạy crawl
- **THEN** các URL chỉ thuộc danh mục bị bỏ chọn không nằm trong phạm vi crawl

#### Scenario: Lần tìm kiếm sau không nhớ lựa chọn cũ
- **WHEN** người dùng nhập lại đúng từ khoá đó ở một lần sau
- **THEN** danh sách khớp hiện đầy đủ như ban đầu, không mục nào bị bỏ chọn sẵn theo lần trước

### Requirement: Tên nhãn hiệu là dữ liệu đăng ký theo domain
Tên nhãn hiệu SHALL là dữ liệu khai báo gắn với domain trong hồ sơ site. Hệ thống SHALL KHÔNG suy ra nhãn hiệu từ thuộc tính do đối thủ công bố trên trang.

Căn cứ đo trên dữ liệu thật: thuộc tính `thuong_hieu` vắng mặt hoàn toàn ở 549/549 bản ghi KingLED, và trên TLC cho ra bốn cách viết khác nhau cho cùng một nhãn hiệu.

#### Scenario: Domain không công bố thương hiệu
- **WHEN** một domain không có thuộc tính thương hiệu nào trên trang sản phẩm
- **THEN** tìm theo nhãn hiệu của domain đó vẫn hoạt động đúng

#### Scenario: Thêm một đối thủ mới
- **WHEN** thêm một domain đối thủ mới vào hệ thống
- **THEN** việc khai tên nhãn hiệu là thêm dữ liệu vào hồ sơ site, không phải thêm một module mã nguồn

#### Scenario: Nhãn hiệu có nhiều cách gọi
- **WHEN** người dùng gõ một biến thể tên nhãn hiệu đã được khai làm bí danh
- **THEN** phạm vi trả về đúng domain đó
