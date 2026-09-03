"""Pipeline ghi vao kho du lieu: snapshot truoc, extraction sau, va an toan khi
nhieu worker chay song song.

Khong dung mang: fetcher gia tra ve HTML co san. Tang 2 (LLM) duoc thay bang
provider gia luon loi - du de di het duong ghi ma khong goi API nao.
"""
from dataclasses import dataclass
from typing import Optional

import pytest

from crawler.llm.provider import LLMProviderError
from crawler.pipeline import crawl_product_urls
from crawler.record import CrawlStatus
from crawler.store import CrawlStore, connect

PAGE = """
<html><body><div class="summary"><h1>Đèn LED âm trần 12W</h1></div>
<div class="desc">
  <h2>4. Ưu điểm nổi bật</h2>
  <ul><li><strong>Tiết kiệm điện:</strong> tiêu thụ 12W.</li>
      <li><strong>Tuổi thọ cao:</strong> 50.000 giờ.</li></ul>
</div></body></html>
"""


@dataclass
class _Fetch:
    url: str
    ok: bool = True
    html: str = PAGE
    status: int = 200
    error: Optional[str] = None

    @property
    def final_url(self):
        return self.url


@dataclass
class _FailedFetch:
    ok: bool = False
    html: Optional[str] = None
    status: int = 503
    final_url: Optional[str] = None
    error: str = "ERR_CONNECTION_REFUSED"


class _FakeFetcher:
    def __init__(self, fail_urls=()):
        self.fail_urls = set(fail_urls)

    def fetch(self, url, **kwargs):
        return _FailedFetch() if url in self.fail_urls else _Fetch(url=url)


class _DeadProvider:
    """Tang 2 luon loi - pipeline nuot loi va de tags rong. Duong ghi kho du
    lieu phai chay het du tang 2 hong."""

    def generate_json(self, prompt, schema):
        raise LLMProviderError("khong goi mang trong test")


