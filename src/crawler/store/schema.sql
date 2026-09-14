-- Kho du lieu crawl (capability `crawl-data-store`).
--
-- Hai LICH SU khac ban chat duoc tach thanh hai bang, day la quyet dinh trung
-- tam cua thiet ke (xem design.md muc 2):
--
--     doi thu doi trang            MINH doi code
--           |                            |
--           v                            v
--     page_snapshots  --- 1:N --->  extractions  --- 1:N --->  product_tags
--     (1 dong / FETCH)              (1 dong / TRICH XUAT)
--
-- Gop chung vao mot bang `products` ghi de thi khi mot gia tri khac di so voi
-- lan truoc, KHONG phan biet duoc "doi thu ha gia" voi "minh vua sua parser".
-- Tach ra thi phan biet duoc ngay: snapshot doi -> ho doi; snapshot y nguyen
-- ma extraction doi -> minh doi.

PRAGMA foreign_keys = ON;


CREATE TABLE IF NOT EXISTS sites (
    domain   TEXT PRIMARY KEY,
    base_url TEXT
);


-- 1 dong = 1 lan fetch thanh cong 1 trang san pham.
--
-- LUU MOI TRANG, khong chi trang trich xuat hong (design.md muc 3): o SAI MA
-- TUONG DUNG khong tu khai bao - pipeline coi no la thanh cong nen se khong
-- luu HTML, tuc dung ca can soi nhat lai la ca khong co du lieu de soi.
CREATE TABLE IF NOT EXISTS page_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,

    -- KHOA DINH DANH SAN PHAM. Luu NGUYEN VAN nhu site cong bo.
    --
    -- KHONG duoc chuan hoa - dac biet KHONG duoc cat dau "/" cuoi. Day la quy
    -- uoc RIENG cua tung site: ca 486 URL cua tlclighting.com.vn (WooCommerce)
    -- ket thuc bang "/", con kingled.com.vn thi khong URL nao co. Cat no di la
    -- doi chinh DANH TINH ban ghi -> co che crawl-lai-co-chon-loc doi chieu
    -- theo URL se mat khop va moi lan chay sau deu phai crawl lai tu dau.
    -- Xem them docstring `select_product_urls` o sites/registry.py.
    url         TEXT    NOT NULL,
    domain      TEXT    NOT NULL REFERENCES sites(domain),

    fetched_at  TEXT    NOT NULL,   -- ISO-8601 UTC
    http_status INTEGER,
    final_url   TEXT,               -- sau chuyen huong, co the khac `url`

    -- HTML nen bang zlib. Ti le nen do that tren fixture: 8,8x (KingLED) /
    -- 4,8x (TLC) / 3,9x (Roman).
    html_gz     BLOB    NOT NULL,
    html_len    INTEGER NOT NULL    -- do dai ky tu TRUOC khi nen
);

CREATE INDEX IF NOT EXISTS idx_snapshots_url ON page_snapshots (url, id DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_domain ON page_snapshots (domain);


-- 1 dong = 1 lan chay bo trich xuat tren 1 snapshot.
--
-- Ten cot la ten SACH, KHONG phai ten cot Excel: khuon 20 cot trong
-- record/schema.py mang ca khoang trang thua cua file tham chieu
-- (" category 1 ", "Thong so ky thuat ") - do la DINH DANG BAN GIAO, khong
-- phai mo hinh du lieu. `COLUMNS` van giu vai tro lop anh xa khi ghi ra file.
--
-- Cot `stt` KHONG co mat: so thu tu la thuoc tinh cua DONG trong file xuat ra,
-- khong phai du lieu san pham.
CREATE TABLE IF NOT EXISTS extractions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    url               TEXT NOT NULL,          -- nguyen van, xem chu thich tren
    domain            TEXT NOT NULL REFERENCES sites(domain),

    -- NULL = ban ghi nhap tu file .xlsx cu, KHONG co HTML kem theo nen khong
    -- chay lai trich xuat duoc (design.md muc Risks). Phan biet duoc bang
    -- `extractor_version = 'imported-xlsx'`.
    snapshot_id       INTEGER REFERENCES page_snapshots(id),
    extractor_version TEXT NOT NULL,
    extracted_at      TEXT NOT NULL,          -- ISO-8601 UTC

    product_id             TEXT,
    ten_san_pham           TEXT,
    ma_san_pham            TEXT,
    ma_sap                 TEXT,
    category_1             TEXT,
    category_2             TEXT,
    category_3             TEXT,
    -- Gia tri-state: so (REAL), literal "Lien he" (TEXT), hoac NULL khi chua
    -- xac dinh duoc do loi crawl. SQLite kieu dong nen luu thang duoc ca ba.
    gia                    ,
    gia_doi_chieu          ,
    link_anh_san_pham      TEXT,
    link_mua_hang_online   TEXT,
    link_file_hdsd         TEXT,
    tom_tat_tskt           TEXT,
    thong_so_ky_thuat      TEXT,
    vd_hdsd                TEXT,
    tom_tat_uu_diem_tinh_nang TEXT,
    noi_dung_uu_diem_sp       TEXT,

    -- LA BAN do tang 2 (LLM) chi ra: dung MOT DONG co that tren trang, dung de
    -- dinh vi muc uu diem (xem quy tac 9 cua prompt). Luu lai la BAT BUOC de
    -- chay lai trich xuat khong can goi LLM: khong co no thi moi lan chay lai
    -- deu mat nhanh 'anchor', va `diff_extractions` se bao hoi quy GIA o moi o
    -- von tim thay nho la ban - tuc phep so mat y nghia.
    uu_diem_la_ban    TEXT,

    -- Duong nao da dinh vi duoc muc uu diem: 'keyword' | 'anchor' | 'cluster'
    -- | 'none'. `extract_advantages` da BIET nhanh nao thang roi vut di; giu
    -- lai thi "6 o sai nam dau" thanh mot cau truy van thay vi mot buoi mo tay
    -- 360 o, va mon no ky thuat o nhanh cum tro nen do dem duoc.
    uu_diem_nguon     TEXT NOT NULL DEFAULT 'none',

    crawl_status      TEXT NOT NULL,          -- ok | error | partial-missing-fields
    crawl_error       TEXT
);

