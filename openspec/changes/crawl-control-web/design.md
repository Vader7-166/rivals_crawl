## Context

Dự án hiện là một pipeline crawl chạy bằng CLI, đã chín ở phần khó: probing,
fetch chống chặn, bốn tầng trích xuất, kho dữ liệu tách hai lịch sử, cơ chế
crawl-lại-có-chọn-lọc. Dữ liệu thật đang có trong kho: KingLED 549 sản phẩm,
TLC 485 sản phẩm.

Điều còn thiếu không nằm ở tầng crawl mà nằm hai đầu của nó:

```
   ┌─── ĐANG THIẾU ────────────────────────────────┐
   │ đi từ "hàng downlight của các đối thủ"        │
   │ tới tập URL cần crawl                         │
   └───────────────────┬───────────────────────────┘
                       ▼
   ┌───────────────────────────────────────────────┐
   │  TẦNG CRAWL — đã chín, KHÔNG ĐỤNG              │
   │  probing · fetch · t1/1.5/1.6/2 · store        │
   └───────────────────┬───────────────────────────┘
                       ▼
   ┌─── ĐANG THIẾU ────────────────────────────────┐
   │ xuất file cắt ngang nhiều đối thủ             │
   │ so sánh hai lần chạy tới mức từng ô           │
   └───────────────────────────────────────────────┘
```

Ràng buộc cứng, kế thừa từ các change trước và không thương lượng lại trong đợt
này:

- Khuôn 20 cột của `product_Metadata (1).xlsx` là **định dạng bàn giao**. Không
  thêm cột.
- `category 1/2/3` giữ nguyên văn của site nguồn (spec `product-record-schema`).
- Kho dữ liệu chỉ có **một** người ghi (`store/crawl_store.py`).
- Bộ lọc sitemap taxonomy không được nới (bug 559-thay-vì-486, `docs/pipeline.md`).

## Goals / Non-Goals

**Goals**

- Điều khiển crawl bằng giao diện: chọn phạm vi, chạy, theo dõi, xuất file.
- Đi được từ một từ khoá tới tập URL cần crawl, cắt ngang nhiều đối thủ.
- So sánh hai lần chạy bộ trích xuất tới mức từng ô.
- Khởi chạy bằng một lệnh Docker Compose, sửa giao diện là thấy ngay.
- Tầng crawl không bị sửa một dòng.

**Non-Goals**

- Không so sánh "đối thủ đổi trang" (snapshot vs snapshot) — để đợt sau.
- Không dựng cây ngành hàng chuẩn hoá, không bảng xếp hạng lưu trữ, không quy
  trình phê duyệt.
- Không phân tích/biểu đồ. Đây là bảng điều khiển crawl, không phải BI.
- Không crawl sàn TMĐT/đại lý. Chỉ web chính hãng, nên một domain là một nhãn.
- Không đa người dùng, không phân quyền.

## Decisions

### 1. "Ngành hàng" là một truy vấn, không phải một bảng phải nuôi

**Chọn:** khớp chữ từ khoá trên tên danh mục lấy từ chính site đối thủ. Không
bảng ánh xạ, không dữ liệu do người nhập.

**Đã cân nhắc và bác bỏ:** một bảng `(domain, category_1) → L1/L2` sinh bởi LLM
rồi cho người duyệt và đóng băng.

**Lý do bác bỏ.** Lý do duy nhất để dựng quy trình duyệt là "ánh xạ sai thì lệch
bảng phân tích mà không ai biết". Điều đó chỉ đúng nếu ánh xạ đi vào file kết
quả — nó không đi vào: cột `category 1/2/3` giữ nguyên văn site nguồn, ánh xạ
chỉ dùng để **chọn crawl cái gì**.

| Ánh xạ sai kiểu | Hậu quả | Giá sửa |
|---|---|---|
| Gom dư | Crawl thừa vài chục sản phẩm | ~0 — lần sau crawl-lại-có-chọn-lọc bỏ qua, mà đó cũng là sản phẩm sớm muộn cũng crawl |
| Gom thiếu | Kết quả ít hơn mong đợi, **thấy được ngay** | Gõ lại từ khoá |

Dựng quy trình curation có vết audit để chống một lỗi mà giá sửa là gõ lại từ
khoá là sai cỡ công cụ. Nguyên tắc rút ra, đáng giữ cho các quyết định sau:
**đừng biến dữ liệu dẫn xuất thành dữ liệu chủ quan.** Chỉ mục danh mục dựng
lại được bất cứ lúc nào từ site đối thủ; một bảng người duyệt thì mất là mất và
phải bảo trì mãi.

**Phần giữ lại:** màn xác nhận **lúc dùng**. Khớp chữ có trượt thật — danh mục
`Eyecare Pro` của TLC là đèn âm trần nhưng không chứa từ khoá nào — nên trước
khi tiêu 30–70 phút, người dùng thấy danh sách khớp và tick bỏ. Không lưu lại.

