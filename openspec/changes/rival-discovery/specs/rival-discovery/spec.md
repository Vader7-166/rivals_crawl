## ADDED Requirements

### Requirement: Tìm site LED ứng viên bằng bộ máy tìm kiếm
Hệ thống SHALL nhận một hoặc nhiều từ khoá, hỏi một bộ máy tìm kiếm, và trả về top N domain ứng viên kèm điểm số.

Bộ máy tìm kiếm SHALL là một thành phần thay thế được: đổi sang nguồn khác (có khoá API) SHALL KHÔNG đòi sửa tầng chọn lọc hay tầng truy vấn.

#### Scenario: Một domain ra ở nhiều từ khoá
- **WHEN** cùng một domain xuất hiện ở kết quả của nhiều từ khoá khác nhau
- **THEN** nó là **một** ứng viên duy nhất, mang theo danh sách từ khoá đã kéo nó ra và thứ hạng tốt nhất

#### Scenario: Bộ máy tìm kiếm chặn hoặc đổi bố cục
- **WHEN** một truy vấn không đọc được kết quả nào
- **THEN** hệ thống cảnh báo rõ là có thể đang bị chặn, và các truy vấn còn lại vẫn chạy — một truy vấn hỏng SHALL KHÔNG làm hỏng cả đợt đo

### Requirement: Chỉ loại thẳng những tập đóng, phần còn lại là điểm kèm lý do
Hệ thống SHALL loại thẳng khỏi kết quả: sàn thương mại điện tử, mạng xã hội, từ điển/bách khoa, và site của chính công ty mình. Đây là các tập **đóng**, kiểm chứng được bằng mắt.

Mọi phán đoán khác — nhà sản xuất hay đại lý — SHALL được thể hiện bằng **điểm kèm lý do đọc được**, và SHALL KHÔNG tự loại ứng viên nào.

Căn cứ: đo trên trang thật cho thấy luật "nhiều nhãn trên trang chủ = đại lý" sai cả hai chiều — `kingled.com.vn` (nhà sản xuất thật) nhắc 5 nhãn, `ledhome.vn` (đại lý thật) nhắc 0 nhãn vì trang render bằng JS.

#### Scenario: Site của chính mình lọt vào kết quả
- **WHEN** domain của chính công ty mình xuất hiện trong kết quả tìm kiếm
- **THEN** nó bị loại kèm lý do, không chiếm chỗ trong top N

#### Scenario: Ứng viên rơi vào vùng không phân biệt được
- **WHEN** các tín hiệu không đủ để nghiêng về nhà sản xuất hay đại lý
- **THEN** tín hiệu đó cho **0 điểm** thay vì đoán một chiều

#### Scenario: Người đọc cần kiểm chứng một ứng viên
- **WHEN** hệ thống xếp một domain vào top N
- **THEN** mỗi tín hiệu góp điểm đều đi kèm một câu giải thích nêu **số đo** dẫn tới nó

### Requirement: Không tự thêm domain nào vào hệ thống
Kết quả tìm kiếm SHALL là danh sách để người dùng đọc và quyết định. Hệ thống SHALL KHÔNG tự thêm domain vào registry, SHALL KHÔNG tự tạo job crawl, và SHALL KHÔNG ghi gì vào kho dữ liệu.

Lý do: một domain sai đi vào kho chỉ lộ ra khi có người soi dữ liệu, trong khi giá của việc bỏ qua một gợi ý đúng chỉ là chạy lại lệnh tìm.

#### Scenario: Chạy tìm kiếm nhiều lần
- **WHEN** người dùng chạy tìm kiếm
- **THEN** số bản ghi trong kho dữ liệu không đổi

### Requirement: Từ khoá tìm kiếm là tên loại hàng, dựng từ dữ liệu đã có
Truy vấn mặc định SHALL được dựng từ tên danh mục của các sản phẩm đã crawl, sau khi **bỏ tên nhãn hiệu** khỏi chuỗi và xếp theo số đối thủ cùng có danh mục đó.

Căn cứ đo trên Bing: truy vấn mô tả loại hình doanh nghiệp không tìm ra site nào trong ngành — `công ty sản xuất đèn led` trả về vietjack và dichvucong.gov.vn; `thương hiệu đèn led việt nam` trả về youtube và wikipedia. Trong khi `đèn led âm trần` trả về 10/10 domain đúng ngành.

#### Scenario: Tên danh mục có kèm tên nhãn
- **WHEN** kho chứa danh mục kiểu `Đèn LED Âm Trần VinaLED`
- **THEN** truy vấn sinh ra là `Đèn LED Âm Trần` — giữ tên nhãn thì chỉ tìm ra chính site của nhãn đó, trái mục đích

#### Scenario: Danh mục không thuộc ngành chiếu sáng
- **WHEN** kho chứa danh mục kiểu `Thiết Bị Điện Thông Minh` hay `Quạt trần`
- **THEN** nó không được dùng làm truy vấn

#### Scenario: Kho chưa có dữ liệu nào
- **WHEN** chạy lần đầu, kho rỗng
- **THEN** hệ thống dùng danh sách truy vấn mặc định và vẫn chạy được

### Requirement: Tìm lại site của một nhãn đã biết
Hệ thống SHALL hỗ trợ tìm địa chỉ hiện tại của một nhãn hiệu đã đăng ký, dùng cho trường hợp domain cũ chết hoặc đối thủ đổi tên miền.

Ở đường này, domain **đã có trong registry** SHALL được đánh dấu chứ không bị loại: nếu nó vẫn đứng đầu thì chính đó là câu trả lời — site cũ vẫn sống.

#### Scenario: Site cũ vẫn hoạt động
- **WHEN** tìm lại một nhãn mà domain đã đăng ký vẫn đứng đầu kết quả
- **THEN** kết quả nêu rõ domain đó đã có trong registry

#### Scenario: Tên nhãn trùng với một từ thông dụng
- **WHEN** tên nhãn là một từ đa nghĩa (`Roman`, `Asia`)
- **THEN** truy vấn vẫn kèm từ neo của ngành, để kết quả không trượt sang lĩnh vực khác
