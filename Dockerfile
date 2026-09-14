# Một image dùng chung cho CẢ api LẪN worker.
#
# Không tách hai image dù chúng chạy hai lệnh khác nhau: cả hai nhập cùng gói
# `crawler`, nên tách ra chỉ được một image nhẹ hơn vài chục MB, đổi lại hai
# Dockerfile phải giữ cho khớp nhau. Thứ khác nhau giữa hai dịch vụ là LỆNH
# CHẠY, và lệnh chạy thuộc về compose.
#
# Ảnh nền là image Playwright chính thức: nó đã mang sẵn Chromium cùng toàn bộ
# thư viện hệ thống mà trình duyệt cần (libnss3, libatk, libgbm…). Tự cài đống
# đó lên một ảnh Python trần là chép lại một danh sách mà Playwright vốn đã
# công bố, và danh sách đó đổi theo từng bản.
#
# THẺ PHIÊN BẢN PHẢI KHỚP với gói `playwright` mà pip cài ở dưới. Trình duyệt
# nằm trong image dưới một đường dẫn có đánh số bản dựng
# (`/ms-playwright/chromium_headless_shell-<số>`), và thư viện đi tìm đúng số
# của riêng nó. Lệch một bản là worker chết ngay lần fetch đầu với
# "Executable doesn't exist" — đã gặp thật khi image v1.56 gặp thư viện v1.62.
#
# Nên `playwright` được ghim ở ngay đây, cạnh thẻ image, để hai con số này
# không thể trôi khỏi nhau một cách lặng lẽ.
FROM mcr.microsoft.com/playwright/python:v1.62.0-noble

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Kho dữ liệu nằm trên volume, KHÔNG nằm trong image: xoá và dựng lại
    # container thì snapshot và kết quả trích xuất vẫn còn.
    CRAWL_DB_PATH=/data/crawl.db \
    OUTPUT_DIR=/data/output \
    HTML_DIR=/data/output/html

# Cài phụ thuộc TRƯỚC khi chép mã nguồn: sửa một dòng trong `src/` thì lớp này
# còn nguyên trong cache, không phải tải lại toàn bộ gói.
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e ".[web]" "playwright==1.62.0"

COPY scripts/ ./scripts/

# Không khai `CMD` mặc định: hai dịch vụ chạy hai lệnh khác nhau và compose
# khai rõ từng cái. Một CMD mặc định ở đây chỉ tạo ra một đường chạy thứ ba mà
# không ai dùng nhưng vẫn phải bảo trì.
