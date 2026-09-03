"""Ha tang kho du lieu: nen HTML va VIEW `products`."""
import sqlite3

import pytest

from crawler.store.db import compress_html, connect, decompress_html


@pytest.fixture
def db(tmp_path):
    conn = connect(tmp_path / "crawl.db")
    conn.execute("INSERT INTO sites (domain, base_url) VALUES ('x.vn', 'https://x.vn')")
    yield conn
    conn.close()


def test_wal_mode_is_on(db):
    """WAL khong phai toi uu ma la dieu kien de nhieu worker khong dam nhau."""
    assert db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_html_survives_a_compress_decompress_round_trip(fixture_html):
    html = fixture_html("tlc_product.html")
    blob, length = compress_html(html)
    assert length == len(html)
    assert decompress_html(blob) == html


@pytest.mark.parametrize(
    "name, floor",
    [
        # Nguong duoi lay tu do that (8,8x / 4,8x / 3,9x), ha xuong mot bac de
        # test khong gay khi noi dung fixture doi chut. Muc dich la bat ca
        # THAM HOA (nen hong, ti le ~1x) chu khong phai khoa chat con so.
        ("kingled_product_rendered.html", 6.0),
        ("tlc_product.html", 3.5),
        ("roman_product.html", 3.0),
    ],
)
def test_compression_ratio_matches_what_was_measured(fixture_html, name, floor):
    html = fixture_html(name)
    blob, _ = compress_html(html)
    assert len(html.encode("utf-8")) / len(blob) >= floor


def test_vietnamese_text_is_not_mangled():
    """UTF-8 nhieu byte: "Ưu điểm" phai ve nguyen ven, ke ca chu "đ" (U+0111)."""
    html = "<h2>4. Ưu điểm nổi bật</h2><li>Chống ẩm — tuổi thọ 50.000h ☑️</li>"
    assert decompress_html(compress_html(html)[0]) == html


def _snapshot(db, url, html="<html></html>"):
    blob, length = compress_html(html)
    cur = db.execute(
        "INSERT INTO page_snapshots (url, domain, fetched_at, http_status, "
        "final_url, html_gz, html_len) VALUES (?, 'x.vn', ?, 200, ?, ?, ?)",
        (url, "2026-09-03T00:00:00", url, blob, length),
    )
    return cur.lastrowid


def _extraction(db, url, snapshot_id, version, ten):
    cur = db.execute(
        "INSERT INTO extractions (url, domain, snapshot_id, extractor_version, "
        "extracted_at, ten_san_pham, crawl_status) "
        "VALUES (?, 'x.vn', ?, ?, '2026-09-03T00:00:00', ?, 'ok')",
        (url, snapshot_id, version, ten),
    )
    return cur.lastrowid


def _current(db, url):
    return db.execute("SELECT * FROM products WHERE url = ?", (url,)).fetchone()


def test_view_picks_latest_extraction_on_latest_snapshot(db):
    """Snapshot va extraction dan xen - view phai bam snapshot moi nhat truoc,
    roi moi toi lan trich xuat moi nhat TREN snapshot do."""
    url = "https://x.vn/den-a"
    snap1 = _snapshot(db, url)
    _extraction(db, url, snap1, "v1", "ten cu")
    snap2 = _snapshot(db, url)
    _extraction(db, url, snap2, "v1", "ten moi")
    # Chay lai v2 tren snapshot CU sau khi da co snapshot moi: khong duoc thang.
    _extraction(db, url, snap1, "v2", "ten cu chay lai")

    assert _current(db, url)["ten_san_pham"] == "ten moi"


def test_view_prefers_a_rerun_on_the_same_snapshot(db):
    """Cung snapshot, chay lai bo trich xuat -> ban moi thang."""
    url = "https://x.vn/den-b"
    snap = _snapshot(db, url)
    _extraction(db, url, snap, "v1", "ket qua cu")
    _extraction(db, url, snap, "v2", "ket qua moi")

    assert _current(db, url)["ten_san_pham"] == "ket qua moi"
    assert _current(db, url)["extractor_version"] == "v2"


def test_view_falls_back_to_an_imported_row_when_there_is_no_snapshot(db):
    url = "https://x.vn/den-c"
    _extraction(db, url, None, "imported-xlsx", "tu file cu")

    row = _current(db, url)
    assert row["ten_san_pham"] == "tu file cu"
    assert row["snapshot_id"] is None


def test_a_real_crawl_beats_an_imported_row_for_the_same_url(db):
    """Ban nhap tu .xlsx cu chi thang khi URL do CHUA TUNG co snapshot nao.

    Day la ly do view sap xep `snapshot_id IS NULL` xuong sau thay vi dua vao
    id: ban nhap co the duoc chen SAU (buoc migration chay sau lan crawl dau),
    nen "id lon hon" khong dong nghia voi "moi hon".
    """
    url = "https://x.vn/den-d"
    snap = _snapshot(db, url)
    _extraction(db, url, snap, "v1", "crawl that")
    _extraction(db, url, None, "imported-xlsx", "tu file cu")

    assert _current(db, url)["ten_san_pham"] == "crawl that"


def test_view_keeps_urls_separate(db):
    _extraction(db, "https://x.vn/a", _snapshot(db, "https://x.vn/a"), "v1", "A")
    _extraction(db, "https://x.vn/b", _snapshot(db, "https://x.vn/b"), "v1", "B")

    assert {r["ten_san_pham"] for r in db.execute("SELECT * FROM products")} == {"A", "B"}


def test_trailing_slash_makes_a_different_product(db):
    """URL luu NGUYEN VAN: "/a" va "/a/" la hai ban ghi khac nhau, dung nhu hai
    site khac quy uoc. Xem chu thich `url` trong schema.sql."""
    _extraction(db, "https://x.vn/a", None, "v1", "khong gach cheo")
    _extraction(db, "https://x.vn/a/", None, "v1", "co gach cheo")

    assert db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 2


def test_tags_go_away_with_their_extraction(db):
    """ON DELETE CASCADE that su co hieu luc - tuc PRAGMA foreign_keys song sot
    qua executescript() luc mo ket noi."""
    ext = _extraction(db, "https://x.vn/e", None, "v1", "E")
    db.execute("INSERT INTO product_tags VALUES (?, 'cong_suat', '12W')", (ext,))
    db.execute("DELETE FROM extractions WHERE id = ?", (ext,))

    assert db.execute("SELECT COUNT(*) FROM product_tags").fetchone()[0] == 0


def test_an_extraction_cannot_point_at_an_unknown_site(db):
    """Khoa ngoai that su duoc thi hanh - `PRAGMA foreign_keys` song sot qua
    `executescript()` luc mo ket noi (executescript tu commit va dong
    transaction, de sot rat de mat PRAGMA nay ma khong ai biet)."""
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO extractions (url, domain, extractor_version, "
            "extracted_at, crawl_status) "
            "VALUES ('https://khac.vn/a', 'khac.vn', 'v1', '2026-09-03', 'ok')"
        )
