"""Chay lai trich xuat tren snapshot da luu: khong mang, khong LLM.

Day la kha nang chinh ma kho du lieu sinh ra de phuc vu - sua tang 1.6 xong,
do lai tren toan bo kho trong vai giay thay vi mot luot crawl 35 phut.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from crawler.record import CrawlStatus, ProductRecord  # noqa: E402
from crawler.store import CrawlStore, connect  # noqa: E402
from crawler.store.crawl_store import IMPORTED_VERSION  # noqa: E402
from reextract import reextract  # noqa: E402

PAGE = """
<html><body><h1>Đèn LED âm trần 12W</h1>
<div class="desc">
  <h2>4. Ưu điểm nổi bật</h2>
  <ul><li><strong>Tiết kiệm điện:</strong> chỉ 12W.</li>
      <li><strong>Tuổi thọ cao:</strong> 50.000 giờ.</li></ul>
</div></body></html>
"""

ANCHOR_PAGE = """
<html><body><h1>Phích cắm 4500W</h1>
<div class="desc">
  <h2>4. Điều làm nên khác biệt của phích cắm 4500W</h2>
  <ul><li><strong>Độ an toàn cao:</strong> chống giật.</li>
      <li><strong>Chịu tải lớn:</strong> lên tới 4500W.</li></ul>
