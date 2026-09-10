## 1. Chốt hành vi probing hiện tại trước khi đụng vào

- [x] 1.1 Viết test chốt số URL sản phẩm mà `resolve_sitemap_entries` +
      `select_product_urls` trả về cho fixture của cả hai site — KingLED 557,
      TLC 486. Test này phải XANH trước khi sửa `sitemap.py` và phải còn xanh
      sau khi sửa; đây là hàng rào chống tái hiện bug 559-thay-vì-486.
- [x] 1.2 Thêm fixture sitemap taxonomy cho cả hai kiểu đặt tên: tiền tố
      `product_cat-sitemap.xml` (WooCommerce) và hậu tố
      `sitemap.xml?page=ProductGroup` (sinh động).

## 2. Chỉ mục danh mục (capability `category-index`)

- [x] 2.1 Cho `resolve_sitemap_entries` trả về URL taxonomy ở một kênh riêng
      thay vì loại bỏ hẳn. KHÔNG sửa regex `_TAXONOMY_SITEMAP`.
- [x] 2.2 Điền các URL đó vào `ProbeResult.listing_urls` trong `prober.py`; ghi
      vào cache probe cùng lúc. Chạy lại 1.1 xác nhận danh sách sản phẩm không
      đổi.
- [x] 2.3 Tổng quát hoá logic phân trang danh mục trong `sites/tlc.py` thành
      một hàm dùng chung cho mọi site (nhận URL danh mục, trả URL sản phẩm),
      giữ nguyên hành vi cho TLC. Đo lại ngưỡng chặn số trang — hiện chặn cứng
      20, chưa biết đủ chưa cho 211 danh mục (Open Question 3 của design).
- [x] 2.4 Bảng lưu chỉ mục: cạnh (domain, tên danh mục, URL danh mục, URL sản
      phẩm) + thời điểm dựng. Đánh dấu rõ đây là cache dẫn xuất, xoá dựng lại
      được.
- [x] 2.5 Hàm dựng chỉ mục cho một domain: duyệt `listing_urls`, phân trang,
      thu cạnh. Không fetch trang sản phẩm, không gọi LLM — khẳng định bằng
      test dùng fetcher giả đếm số lần gọi.
- [x] 2.6 Trang danh mục fetch thất bại được ghi là "chưa có dữ liệu", phân
      biệt được với "danh mục rỗng".
- [x] 2.7 Hàm tra cứu phạm vi: cho (domain, danh mục) trả về tổng số URL, số đã
      có bản trích xuất đầy đủ, số còn thiếu. Dùng lại `urls_needing_crawl()`
      đang có thay vì viết lại logic "còn thiếu".
- [x] 2.8 URL sản phẩm không thuộc danh mục nào vẫn tra được ở mức toàn domain
      và được đánh dấu chưa xác định danh mục.
- [x] 2.9 Script CLI dựng chỉ mục cho một domain. Chạy thật trên KingLED và
      TLC, ghi lại số danh mục và số cạnh thu được vào `docs/pipeline.md`.
      (Chạy `--limit 5` mỗi site — đủ để kiểm chứng cơ chế; lượt đầy đủ 211
      danh mục còn lại để chạy sau.)
- [x] 2.11 Tách `SiteProfile.listing_fetch_options` khỏi `fetch_options`. Lỗi
      phát hiện khi chạy thật: `wait_selector` hiệu chỉnh cho trang sản phẩm
      không bao giờ khớp trên trang danh mục, làm mỗi trang chờ suông 5s. Đo
      A/B: 11,6s vs 37,6s trên cùng 5 danh mục, cạnh giống hệt.
- [x] 2.12 Không nổ cảnh báo độ phủ khi chạy `--limit`: độ phủ một phần là đúng
      theo định nghĩa, cảnh báo nào cũng kêu thì không cảnh báo nào được đọc.
