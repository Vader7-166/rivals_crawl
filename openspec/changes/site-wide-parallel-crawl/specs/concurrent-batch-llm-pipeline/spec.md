## ADDED Requirements

### Requirement: Fetch nhiều sản phẩm đồng thời có giới hạn
Hệ thống SHALL fetch nhiều URL sản phẩm đồng thời (không tuần tự từng URL một), với số lượng đồng thời tối đa SHALL bị giới hạn bởi 1 cấu hình riêng cho fetch (độc lập với giới hạn số lệnh gọi LLM đồng thời).

#### Scenario: Danh sách URL lớn hơn giới hạn concurrency
- **WHEN** hệ thống crawl 1 danh sách URL sản phẩm có số lượng lớn hơn giới hạn fetch-concurrency đã cấu hình
- **THEN** tại bất kỳ thời điểm nào, số lượng fetch đang chạy đồng thời không vượt quá giới hạn đã cấu hình

### Requirement: Gộp nhiều sản phẩm vào 1 lệnh gọi LLM
Hệ thống SHALL gộp nhiều sản phẩm (kích thước batch nhỏ, 3-5 sản phẩm) vào 1 lệnh gọi LLM duy nhất để trích xuất Tags, thay vì gọi riêng từng sản phẩm, khi số sản phẩm đang chờ xử lý đủ để tạo 1 batch.

#### Scenario: Đủ sản phẩm để tạo batch
- **WHEN** có từ 3 đến 5 sản phẩm đã sẵn sàng cho tầng trích xuất Tags
- **THEN** hệ thống gộp các sản phẩm đó vào 1 prompt và thực hiện đúng 1 lệnh gọi LLM cho cả nhóm

### Requirement: Kết quả batch khoá theo ID rõ ràng, không theo vị trí
Prompt batch SHALL yêu cầu LLM trả về kết quả dưới dạng JSON object khoá theo ID tường minh của từng sản phẩm (không phải JSON array dựa vào vị trí), để tránh gán nhầm kết quả giữa các sản phẩm khi model bỏ sót hoặc đổi thứ tự 1 phần tử.

#### Scenario: Model bỏ sót 1 sản phẩm trong batch
- **WHEN** kết quả LLM trả về cho 1 batch 4 sản phẩm chỉ chứa key cho 3 trong 4 ID đã gửi
- **THEN** hệ thống phát hiện được chính xác ID nào bị thiếu (không suy diễn nhầm dữ liệu của sản phẩm khác sang cho ID bị thiếu)

### Requirement: Bậc thang xử lý batch ưu tiên độ tin cậy
Khi 1 lệnh gọi batch thất bại (không phải JSON hợp lệ, hoặc thiếu ID, hoặc có item không hợp lệ), hệ thống SHALL retry nguyên batch đó tối đa 2 lần; nếu vẫn thất bại, hệ thống SHALL rã batch và gọi LLM riêng lẻ cho từng sản phẩm trong batch đó (tương đương cách xử lý 1-sản-phẩm-1-lệnh-gọi trước khi có batching). Hệ thống SHALL KHÔNG chấp nhận một phần kết quả từ 1 lệnh gọi batch đã được xác định là thất bại.

#### Scenario: Batch thất bại nhưng phục hồi được sau khi rã lẻ
- **WHEN** 1 batch 4 sản phẩm thất bại ở cả lệnh gọi đầu và 2 lần retry
- **THEN** hệ thống gọi LLM riêng cho từng sản phẩm trong 4 sản phẩm đó, và mỗi sản phẩm gọi thành công SHALL có kết quả đúng như khi gọi đơn lẻ

#### Scenario: Batch thất bại một phần không được chấp nhận
- **WHEN** kết quả batch có 3/4 ID hợp lệ và 1 ID bị lỗi định dạng giá trị
- **THEN** hệ thống coi toàn bộ batch là thất bại (không lấy riêng 3 kết quả hợp lệ), và tiến hành retry/rã batch theo đúng bậc thang

### Requirement: Phân biệt lỗi tạm thời (quota/rate-limit) với lỗi không thể phục hồi
Khi 1 lệnh gọi tới provider LLM thất bại do vượt quota/rate-limit (ví dụ mã lỗi HTTP 429), hệ thống SHALL thử lại chính provider đó (có khoảng chờ giữa các lần thử) một số lần giới hạn trước khi coi là thất bại và chuyển sang provider dự phòng; lỗi không thuộc loại tạm thời (ví dụ lỗi xác thực) SHALL được chuyển ngay sang provider dự phòng mà không cần thử lại.

#### Scenario: Vertex AI trả về lỗi vượt quota
- **WHEN** 1 lệnh gọi tới Vertex AI thất bại với lỗi vượt quota/rate-limit
- **THEN** hệ thống thử lại chính Vertex AI (không chuyển sang DeepSeek ngay lập tức) trong giới hạn số lần thử lại đã cấu hình

#### Scenario: Vertex AI trả về lỗi xác thực
- **WHEN** 1 lệnh gọi tới Vertex AI thất bại với lỗi xác thực/cấu hình sai
- **THEN** hệ thống chuyển ngay sang provider dự phòng mà không thử lại nhiều lần với Vertex AI

### Requirement: Checkpoint hoạt động đúng khi hoàn thành không theo thứ tự
Khi crawl song song, các sản phẩm hoàn thành không theo đúng thứ tự trong danh sách URL gốc. Hệ thống SHALL vẫn ghi tạm kết quả ra file Excel theo đúng chu kỳ đã cấu hình (mỗi N sản phẩm hoàn thành), đếm theo số lượng sản phẩm đã hoàn thành thực tế, không phụ thuộc vị trí của sản phẩm đó trong danh sách URL gốc.

#### Scenario: Sản phẩm hoàn thành không theo thứ tự URL gốc
- **WHEN** sản phẩm ở vị trí thứ 50 trong danh sách URL gốc hoàn thành crawl trước sản phẩm ở vị trí thứ 10
- **THEN** việc ghi checkpoint vẫn diễn ra đúng sau mỗi N sản phẩm hoàn thành thực tế, không bị lệch hay bỏ sót do thứ tự hoàn thành khác thứ tự danh sách gốc

### Requirement: Không mất dữ liệu khi bị gián đoạn giữa chừng
Nếu tiến trình crawl bị dừng đột ngột giữa chừng (không phải do lỗi logic), hệ thống SHALL đảm bảo dữ liệu đã crawl và ghi checkpoint gần nhất không bị mất, và lần chạy lại tiếp theo SHALL chỉ crawl các sản phẩm chưa hoàn thành (tái sử dụng cơ chế crawl-lại-có-chọn-lọc đã có).

#### Scenario: Tiến trình bị dừng giữa chừng sau khi đã có ít nhất 1 checkpoint
- **WHEN** tiến trình crawl bị dừng sau khi đã ghi ít nhất 1 lần checkpoint nhưng chưa crawl hết toàn bộ danh sách URL
- **THEN** lần chạy lại tiếp theo đọc được các sản phẩm đã hoàn thành từ checkpoint gần nhất và chỉ crawl tiếp các sản phẩm còn thiếu