</div></body></html>
"""


class _Fetch:
    def __init__(self, url, html):
        self.url, self.html = url, html
        self.ok, self.status, self.final_url, self.error = True, 200, url, None


@pytest.fixture
def store(tmp_path):
    conn = connect(tmp_path / "crawl.db")
    yield CrawlStore(conn)
    conn.close()


def _seed(store, url, html, **kwargs):
    snapshot_id = store.save_snapshot(url, _Fetch(url, html))
    record = ProductRecord(product_id="1", link_san_pham=url, **kwargs)
    store.save_extraction(record, snapshot_id=snapshot_id, extractor_version="v1")
    return snapshot_id


def test_no_network_call_happens(store, monkeypatch):
    """Chan tang fetch VA tang LLM: goi toi la test do."""
    import crawler.fetch.stealth_fetch as sf
    import crawler.llm.extractor as ex

    def _boom(*a, **k):
        raise AssertionError("reextract KHÔNG được chạm vào mạng")

    monkeypatch.setattr(sf.StealthFetcher, "fetch", _boom)
    monkeypatch.setattr(ex, "extract_tags_from_html", _boom)

    _seed(store, "https://x.vn/a", PAGE)
    done, skipped = reextract(store, "x.vn", "v2")

    assert (done, skipped) == (1, 0)


def test_a_new_row_is_written_without_touching_the_old_one(store):
    _seed(store, "https://x.vn/a", PAGE)
    reextract(store, "x.vn", "v2")

    rows = store._conn.execute(
        "SELECT extractor_version FROM extractions ORDER BY id"
    ).fetchall()
    assert [r[0] for r in rows] == ["v1", "v2"]
    # View tra ve ban moi nhat tren cung snapshot.
    assert store.current_records("x.vn")["https://x.vn/a"].tom_tat_uu_diem_tinh_nang


def test_the_compass_survives_a_rerun(store):
    """Vi sao phai luu `uu_diem_la_ban`: nhanh `anchor` chi tim thay muc nho mot
    dong do LLM chi ra. Khong luu lai thi moi lan chay lai deu mat nhanh do, va
    diff se bao hoi qui GIA o moi o von tim thay nho la ban."""
    url = "https://x.vn/phich-cam"
    _seed(
        store, url, ANCHOR_PAGE,
        uu_diem_la_ban="4. Điều làm nên khác biệt của phích cắm 4500W",
    )

    reextract(store, "x.vn", "v2")

    row = store._conn.execute(
        "SELECT * FROM products WHERE url = ?", (url,)
    ).fetchone()
    assert row["uu_diem_nguon"] == "anchor"
    assert "Độ an toàn cao" in row["tom_tat_uu_diem_tinh_nang"]


def test_without_the_stored_compass_that_page_would_be_lost(store):
    """Doi chung cho test tren: cung trang, khong la ban -> khong tim ra."""
    _seed(store, "https://x.vn/phich-cam", ANCHOR_PAGE)  # khong luu la ban
    reextract(store, "x.vn", "v2")

    row = store._conn.execute("SELECT * FROM products").fetchone()
    assert row["uu_diem_nguon"] == "none"


def test_tier_2_results_are_carried_over_not_recomputed(store):
    """`tags` la dau ra cua mot lan goi mang da tra tien - chay lai phai mang
    theo, khong duoc lam mat."""
    _seed(store, "https://x.vn/a", PAGE, tags={"cong_suat": "12W"})
    reextract(store, "x.vn", "v2")

    assert store.current_records("x.vn")["https://x.vn/a"].tags == {"cong_suat": "12W"}


def test_rows_imported_from_xlsx_are_skipped_and_counted(store):
    """Ban ghi nhap tu file cu khong co HTML -> bo qua co bao so luong, KHONG
    bao loi. Day la trang thai binh thuong cho toi luot crawl ke tiep."""
    store.save_extraction(
        ProductRecord(product_id="1", link_san_pham="https://x.vn/cu", ten_san_pham="Cũ"),
        snapshot_id=None, extractor_version=IMPORTED_VERSION,
    )
    _seed(store, "https://x.vn/moi", PAGE)

    done, skipped = reextract(store, "x.vn", "v2")

    assert (done, skipped) == (1, 1)
    # Ban ghi cu van con nguyen, khong bi dung toi.
    assert store.current_records("x.vn")["https://x.vn/cu"].ten_san_pham == "Cũ"


def test_only_the_latest_snapshot_of_a_url_is_rerun(store):
    """Site doi trang -> co 2 snapshot. Chay lai chi tren ban moi nhat: ban cu
    van giu duoc de doi chieu lich su, nhung khong sinh them ban ghi thua."""
    url = "https://x.vn/a"
    _seed(store, url, PAGE)
    _seed(store, url, ANCHOR_PAGE)

    done, _ = reextract(store, "x.vn", "v2")

    assert done == 1
    assert store._conn.execute(
        "SELECT COUNT(*) FROM extractions WHERE extractor_version = 'v2'"
    ).fetchone()[0] == 1


def test_a_page_that_lost_its_section_shows_up_as_a_regression(store):
    """Kich ban ma diff sinh ra de bat: HTML y nguyen, ket qua tut xuong."""
    _seed(store, "https://x.vn/a", "<html><body><h1>Đèn</h1></body></html>",
          tom_tat_uu_diem_tinh_nang="có từ lần trước", uu_diem_nguon="cluster")
    reextract(store, "x.vn", "v2")

    row = store._conn.execute("SELECT * FROM products").fetchone()
    assert row["tom_tat_uu_diem_tinh_nang"] is None
    assert row["crawl_status"] != CrawlStatus.OK.value


# --- Dem thay doi giua hai lan chay ----------------------------------------
#
# Phan tinh toan da chuyen tu script sang `crawler/store/diff.py` (task 7.1) de
# CLI va API dung chung mot duong. Cac test duoi day di theo no - chung chot
# HANH VI, khong chot noi ma nguon nam o dau.

def test_the_diff_counts_both_directions():
    """Chieu "lam hong" moi la chieu quan trong: mot chinh sua bao giat gau va
    vai, va truoc gio khong co cach nao biet. Da kiem tay tren 79 snapshot
    that (gieo 5 va / 3 hong -> dem ra dung 5 / 3); test nay khoa lai.
    """
    from crawler.store.diff import tally

    old = {
        1: {"gia": None, "uu_diem_nguon": "none"},        # -> va duoc
        2: {"gia": 100.0, "uu_diem_nguon": "keyword"},    # -> lam hong
        3: {"gia": 100.0, "uu_diem_nguon": "keyword"},    # -> doi khac
        4: {"gia": 100.0, "uu_diem_nguon": "keyword"},    # -> khong doi
    }
    new = {
        1: {"gia": 200.0, "uu_diem_nguon": "cluster"},
        2: {"gia": None, "uu_diem_nguon": "none"},
        3: {"gia": 150.0, "uu_diem_nguon": "anchor"},
        4: {"gia": 100.0, "uu_diem_nguon": "keyword"},
    }

    counts = tally(old, new, fields=("gia",))["gia"]
    assert (counts["va"], counts["hong"], counts["doi"]) == (1, 1, 1)


def test_the_diff_ignores_snapshots_only_one_side_has():
    """Chi so tren snapshot CHUNG: khac snapshot thi khac biet den tu SITE chu
    khong phai tu code, gop vao lam phep so mat nghia."""
    from crawler.store.diff import tally

    counts = tally({1: {"gia": None}, 2: {"gia": 1.0}}, {1: {"gia": 5.0}}, fields=("gia",))
    assert list(counts) == ["gia"] and counts["gia"]["va"] == 1


def test_no_change_reports_nothing():
    """Ca doi chung: cung code + cung snapshot -> khong duoc bao gi. Da xac
    nhan tren 48 snapshot that."""
    from crawler.store.diff import tally

    rows = {1: {"gia": 1.0}, 2: {"gia": None}}
    assert tally(rows, dict(rows), fields=("gia",)) == {}
