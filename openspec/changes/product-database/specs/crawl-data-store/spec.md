## ADDED Requirements

### Requirement: Lưu snapshot HTML cho mọi trang sản phẩm đã fetch
Hệ thống SHALL lưu lại nội dung HTML của **mọi** trang sản phẩm fetch thành công, không phụ thuộc vào việc trích xuất sau đó thành công hay thất bại. HTML SHALL được lưu ở dạng nén, kèm thời điểm fetch, mã HTTP và URL cuối cùng sau chuyển hướng.

#### Scenario: Trang trích xuất thành công vẫn được lưu HTML
- **WHEN** một trang sản phẩm được fetch thành công và mọi tầng trích xuất đều cho ra dữ liệu đầy đủ
- **THEN** HTML của trang đó vẫn được lưu vào kho snapshot

#### Scenario: Fetch thất bại
- **WHEN** việc fetch một URL thất bại (lỗi mạng, bị chặn, timeout) và không có nội dung HTML nào
- **THEN** hệ thống không tạo snapshot rỗng, và bản ghi trích xuất tương ứng mang trạng thái lỗi kèm lý do

### Requirement: Tách lịch sử fetch khỏi lịch sử trích xuất
Hệ thống SHALL lưu kết quả trích xuất trong một thực thể riêng, tham chiếu tới đúng snapshot mà nó được sinh ra từ đó, kèm định danh phiên bản của bộ trích xuất. Một snapshot SHALL có thể mang nhiều kết quả trích xuất khác nhau.

#### Scenario: Chạy lại bộ trích xuất trên HTML đã lưu
- **WHEN** bộ trích xuất được chạy lại trên một snapshot đã có sẵn trong kho
- **THEN** một bản ghi trích xuất **mới** được tạo, tham chiếu tới cùng snapshot đó, và bản ghi trích xuất cũ không bị ghi đè hay xoá

#### Scenario: Phân biệt nguồn thay đổi
- **WHEN** hai bản ghi trích xuất của cùng một URL cho ra giá trị `gia` khác nhau
- **THEN** từ dữ liệu đã lưu xác định được chúng sinh ra từ cùng một snapshot hay từ hai snapshot khác nhau

### Requirement: Chạy lại trích xuất không cần fetch lại
Hệ thống SHALL cho phép chạy lại toàn bộ quy trình trích xuất trên các snapshot đã lưu mà không thực hiện bất kỳ request mạng nào tới site đối thủ.

#### Scenario: Chạy lại trên toàn bộ kho snapshot
- **WHEN** người dùng chạy lại bộ trích xuất trên mọi snapshot của một domain
- **THEN** không có request nào được gửi tới domain đó, và mỗi snapshot sinh ra một bản ghi trích xuất mới

### Requirement: Ghi lại nguồn gốc của hai cột ưu điểm
Với mỗi kết quả trích xuất, hệ thống SHALL ghi lại **đường nào** đã định vị được mục ưu điểm: khớp từ khoá trên tiêu đề, la bàn do tầng LLM chỉ ra, cụm đề mục ngang cấp, hoặc không tìm thấy mục nào.

#### Scenario: Truy vấn các ô có độ tin cậy thấp
- **WHEN** người dùng cần rà soát các ô ưu điểm được lấy bằng nhánh cụm đề mục (nhánh có đánh đổi độ chính xác đã biết)
- **THEN** các bản ghi đó được lọc ra bằng đúng giá trị nguồn gốc đã lưu, không cần mở từng ô để đoán

#### Scenario: Không tìm thấy mục ưu điểm
- **WHEN** không đường nào định vị được mục ưu điểm trên một trang
- **THEN** hai cột ưu điểm để trống và nguồn gốc được ghi là "không tìm thấy" — phân biệt được với trường hợp chưa từng chạy trích xuất

### Requirement: Tags lưu dạng key-value truy vấn được
Hệ thống SHALL lưu mỗi thuộc tính trong `tags` thành một bản ghi riêng gồm khoá và giá trị, gắn với kết quả trích xuất tương ứng. Số lượng và tên khoá SHALL không bị giới hạn bởi một danh sách cố định.

