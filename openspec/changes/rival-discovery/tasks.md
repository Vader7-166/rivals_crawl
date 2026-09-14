## 1. Tầng tìm kiếm

- [x] 1.1 Đo xem nguồn nào lấy được kết quả không cần khoá API. Ghi số đo vào
      docstring. (Bing 16 domain; DuckDuckGo html/lite đều 0 → trang chặn.)
- [x] 1.2 `SearchEngine` trừu tượng + `BingEngine`. Đổi nguồn không được đòi sửa
      tầng trên.
- [x] 1.3 Gỡ lớp bọc redirect của Bing (`/ck/a?u=a1<base64url>`). Không gỡ thì
      mọi kết quả đều mang domain `www.bing.com`.
- [x] 1.4 Chuỗi giải mã không ra URL thì trả về link gốc. `b64decode` **bỏ qua**
      ký tự không hợp lệ thay vì báo lỗi, nên rác giải mã "thành công" ra chuỗi
      rỗng và ứng viên biến mất không dấu vết.
- [x] 1.5 Một truy vấn hỏng không làm hỏng cả đợt; không đọc được kết quả nào
      thì cảnh báo là có thể đang bị chặn.
- [x] 1.6 `StaticEngine` để test không chạm mạng.

## 2. Tầng truy vấn

- [x] 2.1 Đo mẫu truy vấn trên Bing, ghi số đo. Kết luận: truy vấn phải là TÊN
      LOẠI HÀNG, không phải mô tả loại hình doanh nghiệp.
- [x] 2.2 Dựng truy vấn từ tên danh mục trong kho.
- [x] 2.3 Bỏ tên nhãn khỏi truy vấn. Lỗi đo được khi chạy thật: giữ nguyên
      `Đèn LED Âm Trần VinaLED` thì chỉ ra site của chính VinaLED.
- [x] 2.4 Xếp truy vấn theo số đối thủ cùng có danh mục đó, thay vì lấy 6 cái
      đầu danh sách (phụ thuộc thứ tự alphabet của domain).
- [x] 2.5 Truy vấn tìm lại một nhãn luôn kèm từ neo của ngành.

## 3. Tầng chấm điểm

- [x] 3.1 Tập đóng loại thẳng: sàn TMĐT, mạng xã hội, từ điển, site của chính
      mình.
- [x] 3.2 Đo tín hiệu "số nhãn trên trang chủ". Kết quả: sai cả hai chiều
      (kingled 5 nhãn là NSX; ledhome 0 nhãn là đại lý) → giữ với trọng số nhẹ,
      không bao giờ đủ một mình để lật kết quả.
- [x] 3.3 Loại tín hiệu "tên miền mang từ riêng": `ledxanh` và
      `thegioidentrangtri` được điểm y hệt `kingled` vì cả ba đều là một từ
      ghép liền không tách được. Tín hiệu vô dụng.
- [x] 3.4 Thêm tín hiệu TỪ VỰNG nhà sản xuất / bán lẻ. Đo trên 9 site đã biết:
      tách đúng 7/9, 2 ca còn lại rơi vào vùng 0 điểm (không ai bị đẩy sai
      hướng). Vùng mờ cho 0 điểm chứ không đoán.
- [x] 3.5 Hạ trọng số thứ hạng tìm kiếm. Thứ hạng đo SEO, và đại lý đầu tư SEO
      mạnh hơn nhà sản xuất — để nó nặng là thưởng đúng cái cần loại (đo thật:
      ledxanh.vn đứng đầu chỉ nhờ hạng 1 + ra ở 6 từ khoá).
- [x] 3.6 Tách "có structured data" khỏi "có giá". Structured data là tín hiệu
      mạnh nhất và mạnh vì lý do thực dụng: tầng 1 đọc đúng thứ đó, site có nó
      là site crawl được ngay.
- [x] 3.7 Mỗi tín hiệu mang một câu giải thích nêu số đo.

## 4. Ghép và giao diện

- [x] 4.1 `tim_doi_thu()` và `tim_lai_site()` dùng chung một bộ máy.
- [x] 4.2 Domain đã đăng ký được đánh dấu, không bị loại.
- [x] 4.3 Chỉ tải trang cho các ứng viên có cơ hội vào top, không tải hết.
- [x] 4.4 `scripts/find_rivals.py`.
- [x] 4.5 Endpoint `/api/discover` + một màn trong giao diện.
- [x] 4.6 Test không chạm mạng (19 test).

## 5. Tài liệu

- [x] 5.1 `crawl_list.md`: cách tìm đối thủ mới và kiểm tra site cũ còn sống.
- [x] 5.2 `README.md`: thêm lệnh vào mục giao diện web.
