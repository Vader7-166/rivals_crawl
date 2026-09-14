"""Tang API (capability `crawl-web-runtime`).

Tinh chat quan trong nhat o day khong phai hinh dang JSON ma la RANH GIOI GHI:
`crawl.db` chi chiu duoc mot nguoi ghi va nguoi do la worker. Api dat viec vao
hang doi roi buong ra - no khong bao gio tu crawl hay tu sua mot ban ghi san
pham nao (task 4.5).
"""
import importlib

import pytest
from fastapi.testclient import TestClient

from crawler.record import ProductRecord
from crawler.probing.category_crawl import CategoryCrawlResult
from crawler.store import CategoryStore, CrawlStore, JobStatus, connect

KINGLED = "kingled.com.vn"


class _Fetch:
    def __init__(self, url, html):
        self.url, self.html = url, html
        self.ok, self.status, self.final_url, self.error = True, 200, url, None


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Api tro vao mot kho du lieu rieng cua tung test.

    `STORE.db_path` duoc doc luc mo ket noi nen phai vá TRUOC khi api dung
    `_State` - do la ly do module duoc nap lai o day.
    """
    db = tmp_path / "crawl.db"
    monkeypatch.setattr("crawler.config.STORE", type(
        importlib.import_module("crawler.config").STORE
    )(db_path=db))

    conn = connect(db)
    store = CrawlStore(conn)
    url = f"https://{KINGLED}/den-a"
    snapshot_id = store.save_snapshot(url, _Fetch(url, "<html><h1>Đèn A</h1></html>"))
    record = ProductRecord(
        product_id="1", link_san_pham=url, ten_san_pham="Đèn LED âm trần 9W",
        ma_san_pham="DL-9", category_1="ĐÈN DOWNLIGHT ÂM TRẦN", gia=199000.0,
        link_anh_san_pham="https://kingled.com.vn/a.jpg",
        tom_tat_uu_diem_tinh_nang="Tiết kiệm điện", uu_diem_nguon="keyword",
        # Thieu `tags` thi ban ghi xuong PARTIAL_MISSING_FIELDS va van la ung
        # vien crawl lai - tuc fixture nay se khong con la "da crawl du".
        tags={"cong_suat": "9W"},
    )
    record.recompute_status()
    store.save_extraction(record, snapshot_id=snapshot_id, extractor_version="v7")

    # Chi muc danh muc: mot URL da crawl xong + mot URL CHUA crawl. Thieu ve
    # thu hai thi moi pham vi deu "đã crawl đủ" va khong job nao tao duoc - tuc
    # fixture se chot nham mot he thong khong bao gio chay viec gi.
    CategoryStore(conn).save_category(KINGLED, CategoryCrawlResult(
        category_url=f"https://{KINGLED}/am-tran-downlight",
        category_name="ĐÈN DOWNLIGHT ÂM TRẦN",
        product_urls=[url, f"https://{KINGLED}/den-b"],
        pages_fetched=1, ok=True,
    ))
    conn.commit()
    conn.close()

    import crawler.web.api as api
    importlib.reload(api)
    api.state = None
    with TestClient(api.app) as c:
        yield c, db
    if api.state is not None:
        api.state.close()
        api.state = None


def _so_ban_ghi(db):
    conn = connect(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM extractions").fetchone()[0]
    finally:
        conn.close()


def test_suggest_groups_results_by_kind(client):
    c, _ = client

    body = c.get("/api/suggest", params={"q": "led"}).json()

    assert [s["label"] for s in body["brands"]]
    assert all("kind" in s and "query" in s for s in body["brands"])


def test_scope_reports_have_and_missing_per_domain(client):
    c, _ = client

    body = c.get("/api/scope", params={"q": "kingled"}).json()

    assert body["kind"] == "brand"
    assert body["domains"][0]["domain"] == KINGLED
    assert body["domains"][0]["have"] == 1


def test_a_domain_without_an_index_says_so_instead_of_zero(client):
    """Task 3.7 qua duong HTTP: "chưa dựng chỉ mục" khac han "không có sản
    phẩm nào". Doi chung o day la TLC - no khong co ban ghi lan chi muc nao."""
    c, _ = client

    body = c.get("/api/scope", params={"q": "tlc"}).json()

    assert body["domains"][0]["needs_index"] is True
    assert c.get("/api/scope", params={"q": "kingled"}).json()[
        "domains"][0]["needs_index"] is False


def test_products_can_be_filtered_by_status(client):
    c, _ = client

    tat_ca = c.get(f"/api/domains/{KINGLED}/products").json()
    loc = c.get(f"/api/domains/{KINGLED}/products", params={"status": "error"}).json()

    assert tat_ca["matched"] == 1
    assert loc["matched"] == 0


def test_read_endpoints_never_write_to_the_store(client):
    """4.5: khang dinh bang so ban ghi, khong bang y dinh."""
    c, db = client
    truoc = _so_ban_ghi(db)

    c.get("/api/suggest", params={"q": "den"})
    c.get("/api/scope", params={"q": "kingled"})
    c.get("/api/domains")
    c.get(f"/api/domains/{KINGLED}/products")

    assert _so_ban_ghi(db) == truoc


def test_creating_a_job_returns_an_id_immediately(client):
    """Khong duoc cho crawl xong (33-70 phut) de tra loi mot request HTTP."""
    c, _ = client

    body = c.post("/api/jobs", json={"keyword": "kingled"}).json()

    assert body["id"] and body["status"] == "queued"
    assert body["total"] >= 1


def test_a_fully_crawled_scope_is_refused_instead_of_running_empty(client):
    """5.10 o muc API: pham vi da du thi khong tao job nao - crawl lai la 0
    request mang, nhung tao mot job rong van bat nguoi dung ngoi nhin mot thanh
    tien do khong bao gio co gi."""
    c, _ = client
    # Pham vi chi gom dung URL da OK -> khong con gi de crawl.
    body = c.post("/api/jobs", json={"keyword": "đèn led âm trần 9w"})

    assert body.status_code == 409
    assert "đã crawl đủ" in body.json()["detail"]


def test_cancelling_a_queued_job_is_immediate(client):
    c, _ = client
    job = c.post("/api/jobs", json={"keyword": "kingled"}).json()

    huy = c.post(f"/api/jobs/{job['id']}/cancel").json()

    assert huy["status"] == JobStatus.CANCELLED.value
    assert huy["stop_reason"] == "Người dùng huỷ"


def test_the_event_stream_reports_the_final_state_and_closes(client):
    """Dong su kien phai DONG khi job ve trang thai cuoi - de mo thi trinh
    duyet cu noi lai mai mot job da xong."""
    c, _ = client
    job = c.post("/api/jobs", json={"keyword": "kingled"}).json()
    c.post(f"/api/jobs/{job['id']}/cancel")

    with c.stream("GET", f"/api/jobs/{job['id']}/events") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        goi = [line for line in r.iter_lines() if line.startswith("data:")]

    assert any("cancelled" in g for g in goi)


def test_an_unknown_job_is_a_404_not_an_empty_stream(client):
    c, _ = client

    assert c.get("/api/jobs/9999").status_code == 404
