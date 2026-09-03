# rivals_crawl

Crawl dữ liệu sản phẩm từ website đối thủ, chuẩn hoá về đúng khuôn 20 cột của
`datasets/product_Metadata (1).xlsx` (sheet "2. LED Downlight").

Chi tiết từng tầng của pipeline: [docs/pipeline.md](docs/pipeline.md).
Việc còn nợ: [docs/todo.md](docs/todo.md).

## Cài đặt

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/playwright install chromium
cp .env.example .env      # điền khoá LLM + đường dẫn cloakBrowser
```

## Luồng chạy

```
  crawl_site.py <base_url>        →  kho dữ liệu (crawl.db)  →  export_excel.py <domain>
  ─────────────────────────          ────────────────────       ──────────────────────
  probing → fetch → tầng 1/1.5/2     HTML + kết quả trích        file .xlsx đúng khuôn
                                     xuất, có phiên bản          20 cột + sheet cảnh báo
```

```bash
.venv/bin/python scripts/crawl_site.py https://kingled.com.vn
.venv/bin/python scripts/export_excel.py kingled.com.vn
```

## Kho dữ liệu

`crawl.db` (SQLite, 1 file) là **nguồn sự thật**; file `.xlsx` là bản kết xuất.
File này **không nằm trong git** (~100 MB khi đủ 3 site) — dựng lại từ các file
`.xlsx` đã có:

```bash
.venv/bin/python scripts/import_legacy.py output/*.xlsx
```

Bản ghi nhập theo cách này **không có HTML kèm theo** (trước khi có kho, HTML bị
vứt ngay sau khi trích xuất), nên không chạy lại trích xuất được. Kho HTML bắt
đầu tích luỹ từ lượt crawl kế tiếp.

Ba bảng, tách **hai lịch sử khác bản chất** — xem
[design.md](openspec/changes/product-database/design.md) mục 2:

| Bảng | 1 dòng = | Trả lời |
|---|---|---|
| `page_snapshots` | 1 lần **fetch** | đối thủ đổi trang chưa? |
| `extractions` | 1 lần **trích xuất** | code mình đổi kết quả thế nào? |
| `products` (VIEW) | trạng thái hiện tại | bản mới nhất trên snapshot mới nhất |

## Sửa bộ trích xuất mà không phải crawl lại

Đây là lý do chính kho dữ liệu tồn tại:

```bash
.venv/bin/python scripts/reextract.py kingled.com.vn --version v2
.venv/bin/python scripts/diff_extractions.py kingled.com.vn v1 v2
```

`reextract` chạy lại tầng 1/1.5/1.6 trên HTML đã lưu — **0 request mạng, 0 quota
LLM** (kết quả tầng 2 được mang theo từ lần trích xuất trước). Đo thật: 549
trang trong 203 giây, so với ~35 phút của một lượt crawl lại.

`diff_extractions` trả lời câu hỏi mà trước đây không trả lời được: chỉnh sửa
vừa rồi **vá được mấy ô và làm hỏng mấy ô**.

## Kiểm thử

```bash
.venv/bin/python -m pytest tests/ -q
```