### 2. Chỉ mục danh mục dựng từ thứ probing đang vứt đi

Muốn biết "sản phẩm nào thuộc downlight mà chưa crawl" thì phải biết danh mục
của một URL **trước khi** fetch nó — mà biết được thì đã crawl rồi. Vòng lặp
này phá bằng nguyên liệu đang có sẵn:

```
  TLC      product_cat-sitemap.xml        →  73 trang danh mục
  KingLED  sitemap.xml?page=ProductGroup  → 138 trang danh mục
                                            ─────────────────
                                            211 trang, 0 LLM
```

`_TAXONOMY_SITEMAP` (`probing/sitemap.py:40`) đang loại sạch chúng, và **loại
đúng**. Nhưng "không được lẫn vào danh sách sản phẩm" khác với "phải vứt đi".

**Quyết định:** giữ chúng vào `ProbeResult.listing_urls` — field đã tồn tại
trong dataclass, hiện luôn rỗng vì chỉ nhánh menu-crawl điền mà cả hai site đều
thắng bằng nhánh sitemap. Bộ lọc **không đổi một ký tự**; chỉ thêm đường ghi
vào ngăn thứ hai.

Kiểm chứng bắt buộc: sau thay đổi, số URL sản phẩm phải bằng đúng số cũ
(KingLED 557, TLC 486). Lệch một đơn vị nghĩa là đã nới bộ lọc.

**Đã cân nhắc và bác bỏ:** đọc breadcrumb của từng trang sản phẩm. Đúng hơn
nhưng cần fetch cả 1.034 trang — tức phải crawl trước khi biết crawl gì, đúng
cái vòng lặp đang cần phá.

### 3. Xếp hạng đối thủ chỉ chạm tới thứ tự sheet

Đã tìm nguồn xếp hạng công khai (hiệp hội ngành, dữ liệu tài chính công ty niêm
yết, các báo cáo thị trường). Kết luận, ghi lại để không ai khảo sát lại:

- Các bài "Top 10 hãng đèn LED" đều **do chính người bán viết** — trong đó có cả
  shop của Rạng Đông, và các hãng tự xếp hạng mình. Đưa vào là nhập thiên kiến
  của đối thủ vào công cụ phân tích đối thủ.
- Hiệp hội Chiếu sáng Việt Nam nêu tên các tay chơi lớn nhưng **không công bố
  bảng thị phần**.
- Dữ liệu tài chính đã kiểm toán chỉ có với công ty niêm yết; KingLED và TLC là
  công ty tư nhân, không có mặt.
- **Không nguồn nào xếp hạng theo ngành hàng** — mọi thứ đều ở mức toàn công ty.

Nên thứ hạng là phán đoán của bên nghiệp vụ, tức **không kiểm chứng được**. Với
một đại lượng như thế, để nó quyết định crawl ai là rủi ro bất đối xứng:

```
  hạng sai → quyết định crawl ai      hạng sai → chỉ quyết thứ tự sheet
  ────────────────────────────────    ────────────────────────────────
  mất hẳn dữ liệu                     sheet xếp sai thứ tự
  phát hiện ra → crawl lại 30–70 phút  sửa thứ tự, xuất lại: 10 giây
```

**Quyết định:** thứ hạng nằm ở tầng trình bày. Mặc định xếp theo số sản phẩm đo
được trong phạm vi (số đo thật, không phán đoán); đổi được lúc xuất file. Thứ
tự sheet trong file chính là thứ hạng — mở file ra là đọc được, không tốn cột
nào trong khuôn 20 cột.

### 4. Ba tiến trình, một người ghi

```
  ┌───────────┐   ┌────────────┐   ┌────────────────────┐
  │ giao diện │──▶│ api        │──▶│ worker             │
  │ HTML+JS   │   │ CHỈ ĐỌC    │   │ Playwright đồng bộ │
  │ bind mount│   │ + xếp job  │   │ NGƯỜI GHI DUY NHẤT │
  │ EventSource◀──│ SSE        │◀──│                    │
  └───────────┘   └─────┬──────┘   └─────────┬──────────┘
                        │ đọc               │ ghi
                        ▼                   ▼
                  ┌──────────────────────────────┐
                  │ crawl.db (volume) — WAL       │
                  └──────────────────────────────┘
        KHÔNG dịch vụ nào bật --reload
```

Ba ràng buộc dẫn tới hình này, mỗi cái từ một sự thật đã biết:

1. `StealthFetcher` dùng `sync_playwright()`, không sống chung với vòng lặp bất
   đồng bộ của tầng API → worker **bắt buộc** là tiến trình riêng.
