## ADDED Requirements

### Requirement: Giữ lại URL trang danh mục thay vì vứt bỏ
Site probing SHALL giữ các URL trang danh mục phát hiện được từ sitemap taxonomy vào một danh sách riêng của kết quả probe. Các URL này SHALL KHÔNG được trộn vào danh sách URL sản phẩm.

Ràng buộc "không trộn" là bắt buộc chứ không phải khuyến nghị: trang danh mục không có structured data sản phẩm, lẫn vào thì tốn lượt fetch và lượt gọi LLM để sinh ra bản ghi rỗng. Đây là lỗi đã xảy ra một lần và đã được ghi lại (559 URL thay vì 486 trên TLC).

#### Scenario: Sitemap index có cả sitemap sản phẩm lẫn sitemap taxonomy
- **WHEN** sitemap index của một domain chứa cả sub-sitemap sản phẩm lẫn sub-sitemap taxonomy (tiền tố `product_` kiểu WooCommerce, hoặc hậu tố Group/Category kiểu sitemap sinh động)
- **THEN** URL sản phẩm nằm trong danh sách URL sản phẩm, URL trang danh mục nằm trong danh sách trang danh mục, và hai danh sách không giao nhau

#### Scenario: Domain không có sitemap taxonomy
- **WHEN** một domain chỉ có sitemap sản phẩm, không có sitemap taxonomy nào
- **THEN** danh sách trang danh mục để rỗng, và danh sách URL sản phẩm không đổi so với hành vi trước đây

#### Scenario: Số lượng URL sản phẩm không đổi
- **WHEN** probe chạy lại trên một domain đã probe trước đây
- **THEN** số lượng URL sản phẩm trả về bằng đúng số lượng của lần probe trước — việc giữ thêm trang danh mục không được làm thay đổi danh sách sản phẩm

### Requirement: Dựng chỉ mục danh mục ↔ sản phẩm trước khi crawl
Hệ thống SHALL duyệt các trang danh mục đã giữ được và dựng chỉ mục các cạnh (danh mục, URL sản phẩm) cho một domain. Việc dựng chỉ mục SHALL KHÔNG gọi tầng LLM và SHALL KHÔNG fetch trang sản phẩm nào.

Mục đích: biết một URL sản phẩm thuộc danh mục nào **trước khi** tốn một lượt fetch nào cho chính URL đó.

#### Scenario: Dựng chỉ mục cho một domain
- **WHEN** hệ thống dựng chỉ mục danh mục cho một domain đã probe
- **THEN** mỗi trang danh mục được fetch đúng một lần, không trang sản phẩm nào được fetch, và không lời gọi LLM nào được thực hiện

#### Scenario: Một sản phẩm thuộc nhiều danh mục
- **WHEN** cùng một URL sản phẩm xuất hiện trong lưới của hai trang danh mục khác nhau
- **THEN** chỉ mục ghi nhận cả hai cạnh, không cạnh nào ghi đè cạnh nào

#### Scenario: Trang danh mục có phân trang
- **WHEN** một trang danh mục trải ra nhiều trang con
- **THEN** chỉ mục thu thập sản phẩm trên toàn bộ các trang con, không chỉ trang đầu

#### Scenario: Một trang danh mục fetch thất bại
- **WHEN** một trong các trang danh mục không fetch được
- **THEN** việc dựng chỉ mục vẫn hoàn tất cho các trang còn lại, và danh mục thất bại được ghi nhận là chưa có dữ liệu thay vì được ghi nhận là rỗng

### Requirement: Chỉ mục là dữ liệu dẫn xuất, dựng lại được
Chỉ mục danh mục SHALL có thể bị xoá và dựng lại hoàn toàn từ site đối thủ mà không mất bất kỳ dữ liệu nào do người nhập vào. Hệ thống SHALL KHÔNG yêu cầu người dùng chỉnh sửa hay phê duyệt chỉ mục để nó dùng được.

#### Scenario: Xoá và dựng lại chỉ mục
- **WHEN** toàn bộ chỉ mục của một domain bị xoá rồi dựng lại
- **THEN** kết quả tra cứu giống như trước khi xoá (với điều kiện site đối thủ không đổi), và không có thao tác nhập liệu tay nào cần thực hiện

#### Scenario: Đối thủ đổi cấu trúc danh mục
- **WHEN** đối thủ thêm, đổi tên hoặc bỏ một danh mục
- **THEN** dựng lại chỉ mục là đủ để phản ánh thay đổi đó, không cần sửa cấu hình nào trong mã nguồn

### Requirement: Tra cứu phạm vi theo danh mục trước khi crawl
Hệ thống SHALL trả lời được, cho một danh mục của một domain: tổng số URL sản phẩm thuộc danh mục đó, số URL đã có bản trích xuất đầy đủ trong kho, và số URL còn thiếu.

#### Scenario: Danh mục chưa crawl lần nào
- **WHEN** tra cứu một danh mục mà chưa URL nào trong đó được crawl
- **THEN** kết quả cho biết tổng số URL và số còn thiếu bằng tổng số đó

#### Scenario: Danh mục đã crawl một phần
- **WHEN** tra cứu một danh mục mà một số URL đã có bản trích xuất trạng thái đầy đủ còn số khác thì chưa
- **THEN** kết quả tách rõ số đã có và số còn thiếu, và số còn thiếu đúng bằng tập URL sẽ được crawl nếu chạy

#### Scenario: Sản phẩm không thuộc danh mục nào
- **WHEN** một URL sản phẩm có trong sitemap nhưng không xuất hiện trên bất kỳ trang danh mục nào
- **THEN** URL đó vẫn tra cứu được ở phạm vi toàn domain và được đánh dấu là chưa xác định danh mục, không bị loại khỏi hệ thống
