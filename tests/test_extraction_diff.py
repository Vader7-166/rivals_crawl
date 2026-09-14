"""So hai phien ban trich xuat (capability `extraction-diff-view`).

Phep so CHI hop le tren snapshot chung: khac snapshot thi khac biet den tu
SITE chu khong phai tu code minh vua sua - do la ly do kho du lieu tach
`page_snapshots` khoi `extractions` ngay tu dau.
"""
import pytest

from crawler.record import ProductRecord
from crawler.store import CrawlStore, connect
from crawler.store.diff import DOI, HONG, VA, changes, diff, versions

DOMAIN = "kingled.com.vn"


class _Fetch:
    def __init__(self, url, html="<html></html>"):
        self.url, self.html = url, html
        self.ok, self.status, self.final_url, self.error = True, 200, url, None


@pytest.fixture
def store(tmp_path):
    conn = connect(tmp_path / "crawl.db")
    yield CrawlStore(conn), conn
    conn.close()


def _luu(store, conn, url, version, *, snapshot_id=None, **fields):
    if snapshot_id is None:
        snapshot_id = store.save_snapshot(url, _Fetch(url))
    record = ProductRecord(product_id="1", link_san_pham=url, **fields)
    store.save_extraction(record, snapshot_id=snapshot_id, extractor_version=version)
    return snapshot_id


def test_the_three_groups_mean_three_different_things(store):
    """"vá được" / "làm hỏng" / "đổi khác" tach rieng vi chinh su tach do tra
    loi duoc "sửa vừa rồi lãi hay hại"."""
    s, conn = store
    a = _luu(s, conn, f"https://{DOMAIN}/a", "v1", tom_tat_uu_diem_tinh_nang=None)
    _luu(s, conn, f"https://{DOMAIN}/a", "v2", snapshot_id=a,
         tom_tat_uu_diem_tinh_nang="Tiết kiệm điện")
    b = _luu(s, conn, f"https://{DOMAIN}/b", "v1", tom_tat_uu_diem_tinh_nang="Có sẵn")
    _luu(s, conn, f"https://{DOMAIN}/b", "v2", snapshot_id=b,
         tom_tat_uu_diem_tinh_nang=None)
    c = _luu(s, conn, f"https://{DOMAIN}/c", "v1", tom_tat_uu_diem_tinh_nang="Cũ")
    _luu(s, conn, f"https://{DOMAIN}/c", "v2", snapshot_id=c,
         tom_tat_uu_diem_tinh_nang="Mới")

    ket_qua = diff(conn, DOMAIN, "v1", "v2")

    dem = ket_qua.counts["tom_tat_uu_diem_tinh_nang"]
    assert (dem[VA], dem[HONG], dem[DOI]) == (1, 1, 1)
    assert ket_qua.shared_snapshots == 3


def test_versions_are_listed_with_their_snapshot_counts(store):
    s, conn = store
    a = _luu(s, conn, f"https://{DOMAIN}/a", "v1", ten_san_pham="A")
    _luu(s, conn, f"https://{DOMAIN}/a", "v2", snapshot_id=a, ten_san_pham="A")
    _luu(s, conn, f"https://{DOMAIN}/b", "v1", ten_san_pham="B")

    assert [(v.version, v.snapshots) for v in versions(conn, DOMAIN)] == [("v1", 2), ("v2", 1)]


def test_no_shared_snapshot_explains_how_to_make_a_valid_comparison(store):
    """7.4: bang rong doc thanh "không có gì đổi", trong khi su that la "phép so
    này không hợp lệ". Hai cau do dan toi hai hanh dong khac han nhau."""
    s, conn = store
    _luu(s, conn, f"https://{DOMAIN}/a", "v1", ten_san_pham="A")
    _luu(s, conn, f"https://{DOMAIN}/b", "v2", ten_san_pham="B")

    ket_qua = diff(conn, DOMAIN, "v1", "v2")

    assert ket_qua.shared_snapshots == 0
    assert ket_qua.counts == {}
    assert "reextract.py" in ket_qua.message


def test_records_without_a_snapshot_are_counted_not_swallowed(store):
    """7.5: ban ghi nhap tu .xlsx cu khong co HTML nen khong so duoc. Nguoi doc
    phai biet phep so bo qua bao nhieu."""
    s, conn = store
    a = _luu(s, conn, f"https://{DOMAIN}/a", "v1", ten_san_pham="A")
    _luu(s, conn, f"https://{DOMAIN}/a", "v2", snapshot_id=a, ten_san_pham="A2")
    # Ban nhap tu file cu: khong co snapshot.
    cu = ProductRecord(product_id="9", link_san_pham=f"https://{DOMAIN}/cu",
                       ten_san_pham="Cũ")
    s.save_extraction(cu, snapshot_id=None, extractor_version="imported-xlsx")

    assert diff(conn, DOMAIN, "v1", "v2").skipped_without_snapshot == 1


def test_every_changed_product_is_listable_not_just_a_sample(store):
    """7.6: "vá được 47 ô" ma chi xem duoc 3 thi 44 o kia van phai mo SQLite tra
    tay - dung cai ma man so sanh sinh ra de khoi phai lam."""
    s, conn = store
    for i in range(12):
        url = f"https://{DOMAIN}/sp-{i}"
        sid = _luu(s, conn, url, "v1", tom_tat_uu_diem_tinh_nang=None)
        _luu(s, conn, url, "v2", snapshot_id=sid, tom_tat_uu_diem_tinh_nang="Có")

    tat_ca = changes(conn, DOMAIN, "v1", "v2", field_name="tom_tat_uu_diem_tinh_nang")

    assert len(tat_ca) == 12
    assert all(o.group == VA for o in tat_ca)


def test_a_cell_carries_both_values_and_the_product_url(store):
    """7.7: mot o phai xem duoc truoc/sau KEM URL san pham goc - khong co URL
    thi khong kiem chung duoc ben nao dung."""
    s, conn = store
    url = f"https://{DOMAIN}/a"
    sid = _luu(s, conn, url, "v1", gia=199000.0)
    _luu(s, conn, url, "v2", snapshot_id=sid, gia=149000.0)

    o = changes(conn, DOMAIN, "v1", "v2", field_name="gia", group=DOI)

    assert len(o) == 1
    assert (o[0].url, o[0].before, o[0].after) == (url, 199000.0, 149000.0)


def test_rerunning_the_same_version_compares_the_latest_run(store):
    """Chay lai cung mot nhan (sua xong chay lai `v7`) thi ban SAU moi la ban
    dang dung."""
    s, conn = store
    url = f"https://{DOMAIN}/a"
    sid = _luu(s, conn, url, "v1", ten_san_pham="A")
    _luu(s, conn, url, "v2", snapshot_id=sid, ten_san_pham="sai")
    _luu(s, conn, url, "v2", snapshot_id=sid, ten_san_pham="đúng")

    o = changes(conn, DOMAIN, "v1", "v2", field_name="ten_san_pham")

    assert o[0].after == "đúng"