2. `crawl_store.py` chốt "mọi hàm ghi phải gọi từ duy nhất một luồng" → lên
   nhiều container thì thành "duy nhất một tiến trình". Nhân bản worker là dính
   `database is locked` bất kể `busy_timeout`.
3. Một lượt crawl là 33–70 phút, còn cơ chế nạp lại thì khởi động lại tiến
   trình mỗi lần lưu file.

Về (3): cô lập worker sang container riêng đã đủ để `--reload` ở dịch vụ khác
không chạm tới nó. Nhưng **bỏ hẳn `--reload` ở mọi dịch vụ** thì rủi ro về 0 và
bớt một biến phải suy luận mỗi lần đọc lại cấu hình — đánh đổi rẻ, vì thứ mất
đi chỉ là việc phải bấm F5.

WAL cho phép api đọc song song trong lúc worker ghi. Volume phải là ổ local —
WAL không an toàn trên NFS.

**Đã cân nhắc và bác bỏ:** một container gộp cả ba. Đơn giản hơn nhưng không
thoả được (1).

### 4b. Tiến độ đẩy theo dòng (SSE), và điều đó chọn luôn stack giao diện

Yêu cầu "biết đang xử lý tới đâu" trên một tiến trình 33–70 phút loại bỏ kiểu
request/response. Hai đường: hỏi vòng (polling) hay đẩy theo dòng.

**Chọn SSE** (`text/event-stream`). Luồng dữ liệu ở đây là **một chiều** —
worker báo tiến độ, trình duyệt chỉ nghe. WebSocket giải bài toán hai chiều mà
ta không có, đổi lại thêm một giao thức và một tầng quản lý kết nối. SSE tự nối
lại khi đứt, đi qua proxy như HTTP thường, và phía trình duyệt là `EventSource`
— API có sẵn, không thư viện.

**Hệ quả: giao diện là HTML + JS thuần, không build step.** `EventSource` đã có
sẵn nên thứ mà một framework thêm vào (bundler, HMR, component) không mua thêm
gì cho bốn màn hình này, mà lại kéo theo Node vào compose, `package.json`,
`node_modules`, và một bước build đứng giữa "sửa file" với "thấy kết quả".

Bỏ được luôn cả một container. Và vì không có build step, việc bỏ `--reload`
không mất gì: sửa file, bấm F5, xong.

**Đã cân nhắc và bác bỏ:** React + Vite. HMR của Vite là lý do chính để chọn nó,
mà ta vừa quyết định bỏ cơ chế nạp lại — nên nó chỉ còn lại phần chi phí.

### 5. Tìm kiếm: khớp từ điển trước, toàn văn sau

Hai tập đóng và nhỏ: nhãn hiệu (vài chục dòng trong `sites/registry.py`) và tên
danh mục (~211 từ chỉ mục). Khớp từ điển trên hai tập đó trước; không khớp thì
coi là tên sản phẩm và tìm trên tên trong kho.

