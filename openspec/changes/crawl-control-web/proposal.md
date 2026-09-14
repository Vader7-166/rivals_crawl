## Why

Crawler hiện chỉ điều khiển được bằng CLI, và mọi lệnh đều lấy **một domain**
làm đơn vị: `crawl_site.py <base_url>`, `export_excel.py <domain>`,
`reextract.py <domain>`. Muốn dùng được, người thao tác phải nhớ sẵn domain nào
đã crawl, domain nào chưa, và trong domain đó còn thiếu gì.

Hai việc mà mô hình "một domain một lệnh" không làm được:

1. **Chọn phạm vi cắt ngang nhiều đối thủ.** Câu hỏi thật của người dùng là
   "lấy hàng downlight của các đối thủ", nhưng mỗi đối thủ gọi downlight bằng
   một tên khác: KingLED có 3 danh mục (`ĐÈN DOWNLIGHT ÂM TRẦN`,
   `ĐÈN LED ÂM TRẦN`, `ĐÈN SPOTLIGHT ÂM TRẦN`), TLC có 10. Không có đường nào
   đi từ một từ khoá tới tập URL cần crawl.
2. **So sánh hai lần chạy.** Kho dữ liệu sinh ra chính vì việc này, nhưng
   `diff_extractions.py` chỉ in ra bảng đếm cộng 3 URL mẫu — muốn biết một ô
   đổi từ gì sang gì thì phải tự mở SQLite.

Thêm nữa, một lượt crawl mất 30–70 phút (đo thật: KingLED 549 SP ~70 phút, TLC
485 SP ~33 phút). Đó là thời lượng cần một giao diện có tiến độ, không phải một
terminal bị chiếm.

## What Changes

- **Chỉ mục danh mục trước khi crawl.** Site probing hiện **vứt bỏ** các
  sitemap taxonomy (TLC `product_cat-sitemap.xml` — 73 trang danh mục; KingLED
  `sitemap.xml?page=ProductGroup` — 138 trang). Việc loại chúng khỏi danh sách
  sản phẩm là **đúng** và giữ nguyên, nhưng thay vì vứt, URL của chúng được giữ
  vào `ProbeResult.listing_urls` (field đã tồn tại, hiện luôn rỗng). Duyệt
  ~211 trang này dựng được cạnh (danh mục ↔ URL sản phẩm) — biết một URL thuộc
  danh mục nào **trước khi** tốn một lượt fetch nào cho nó.
- **Một ô tìm kiếm làm bộ chọn phạm vi.** Từ khoá được tự phân loại thành nhãn
  hiệu / danh mục / tên sản phẩm bằng khớp trên hai tập đóng (danh sách domain
  đã đăng ký, tên danh mục từ chỉ mục trên). Kết quả hiện rõ: khớp vào đâu, đã
  có bao nhiêu trong kho, còn thiếu bao nhiêu — rồi mới quyết định crawl.
- **Crawl chạy như job nền có tiến độ**, thay vì chiếm một terminal 70 phút.
  Cơ chế crawl-lại-có-chọn-lọc và checkpoint hiện có được giữ nguyên, nên job
  bị ngắt giữa chừng chạy lại là tiếp tục.
- **Xuất Excel cho một tập chọn cắt ngang nhiều domain.** `export_domain()`
  hiện nhận đúng một domain. Khuôn **20 cột giữ nguyên tuyệt đối**; chiều phân
  loại mới chỉ được phép nằm ở tên file và tên sheet.
- **Xem và so sánh hai phiên bản trích xuất trên web**, bấm được vào từng ô để
  thấy giá trị trước/sau — thứ `diff_extractions.py` không làm được.
- **Khởi chạy chung bằng Docker Compose** (frontend + api + worker + volume kho
  dữ liệu), frontend bind-mount và hot reload.

### Không làm trong đợt này

Ghi lại tường minh vì đây là các hướng đã cân nhắc và **chủ động cắt**:

- **Không** so sánh "đối thủ đổi trang" (snapshot vs snapshot). Schema đã tách
  sẵn `page_snapshots` cho việc này và dữ liệu đã tích luỹ, nhưng để đợt sau.
- **Không** dựng bảng ánh xạ ngành hàng chuẩn hoá, cũng **không** dựng bảng xếp
  hạng đối thủ curated, và **không** có màn duyệt/audit cho chúng. Ánh xạ là
  **dữ liệu dẫn xuất** (xoá đi chạy lại probe là có), không phải dữ liệu chủ
  quan phải bảo trì. Nó không đi vào file kết quả — cột `category 1/2/3` vẫn
  giữ nguyên văn của site nguồn — nên ánh xạ sai chỉ làm crawl thừa/thiếu, giá
  sửa là gõ lại từ khoá. Thứ giữ lại là màn **xác nhận lúc dùng**: tick bỏ chỗ
  khớp trượt trước khi tiêu 30–70 phút, không lưu lại gì.