- [x] 2.10 Đối chiếu tổng số URL trong chỉ mục với số URL từ sitemap; chênh
      lệch phải được báo ra chứ không nuốt (rủi ro "trang danh mục không liệt
      kê đủ" trong design).

## 3. Nhãn hiệu và tìm kiếm phạm vi (capability `crawl-scope-search`)

- [x] 3.1 Thêm field `brand_name` (và danh sách bí danh) vào `SiteProfile`.
      Điền cho `kingled.com.vn` và `tlclighting.com.vn`. Không suy từ tag
      `thuong_hieu`.
- [x] 3.2 Hàm chuẩn hoá chuỗi để so khớp: bỏ dấu tiếng Việt, về chữ thường.
      Test bằng cặp thật: `den am tran` khớp `Đèn LED âm trần`, `downlight`
      khớp `ĐÈN DOWNLIGHT ÂM TRẦN`.
- [x] 3.3 Bộ phân loại từ khoá: khớp nhãn hiệu → khớp danh mục → coi là tên sản
      phẩm. Thứ tự ưu tiên cố định và ghi rõ trong docstring.
- [x] 3.4 Từ khoá khớp cả nhãn hiệu lẫn danh mục: trả về loại ưu tiên kèm thông
      tin để giao diện cho chuyển loại mà không phải gõ lại.
- [x] 3.5 Không khớp gì ở cả ba loại: trả kết quả rỗng có lý do, không tạo job.
- [x] 3.6 Gộp phạm vi + tra cứu: cho một từ khoá, trả về theo từng domain danh
      sách danh mục khớp, tổng số / đã có / còn thiếu.
- [x] 3.7 Domain chưa có chỉ mục: báo rõ "chưa dựng chỉ mục", không báo "không
      có sản phẩm".

## 4. Tầng API chỉ đọc

- [ ] 4.1 Dựng khung ứng dụng API, mở kết nối kho ở chế độ chỉ đọc.
- [ ] 4.2 Endpoint tìm kiếm phạm vi (bọc mục 3).
- [ ] 4.3 Endpoint liệt kê domain đã đăng ký kèm trạng thái: đã probe chưa, đã
      dựng chỉ mục chưa, có bao nhiêu bản ghi.
- [ ] 4.4 Endpoint xem sản phẩm của một domain, lọc được theo trạng thái crawl
      và theo "cần xử lý tay".
- [ ] 4.5 Khẳng định bằng test: mọi endpoint ở mục này không ghi vào kho.

## 5. Job nền chạy crawl (capability `crawl-job-runner`)

- [ ] 5.1 Chốt cơ chế hàng đợi (Open Question 4 của design) và ghi quyết định
      cùng lý do vào `design.md`.
- [ ] 5.2 Bảng job: định danh, phạm vi, trạng thái, đã xử lý / tổng, thời điểm
      bắt đầu và kết thúc, lý do dừng.
- [ ] 5.3 Tiến trình worker: nhận job, gọi `crawl_product_urls` với đúng tập
      URL của phạm vi, truyền `fetch_options` theo hồ sơ domain.
- [ ] 5.4 Cập nhật tiến độ trong lúc chạy chứ không chỉ lúc xong. Tận dụng điểm
      thu hoạch đơn luồng đã có trong `_crawl_pipelined` thay vì thêm điểm ghi
      mới.
- [ ] 5.5 Xếp hàng: job thứ hai đợi, không chạy song song ghi.
- [ ] 5.6 Huỷ job đang chạy; bản ghi đã lưu trước lúc huỷ được giữ.
- [ ] 5.7 Job dừng vì lỗi: trạng thái cuối mang lý do (cạn quota LLM, bị chặn,
      lỗi kỹ thuật).
- [ ] 5.8 Endpoint tạo job (trả định danh ngay) và endpoint tiến độ dạng SSE
      (`text/event-stream`). Không hỏi vòng.
- [ ] 5.9 Test: chạy lại đúng phạm vi sau khi huỷ thì số cần crawl bằng số còn
      thiếu, không phải toàn bộ phạm vi.
- [ ] 5.10 Test: chạy lại phạm vi đã đủ thì 0 request mạng, 0 gọi LLM.

## 6. Xuất Excel theo tập chọn (capability `excel-export-selection`)

- [ ] 6.1 `export_selection()` cạnh `export_domain()`: nhận tập bản ghi cắt
      ngang nhiều domain + cách chia sheet. Giữ nguyên `export_domain()`.
- [ ] 6.2 Chia sheet theo đối thủ cho phạm vi danh mục; chia theo `category 1`
      cho phạm vi một nhãn hiệu. Dùng lại `_sheet_name` / `_shorten` đang có
      cho việc rút gọn và làm duy nhất tên sheet.
- [ ] 6.3 Thứ tự sheet mặc định theo số sản phẩm trong phạm vi, giảm dần; nhận
      thứ tự chỉ định từ ngoài.
- [ ] 6.4 Sheet cảnh báo hoạt động như đường xuất theo domain, gom qua nhiều
      domain.
- [ ] 6.5 Test chốt khuôn: header của mọi sheet dữ liệu khớp tuyệt đối 20 cột
      của khuôn tham chiếu, kể cả khoảng trắng thừa trong tên cột.
- [ ] 6.6 Test: `category 1` của bản ghi mang nguyên văn tên site nguồn, không
      bị thay bằng từ khoá tìm kiếm.
- [ ] 6.7 Test đối chiếu: xuất phạm vi một nhãn hiệu cho ra file tương đương
      file sinh bởi `export_domain()` cho domain đó.
- [ ] 6.8 Endpoint xuất file; xuất được khi phạm vi mới crawl một phần, kèm số
      còn thiếu trong phản hồi.

## 7. Xem và so sánh phiên bản (capability `extraction-diff-view`)

- [ ] 7.1 Chuyển phần tính toán của `diff_extractions.py` thành hàm dùng chung
      cho cả CLI lẫn API; CLI giữ nguyên đầu ra hiện tại.
- [ ] 7.2 Endpoint liệt kê các `extractor_version` đã có của một domain, kèm số
      snapshot của mỗi phiên bản.
- [ ] 7.3 Endpoint so hai phiên bản: bảng đếm ba nhóm (vá được / làm hỏng / đổi
      khác) theo từng cột, kèm số snapshot chung.
- [ ] 7.4 Hai phiên bản không có snapshot chung: thông điệp hướng dẫn cách tạo
      phép so hợp lệ, không trả bảng rỗng.
- [ ] 7.5 Báo rõ số bản ghi bị loại khỏi phép so vì không có snapshot (bản nhập
      từ file cũ).
- [ ] 7.6 Endpoint liệt kê ĐẦY ĐỦ sản phẩm của một nhóm thay đổi (không giới
      hạn vài mẫu như CLI).
- [ ] 7.7 Endpoint xem một ô: giá trị trước và sau, kèm URL sản phẩm gốc. Nội
      dung dài thì cắt CÓ BÁO, không cắt âm thầm.

## 8. Giao diện

- [ ] 8.1 Một trang HTML + JS thuần do api phục vụ tĩnh, bind mount từ máy chủ.
      KHÔNG build step, KHÔNG Node, KHÔNG `--reload` — sửa file rồi F5.
- [ ] 8.2 Màn tìm kiếm: một ô nhập, hiện loại phạm vi đã phân loại, cho chuyển
      loại khi từ khoá khớp nhiều loại.
- [ ] 8.3 Màn xác nhận phạm vi: liệt kê mọi danh mục của các domain liên quan,
      tick sẵn phần khớp, cho tick thêm/bỏ. Hiện tổng / đã có / còn thiếu theo
      từng domain. Lựa chọn KHÔNG được lưu lại giữa hai lần tìm.
- [ ] 8.4 Màn tiến độ job dùng `EventSource`: trạng thái, đã xử lý / tổng, sản
      phẩm đang xử lý, nút huỷ. Đóng và mở lại trình duyệt vẫn thấy đúng tiến
      độ; dòng sự kiện đứt thì tự nối lại, không kẹt ở số cũ.
- [ ] 8.5 Màn domain: danh sách sản phẩm, lọc theo trạng thái và theo "cần xử
      lý tay". Domain chưa có dữ liệu thì mời chạy crawl.
- [ ] 8.6 Màn so sánh: chọn hai phiên bản, xem bảng đếm, bấm một con số để
      xuống danh sách sản phẩm, bấm một sản phẩm để xem ô trước/sau.
- [ ] 8.7 Màn xuất file: chọn thứ tự đối thủ (mặc định theo số sản phẩm), tải
      file. Báo số còn thiếu nếu phạm vi chưa crawl đủ.

## 9. Docker (capability `crawl-web-runtime`)

- [ ] 9.1 Image cho api và worker, nền có sẵn thư viện hệ thống cho Chromium.
- [ ] 9.2 Bind mount thư mục giao diện vào container api (phục vụ tĩnh) — không
      cần image riêng, không cần Node.
- [ ] 9.3 `docker-compose.yml`: api + worker + volume cho `crawl.db`. KHÔNG dịch
      vụ nào bật `--reload`.
- [ ] 9.4 Khoá LLM và file xác thực nạp lúc chạy qua biến môi trường / volume,
      không nướng vào image. Cập nhật `.env.example`.
- [ ] 9.5 Kiểm tra cấu hình lúc khởi động: thiếu khoá LLM thì báo lỗi ngay, hỏng
      sớm thay vì hỏng giữa lượt crawl.
- [ ] 9.6 Chặn nhân bản worker, hoặc nêu rõ ràng buộc một tiến trình ghi duy
      nhất trong cấu hình và tài liệu.
- [ ] 9.7 Kiểm chứng bằng tay: sửa một file giao diện rồi F5 là thấy, không dựng
      lại image; sửa mã nguồn trong lúc một job đang chạy thì job KHÔNG bị ngắt.
- [ ] 9.8 Kiểm chứng bằng tay: xoá và dựng lại container thì snapshot và kết
      quả trích xuất vẫn còn.

## 10. Tài liệu

- [x] 10.1 `docs/pipeline.md`: thêm mục tầng 0.5 (chỉ mục danh mục) kèm số đo
      thật thu được ở 2.9.
- [ ] 10.2 `README.md`: cách chạy bằng Docker, đặt cạnh đường CLI hiện có —
      đường CLI vẫn là đường lui và phải còn chạy được.
- [ ] 10.3 `docs/todo.md`: ghi lại việc đã cắt khỏi đợt này, rõ nhất là so sánh
      "đối thủ đổi trang" (snapshot vs snapshot), kèm lý do dữ liệu đã sẵn sàng
      mà chưa có công cụ.