Không dùng LLM ở khâu này: kết quả phải tất định và giải thích được ("từ khoá
này khớp vào 3 danh mục sau"), và phải trả lời tức thì.

Không dựng chỉ mục toàn văn (FTS5) trong đợt này: kho đang 1.034 sản phẩm, so
khớp trên tên đã chuẩn hoá bỏ dấu là tức thì. FTS5 lại không tách được từ ghép
tiếng Việt nên lợi ích cũng nhỏ hơn vẻ ngoài. Dựng khi kho lên hàng chục nghìn.

### 6. Nhãn hiệu là một dòng dữ liệu, không suy từ trang

Đo trên dữ liệu thật: tag `thuong_hieu` vắng ở **549/549** bản ghi KingLED, và
trên TLC cho ra bốn cách viết (`TLC LIGHTING`, `TLC`, `TLC Lighting`,
`TLC LIGHTING, TLC Lighting`) cho cùng một nhãn. Suy nhãn hiệu từ tag là vừa
thiếu vừa bẩn.

Thêm một field `brand_name` vào `SiteProfile`. Đúng nguyên tắc đã chốt của dự
án: thêm một đối thủ là thêm **một dòng dữ liệu**, không phải một module.

## Risks / Trade-offs

**[Nới nhầm bộ lọc taxonomy khi thêm `listing_urls`]** → Bug 559-thay-vì-486
quay lại: trang danh mục lọt vào danh sách sản phẩm, tốn fetch và LLM để sinh
bản ghi rỗng. *Giảm thiểu:* test chốt số URL sản phẩm không đổi (KingLED 557,
TLC 486) chạy trước khi đụng vào `sitemap.py`.

**[Khớp chữ trượt danh mục đặt tên riêng]** → `Eyecare Pro`, `Galaxy`, `Radar`
là đèn nhưng tên không mang từ khoá nào. *Giảm thiểu:* màn xác nhận liệt kê
**mọi** danh mục của domain, phần khớp được tick sẵn, phần còn lại tick thêm
được. Trượt thì thấy, không lặng lẽ.

**[Trang danh mục không liệt kê đủ sản phẩm]** → Vài site chỉ hiện sản phẩm còn
hàng, hoặc nạp thêm bằng JS. Chỉ mục thiếu → phạm vi thiếu. *Giảm thiểu:* đối
chiếu tổng số URL trong chỉ mục với số URL từ sitemap; chênh lệch báo ra, và
URL không thuộc danh mục nào vẫn tra cứu được ở mức toàn domain.

**[Worker là điểm chết đơn]** → Worker chết là mọi lượt crawl dừng. *Chấp nhận:*
đây là hệ quả trực tiếp của ràng buộc một người ghi, không phải sơ suất. Cơ chế
crawl-lại-có-chọn-lọc làm việc khởi động lại rẻ — chạy lại là chạy tiếp.

**[Một lượt crawl vẫn mất 30–70 phút]** → Giao diện không rút ngắn được, vì
điểm nghẽn là fetch tuần tự và fetch tuần tự là cố ý (đo được: fetch song song
làm **chậm đi** và gây timeout). *Giảm thiểu:* cho xuất phần dữ liệu đang có
ngay, không bắt chờ crawl xong.

**[Xuất file khi phạm vi mới crawl một phần]** → Người nhận có thể tưởng file là
đầy đủ. *Giảm thiểu:* báo số còn thiếu lúc xuất; sheet cảnh báo đã có sẵn cho
phần cần xử lý tay.

## Migration Plan

Không có dữ liệu nào phải chuyển đổi: kho giữ nguyên schema, tầng crawl giữ
nguyên hành vi. Triển khai theo lớp, mỗi lớp tự đứng được:

1. `listing_urls` + chỉ mục danh mục. Kiểm chứng bằng test chốt số URL sản phẩm
   không đổi. Chưa có giao diện, chạy bằng CLI.
2. Tầng API chỉ đọc + tìm kiếm + tra cứu phạm vi. Vẫn crawl bằng CLI.
3. Worker + job nền. Từ đây crawl được từ giao diện.
4. `export_selection` + màn so sánh phiên bản.
5. Docker Compose gộp cả bốn.

Đường CLI hiện có (`crawl_site.py`, `export_excel.py`, `reextract.py`,
`diff_extractions.py`) giữ nguyên và chạy được suốt quá trình. Đó cũng là đường
lui: hỏng tầng web thì quay về CLI, không mất dữ liệu.

## Open Questions

1. **Xuất phần đang có hay chờ crawl xong?** Đã nghiêng về "xuất ngay phần đang
   có + báo số còn thiếu", nhưng chưa xác nhận với người dùng cuối. Chốt lúc
   dựng màn xuất file.
2. **Chỉ mục danh mục làm mới khi nào?** Thủ công, hay tự làm mới sau một
   khoảng thời gian? Bắt đầu bằng thủ công; thêm tự động khi biết đối thủ đổi
   danh mục thường xuyên đến mức nào.
3. **Phân trang danh mục dừng ở đâu?** Trần 20 trang/danh mục giữ nguyên từ bản
   pilot. Đo trên 5 danh mục thật của mỗi site chưa lần nào chạm trần, nhưng
   chưa đo trên cả 211 danh mục.
4. **Job nền dùng cơ chế nào?** Hàng đợi trong chính SQLite (không thêm phụ
   thuộc, hợp với quy mô một người ghi) hay một hàng đợi riêng. Nghiêng về cái
   đầu; chốt ở bước 3 của Migration Plan.

## Phụ lục: số đo trên site thật (04/09/2026)

Chạy `scripts/build_category_index.py --limit 5` trên cả hai site:

| | KingLED | TLC |
|---|---|---|
| URL sản phẩm từ sitemap | 557 | 486 |
| Trang danh mục giữ lại được | 138 | 73 |
| Cạnh thu được / 5 danh mục | 39 | 138 |

Hai cột đầu **khớp tuyệt đối** với số đã ghi trong `docs/pipeline.md` từ trước —
xác nhận việc giữ `listing_urls` không làm xê dịch danh sách sản phẩm.

**Một lỗi phát hiện nhờ chạy thật:** truyền `profile.fetch_options` (hiệu chỉnh
cho trang **sản phẩm**) sang trang **danh mục** làm mỗi trang đứng chờ hết 5s
timeout cho một selector không thể xuất hiện. Đo A/B trên cùng 5 danh mục
KingLED: **11,6s so với 37,6s**, cạnh thu được **giống hệt** (39) — toàn bộ
chênh lệch là chờ suông. Ngoại suy cả 138 danh mục: ~12 phút. Đã tách thành
`SiteProfile.listing_fetch_options` riêng.