- **Không** đổi khuôn 20 cột của `product_Metadata (1).xlsx`.
- **Không** sửa tầng crawl (`probing` phần chọn URL sản phẩm, `fetch`, tầng
  1/1.5/1.6/2). Toàn bộ việc mới nằm ở tầng chọn phạm vi phía trên và tầng xuất
  file phía dưới.
- **Nhãn hiệu = domain.** Chỉ crawl web chính hãng, không crawl sàn TMĐT / đại
  lý, nên một domain là một nhãn hiệu. Tên nhãn hiệu là **một field mới trong
  `sites/registry.py`**, không phải một cột mới và không suy ra từ tag
  `thuong_hieu` (đo thật: KingLED 0/549 bản ghi có tag này, TLC ra 4 cách viết
  cho cùng một nhãn).
- **Không** xếp hạng đối thủ quyết định crawl ai. Thứ hạng chỉ ảnh hưởng **thứ
  tự sheet** khi xuất file: hạng sai thì sửa thứ tự và xuất lại trong 10 giây,
  còn để hạng sai quyết định crawl thì mất hẳn dữ liệu và phải crawl lại 30–70
  phút. Mặc định xếp theo số sản phẩm đo được từ chỉ mục danh mục.

## Capabilities

### New Capabilities

- `category-index`: giữ URL trang danh mục vào `listing_urls` (không trộn vào
  `product_urls`), duyệt chúng để dựng và tra cứu chỉ mục (danh mục ↔ URL sản
  phẩm) theo domain. Là cache dẫn xuất, dựng lại được từ đầu.
- `crawl-scope-search`: một ô tìm kiếm, tự phân loại từ khoá thành nhãn hiệu /
  danh mục / tên sản phẩm, trả về phạm vi crawl kèm số đã có / còn thiếu, và
  cho tick bỏ phần khớp trượt trước khi chạy. Bao gồm field tên nhãn hiệu trong
  `sites/registry.py`.
- `crawl-job-runner`: chạy crawl như job nền có tiến độ và huỷ được, bảo toàn
  ràng buộc **một tiến trình ghi duy nhất** vào `crawl.db`.
- `extraction-diff-view`: xem một lượt crawl và so sánh hai `extractor_version`
  trên cùng snapshot, bấm được vào từng ô để xem giá trị trước/sau.
- `excel-export-selection`: xuất một tập chọn cắt ngang nhiều domain ra `.xlsx`,
  khuôn 20 cột giữ nguyên tuyệt đối, chiều phân loại mới chỉ nằm ở tên file và
  tên sheet.
- `crawl-web-runtime`: khởi chạy toàn bộ bằng Docker Compose — frontend (bind
  mount + hot reload), api, worker tách tiến trình, volume cho `crawl.db`, khoá
  LLM không nướng vào image.

### Modified Capabilities

Không có. Các capability đã có (`site-probing`, `stealth-fetch`,
`structured-data-extraction`, `llm-attribute-normalization`,
`product-record-schema`, `crawl-data-store`, `excel-export-from-store`) giữ
nguyên yêu cầu. Phần mở rộng của probing phát biểu trong `category-index`, phần
mở rộng của xuất file phát biểu trong `excel-export-selection` — cả hai chỉ
thêm hành vi mới, không hạ hay đổi yêu cầu cũ. `export_domain()` hiện có vẫn
chạy nguyên như trước.

## Impact

**Code đụng tới**

| Chỗ | Kiểu đụng |
|---|---|
| `src/crawler/probing/sitemap.py`, `prober.py`, `cache.py` | Thêm: giữ URL taxonomy vào `listing_urls`. Bộ lọc `_TAXONOMY_SITEMAP` **không được nới** — nới là tái hiện bug 559-thay-vì-486 đã ghi trong `docs/pipeline.md` |
| `src/crawler/sites/registry.py` | Thêm một field `brand_name` vào `SiteProfile` |
| `src/crawler/store/export.py` | Thêm đường xuất theo tập chọn, cạnh `export_domain()` đang có |
| `src/crawler/` phần còn lại | **Không đụng** |
| Mới | Tầng web (api + worker + frontend), chỉ đọc/ghi qua `CrawlStore` |

**Hạ tầng / phụ thuộc**

- Web framework + worker nền, `Dockerfile` + `docker-compose.yml`.
- Image phải có thư viện hệ thống cho Chromium (Playwright).
- `crawl.db` thành volume; WAL cho phép nhiều tiến trình đọc song song với
  **một** tiến trình ghi. Nhân bản worker lên 2 là dính `database is locked`.

**Ba cái bẫy đã biết**

1. `StealthFetcher` dùng `sync_playwright()` — không sống chung với event loop
   async. Worker **bắt buộc** là tiến trình riêng.
2. `uvicorn --reload` ở container worker sẽ giết ngang một lượt crawl 70 phút.
   `--reload` chỉ đặt ở frontend và api; worker không bật.
3. `CLOAKBROWSER_EXECUTABLE_PATH` hiện để trống (đang chạy Chromium thường) nên
   container hoá được. Ngày nào trỏ nó tới binary trên máy host thì phải đưa
   binary vào image.