#### Scenario: Hai sản phẩm có bộ thuộc tính khác nhau
- **WHEN** một sản phẩm có 3 thuộc tính và một sản phẩm khác có 11 thuộc tính, với tên khoá không trùng nhau hoàn toàn
- **THEN** cả hai được lưu đầy đủ, không sản phẩm nào bị mất thuộc tính và không cần thay đổi cấu trúc lưu trữ

#### Scenario: Thống kê thuộc tính trên toàn site
- **WHEN** cần biết có bao nhiêu sản phẩm của một domain công bố một thuộc tính cụ thể
- **THEN** trả lời được bằng một truy vấn trên kho dữ liệu, không cần đọc và giải mã từng ô JSON

### Requirement: URL là định danh sản phẩm, giữ nguyên văn
Hệ thống SHALL dùng URL sản phẩm làm định danh, và SHALL lưu URL **đúng nguyên văn** như site công bố — không cắt bỏ dấu `/` cuối, không chuẩn hoá dạng khác.

#### Scenario: Hai site có quy ước dấu gạch chéo khác nhau
- **WHEN** kho dữ liệu chứa sản phẩm của một site mà mọi URL kết thúc bằng `/` và một site mà không URL nào kết thúc bằng `/`
- **THEN** URL của cả hai site được lưu và tra cứu đúng như dạng gốc, và việc đối chiếu bản ghi cũ ở lần crawl sau vẫn khớp

### Requirement: Kho dữ liệu là nguồn xác định bản ghi cần crawl lại
Hệ thống SHALL xác định sản phẩm nào cần crawl lại dựa trên kho dữ liệu, không dựa vào việc đọc ngược file Excel đã xuất.

#### Scenario: Chạy lại sau khi đã có dữ liệu
- **WHEN** một lượt crawl được chạy lại trên một domain đã có dữ liệu trong kho
- **THEN** chỉ các URL chưa có kết quả trích xuất đầy đủ mới được fetch lại; kết quả này không phụ thuộc vào sự tồn tại hay nội dung của bất kỳ file `.xlsx` nào

#### Scenario: File Excel bị xoá
- **WHEN** file `.xlsx` đã xuất trước đó bị xoá khỏi thư mục output
- **THEN** lượt crawl tiếp theo vẫn nhận ra các sản phẩm đã crawl xong và không crawl lại chúng

### Requirement: Nhập dữ liệu đã có từ file Excel
Hệ thống SHALL nhập được các bản ghi từ file `.xlsx` đã xuất trước đây vào kho dữ liệu, đánh dấu rõ chúng không có snapshot HTML kèm theo.

#### Scenario: Nhập file cũ
- **WHEN** một file `.xlsx` đã xuất trước đây được nhập vào kho
- **THEN** mỗi dòng sản phẩm trở thành một bản ghi trích xuất không gắn snapshot, được đánh dấu là nhập từ file cũ, và không bị nhầm là kết quả của một lượt trích xuất thật

#### Scenario: Bản ghi nhập từ file cũ không chạy lại trích xuất được
- **WHEN** bộ trích xuất được chạy lại trên toàn kho
- **THEN** các bản ghi nhập từ file cũ bị bỏ qua (không có HTML để chạy) và được báo rõ số lượng, không gây lỗi

### Requirement: Ghi dữ liệu an toàn khi crawl song song
Hệ thống SHALL ghi vào kho dữ liệu một cách an toàn khi pipeline chạy nhiều tác vụ crawl đồng thời, không để mất bản ghi và không lỗi khoá cơ sở dữ liệu.

#### Scenario: Nhiều tác vụ hoàn thành đồng thời
- **WHEN** nhiều tác vụ crawl hoàn thành gần như cùng lúc và cùng cần ghi kết quả
- **THEN** mọi kết quả đều được lưu, không bản ghi nào bị mất và không phát sinh lỗi khoá cơ sở dữ liệu

#### Scenario: Tiến trình bị dừng giữa chừng
- **WHEN** tiến trình crawl bị dừng đột ngột giữa chừng
- **THEN** mọi bản ghi đã ghi xong trước thời điểm đó vẫn còn nguyên trong kho, và lượt chạy tiếp theo chỉ crawl phần còn thiếu