class _CountingFetcher(_FakeFetcher):
    """Ghi lai URL nao that su bi fetch - de kiem tra ban ghi da xong khong bi
    crawl lai."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fetched: list[str] = []

    def fetch(self, url, **kwargs):
        self.fetched.append(url)
        return super().fetch(url, **kwargs)


URLS = [f"https://x.vn/den-{i}" for i in range(6)]


@pytest.fixture
def store(tmp_path):
    conn = connect(tmp_path / "crawl.db")
    yield CrawlStore(conn)
    conn.close()


def _count(store, table):
    return store._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


@pytest.mark.parametrize("workers", [1, 4])
def test_every_page_gets_a_snapshot_and_an_extraction(store, workers):
    crawl_product_urls(
        URLS, llm_provider=_DeadProvider(), fetcher=_FakeFetcher(),
        workers=workers, store=store,
    )

    assert _count(store, "page_snapshots") == len(URLS)
    assert _count(store, "extractions") == len(URLS)


@pytest.mark.parametrize("workers", [1, 4])
def test_a_successful_page_is_stored_even_though_tier_2_failed(store, workers):
    """Luu MOI trang, khong chi trang hong - o sai ma tuong dung khong tu khai
    bao, nen "chi luu khi hong" bo mat dung ca can soi nhat."""
    crawl_product_urls(
        URLS[:1], llm_provider=_DeadProvider(), fetcher=_FakeFetcher(),
        workers=workers, store=store,
    )

    row = store._conn.execute("SELECT * FROM products").fetchone()
    assert row["crawl_status"] != CrawlStatus.OK.value  # tang 2 hong that
    assert store.snapshot_html(row["snapshot_id"]) == PAGE


@pytest.mark.parametrize("workers", [1, 4])
def test_a_failed_fetch_records_the_error_without_an_empty_snapshot(store, workers):
    crawl_product_urls(
        URLS[:2], llm_provider=_DeadProvider(),
        fetcher=_FakeFetcher(fail_urls={URLS[0]}), workers=workers, store=store,
    )

    assert _count(store, "page_snapshots") == 1  # chi trang fetch duoc
    failed = store._conn.execute(
        "SELECT * FROM products WHERE url = ?", (URLS[0],)
    ).fetchone()
    assert failed["snapshot_id"] is None
    assert failed["crawl_status"] == CrawlStatus.ERROR.value
    assert "ERR_CONNECTION_REFUSED" in failed["crawl_error"]


def test_many_workers_finishing_at_once_lose_nothing(store):
    """4 worker, 40 URL: khong mat ban ghi va khong `database is locked`.

    Ghi chi xay ra tren main thread (fetch + harvest); test nay la cai chot giu
    cho dieu do dung ve sau - neu ai do chuyen loi goi save_extraction vao
    trong worker thi day la cho bao.
    """
    urls = [f"https://x.vn/den-{i}" for i in range(40)]
    records = crawl_product_urls(
        urls, llm_provider=_DeadProvider(), fetcher=_FakeFetcher(),
        workers=4, store=store,
    )

    assert len(records) == len(urls)
    assert _count(store, "extractions") == len(urls)
    assert {r["url"] for r in store._conn.execute("SELECT url FROM products")} == set(urls)


def test_tags_are_stored_one_row_per_attribute(store):
    """Ghi thang mot ban ghi co tags de khoi phai gia lap ca tang 2."""
    from crawler.record import ProductRecord

    record = ProductRecord(
        product_id="1", link_san_pham="https://x.vn/a", ten_san_pham="Đèn",
        tags={"cong_suat": "12W", "nhiet_do_mau": "3000K, 4000K, 6500K"},
    )
    store.save_extraction(record, snapshot_id=None, extractor_version="v1")

    rows = dict(store._conn.execute("SELECT key, value FROM product_tags").fetchall())
    assert rows == {"cong_suat": "12W", "nhiet_do_mau": "3000K, 4000K, 6500K"}
    assert store.current_records("x.vn")["https://x.vn/a"].tags == rows


def test_stopping_halfway_keeps_what_was_already_written(store):
    """Gian doan giua chung: ban ghi da ghi con nguyen, lan sau chi crawl phan
    thieu. Mo phong bang mot fetcher no o URL thu 3."""
    class _Exploding(_FakeFetcher):
        def fetch(self, url, **kwargs):
            if url == URLS[3]:
                raise KeyboardInterrupt("nguoi dung bam Ctrl-C")
            return super().fetch(url, **kwargs)

    with pytest.raises(KeyboardInterrupt):
        crawl_product_urls(
            URLS, llm_provider=_DeadProvider(), fetcher=_Exploding(),
            workers=1, store=store,
        )

    done = set(store.current_records("x.vn"))
    assert done == set(URLS[:3])
    assert store.urls_needing_crawl(URLS) == URLS  # tang 2 hong -> chua ai OK


def test_urls_needing_crawl_skips_the_ones_already_complete(store):
    from crawler.record import ProductRecord

    complete = ProductRecord(
        product_id="1", link_san_pham=URLS[0], ten_san_pham="Đèn",
        ma_san_pham="A1", category_1="Âm trần", link_anh_san_pham="https://x.vn/a.jpg",
        gia=100.0, tags={"cong_suat": "12W"},
    ).recompute_status()
    assert complete.crawl_status == CrawlStatus.OK
    store.save_extraction(complete, snapshot_id=None, extractor_version="v1")

    assert store.urls_needing_crawl(URLS) == URLS[1:]


def test_the_store_does_not_need_an_xlsx_file_to_know_what_is_done(store, tmp_path):
    """Khac biet chinh so voi co che cu: khong con phu thuoc file .xlsx nao."""
    crawl_product_urls(
        URLS[:2], llm_provider=_DeadProvider(), fetcher=_FakeFetcher(),
        workers=1, store=store,
    )
    assert not list(tmp_path.glob("*.xlsx"))
    assert set(store.current_records("x.vn")) == set(URLS[:2])


# --- Kho du lieu la nguon trang thai ---------------------------------------

def test_a_completed_product_is_not_crawled_again(store):
    """Crawl-lai-co-chon-loc lay trang thai tu KHO, khong doc nguoc .xlsx."""
    from crawler.record import ProductRecord

    xong = ProductRecord(
        product_id="1", link_san_pham=URLS[0], ten_san_pham="Đèn",
        ma_san_pham="A1", category_1="Âm trần", link_anh_san_pham="https://x.vn/a.jpg",
        gia=100.0, tags={"cong_suat": "12W"},
    ).recompute_status()
    store.save_extraction(xong, snapshot_id=None, extractor_version="v1")

    fetcher = _CountingFetcher()
    crawl_product_urls(
        URLS[:3], llm_provider=_DeadProvider(), fetcher=fetcher,
        workers=1, store=store,
    )

    assert fetcher.fetched == URLS[1:3]  # URL da xong khong bi fetch lai


def test_deleting_the_xlsx_does_not_make_it_crawl_everything_again(store, tmp_path):
    """Cai bay cu bien mat: truoc day trang thai nam trong file .xlsx nen xoa
    file la mat sach tien do (va nguoc lai - GIU file lai lam ban ghi cu bi tai
    su dung nguyen ven du da sua bo trich xuat, xem docs/todo.md).
    """
    from crawler.record import ProductRecord, write_records_to_excel

    xong = ProductRecord(
        product_id="1", link_san_pham=URLS[0], ten_san_pham="Đèn",
        ma_san_pham="A1", category_1="Âm trần", link_anh_san_pham="https://x.vn/a.jpg",
        gia=100.0, tags={"cong_suat": "12W"},
    ).recompute_status()
    store.save_extraction(xong, snapshot_id=None, extractor_version="v1")

    path = tmp_path / "out.xlsx"
    write_records_to_excel([xong], path)
    path.unlink()
    assert not path.exists()

    fetcher = _CountingFetcher()
    crawl_product_urls(
        URLS[:2], llm_provider=_DeadProvider(), fetcher=fetcher,
        workers=1, store=store, checkpoint_path=path,
    )

    assert fetcher.fetched == [URLS[1]]


def test_urls_from_two_domains_both_get_their_state(store):
    """Mot lan chay thuong chi nham 1 site, nhung gia dinh do khong duoc im
    lang: lech domain thi cac URL con lai se bi crawl lai het."""
    from crawler.record import ProductRecord

    for url in ("https://x.vn/a", "https://y.vn/b"):
        store.ensure_site(url)
        store.save_extraction(
            ProductRecord(
                product_id="1", link_san_pham=url, ten_san_pham="Đèn",
                ma_san_pham="A1", category_1="C", link_anh_san_pham="https://i/a.jpg",
                gia=1.0, tags={"k": "v"},
            ).recompute_status(),
            snapshot_id=None, extractor_version="v1",
        )

    fetcher = _CountingFetcher()
    crawl_product_urls(
        ["https://x.vn/a", "https://y.vn/b", "https://y.vn/moi"],
        llm_provider=_DeadProvider(), fetcher=fetcher, workers=1, store=store,
    )

    assert fetcher.fetched == ["https://y.vn/moi"]


def test_no_mid_crawl_xlsx_is_written_when_the_store_is_in_use(store, tmp_path):
    """Kho du lieu commit tung ban ghi -> diem khoi phuc day hon han moi 40 ban.
    Ghi Excel lui han ve buoc ket xuat, khong con la co che chong mat tien do."""
    path = tmp_path / "checkpoint.xlsx"
    crawl_product_urls(
        URLS, llm_provider=_DeadProvider(), fetcher=_FakeFetcher(),
        workers=1, store=store, checkpoint_path=path, checkpoint_every=2,
    )

    assert not path.exists()
    assert _count(store, "extractions") == len(URLS)  # tien do nam trong kho