CREATE INDEX IF NOT EXISTS idx_extractions_url ON extractions (url, id DESC);
CREATE INDEX IF NOT EXISTS idx_extractions_domain ON extractions (domain);
CREATE INDEX IF NOT EXISTS idx_extractions_version ON extractions (extractor_version);
CREATE INDEX IF NOT EXISTS idx_extractions_snapshot ON extractions (snapshot_id);


-- `tags` dang key-value thay vi mot cot JSON: spec llm-attribute-normalization
-- da chot "schema thuoc tinh linh hoat theo site/category" - so luong va ten
-- key khac nhau giua cac san pham. Dang nay giu nguyen tinh linh hoat do ma
-- van truy van duoc ("bao nhieu SP cong bo CRI?", "phan bo nhiet do mau cua
-- doi thu"), von la muc dich cuoi cua ca du an. Khi ghi ra Excel thi gop
-- nguoc lai thanh json.dumps nhu cu.
CREATE TABLE IF NOT EXISTS product_tags (
    extraction_id INTEGER NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
    key           TEXT    NOT NULL,
    value         TEXT,
    PRIMARY KEY (extraction_id, key)
);


-- Trang thai hien tai: ban trich xuat MOI NHAT tren snapshot MOI NHAT moi URL.
--
-- La VIEW chu khong phai bang: view luon dung theo dinh nghia, khong co nguy co
-- lech voi bang nguon nhu mot bang vat chat hoa.
--
-- Thu tu uu tien trong `ORDER BY`:
--   1. `snapshot_id IS NULL` xep SAU  -> ban ghi nhap tu .xlsx cu chi thang khi
--      URL do chua tung co snapshot nao.
--   2. `snapshot_id DESC`             -> snapshot moi nhat (id AUTOINCREMENT
--      tang theo thu tu fetch nen tuong duong `fetched_at` moi nhat).
--   3. `id DESC`                      -> lan trich xuat moi nhat tren chinh
--      snapshot do.
CREATE VIEW IF NOT EXISTS products AS
SELECT * FROM (
    SELECT
        e.*,
        ROW_NUMBER() OVER (
            PARTITION BY e.url
            ORDER BY (e.snapshot_id IS NULL) ASC, e.snapshot_id DESC, e.id DESC
        ) AS rn
    FROM extractions e
)
WHERE rn = 1;


-- CHI MUC DANH MUC (tang 0.5, capability `category-index`).
--
-- KHAC BAN CHAT voi ba bang tren: day la CACHE DAN XUAT, khong phai lich su.
-- Xoa sach hai bang nay roi dung lai tu site doi thu se ra ket qua nhu cu, va
-- khong mat mot du lieu nao do nguoi nhap - vi khong co du lieu nao do nguoi
-- nhap ca. Do la quyet dinh trung tam cua change `crawl-control-web`: anh xa
-- nganh hang KHONG duoc phep tro thanh mot bang phai bao tri (xem design.md
-- muc 1).
--
-- Chung ton tai de tra loi mot cau hoi ma truoc day khong tra loi duoc:
-- "URL nay thuoc danh muc nao?" TRUOC khi ton mot luot fetch cho chinh no.

-- 1 dong = 1 trang danh muc da duyet.
--
-- `ok = 0` (fetch hong) PHAI phan biet duoc voi `ok = 1` ma khong canh nao
-- trong `category_products`: cai dau la "chua biet gi ve danh muc nay", cai sau
-- la "danh muc that su rong". Gop lam mot thi mot danh muc chet mang bi doc
-- thanh mot danh muc khong co hang.
CREATE TABLE IF NOT EXISTS category_pages (
    domain        TEXT    NOT NULL REFERENCES sites(domain),
    url           TEXT    NOT NULL,
    name          TEXT,                       -- lay tu <h1>/<title> cua trang
    indexed_at    TEXT    NOT NULL,           -- ISO-8601 UTC
    pages_fetched INTEGER NOT NULL DEFAULT 0, -- ke ca trang con cua phan trang
    ok            INTEGER NOT NULL DEFAULT 1,
    error         TEXT,
    PRIMARY KEY (domain, url)
);

CREATE INDEX IF NOT EXISTS idx_category_pages_domain ON category_pages (domain);


-- 1 dong = 1 canh (danh muc <-> san pham).
--
-- Mot san pham thuoc nhieu danh muc la chuyen BINH THUONG tren site that, nen
-- khoa chinh gom ca hai dau - khong canh nao ghi de canh nao.
CREATE TABLE IF NOT EXISTS category_products (
    domain       TEXT NOT NULL REFERENCES sites(domain),
    category_url TEXT NOT NULL,
    -- URL NGUYEN VAN nhu sitemap cong bo, KHONG chuan hoa dau `/` cuoi - cung
    -- quy uoc voi `page_snapshots.url` va `extractions.url`, de join duoc.
    product_url  TEXT NOT NULL,
    PRIMARY KEY (domain, category_url, product_url),
    FOREIGN KEY (domain, category_url) REFERENCES category_pages (domain, url) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_category_products_url ON category_products (product_url);
CREATE INDEX IF NOT EXISTS idx_category_products_cat ON category_products (domain, category_url);


-- HANG DOI JOB (capability `crawl-job-runner`).
--
-- Hang doi nam trong chinh file nay chu khong o mot broker rieng - quyet dinh
-- va ly do day du o design.md Open Question 4. Tom tat: rang buoc MOT NGUOI GHI
-- da loai bo phan kho cua bai toan hang doi, nen ca viec nay rut lai thanh "lay
-- job cho lau nhat", va mot broker rieng chi them mot tien trinh phai nuoi.
--
-- Job va du lieu no sinh ra nam cung mot file: mot lan sao luu, mot lan khoi
-- phuc. Hang doi ngoai thi khoi phuc kho ve moc cu la lech voi hang doi.
CREATE TABLE IF NOT EXISTS jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Pham vi da CHOT thanh danh sach URL, luu JSON. Chot o luc TAO job chu
    -- khong tra cuu lai luc chay: nguoi dung da nhin thay con so "con thieu N"
    -- va bam dong y voi chinh no. Tra cuu lai luc chay thi pham vi co the da
    -- khac (vd chi muc vua duoc dung lai), tuc chay mot thu khong ai duyet.
    kind         TEXT    NOT NULL,            -- 'crawl' | 'index'
    keyword      TEXT,                        -- tu khoa nguoi dung go, de hien lai
    scope_json   TEXT    NOT NULL,            -- {"domains": {...: [url, ...]}}

    status       TEXT    NOT NULL,            -- xem JobStatus trong job_store.py
    total        INTEGER NOT NULL DEFAULT 0,
    processed    INTEGER NOT NULL DEFAULT 0,
    -- URL dang xu ly, de man tien do noi duoc cau "dang lam gi" chu khong chi
    -- mot thanh %.
    current_url  TEXT,

    created_at   TEXT    NOT NULL,            -- ISO-8601 UTC
    started_at   TEXT,
    finished_at  TEXT,
    -- Nhip tim cua worker dang giu job. Job 'running' ma tim ngung qua lau la
    -- job cua mot worker da chet - xem `JobStore.reclaim_dead()`. Khong co cot
    -- nay thi mot worker chet giua chung khoa hang doi vinh vien.
    heartbeat_at TEXT,

    -- Ly do dung, cho ca truong hop dung dep lan dung xau. Nguoi dung phai doc
    -- duoc "can quota LLM" khac "bi chan" khac "nguoi dung huy".
    stop_reason  TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status, id);
