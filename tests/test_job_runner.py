"""Vong chay job: huy giua chung, chay lai la CHAY TIEP, va pham vi da du thi
khong cham mang (capability `crawl-job-runner`, tasks 5.9/5.10).

Khong dung mang va khong goi LLM: fetcher gia dem so lan fetch, provider gia
dem so lan goi. Chinh hai con so do la thu duoc kiem chung.
"""
from dataclasses import dataclass
from typing import Optional

import pytest

from crawler.llm.provider import LLMProvider
from crawler.pipeline import crawl_product_urls
from crawler.record import ProductRecord
from crawler.store import CrawlStore, JobStatus, JobStore, connect

DOMAIN = "kingled.com.vn"
URLS = [f"https://{DOMAIN}/sp-{i}" for i in range(6)]

# Trang gia nhung DAY DU theo dung nghia cua `REQUIRED_FIELDS`: thieu breadcrumb
# hay thieu gia thi ban ghi xuong PARTIAL_MISSING_FIELDS va van la ung vien
# crawl lai - luc do phep dem "0 request mang" o duoi khong con do dung thu no
# dinh do.
TRANG = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
 {"@type":"ListItem","position":1,"name":"Trang chủ","item":"https://kingled.com.vn/"},
 {"@type":"ListItem","position":2,"name":"ĐÈN DOWNLIGHT ÂM TRẦN","item":"https://kingled.com.vn/dl"},
 {"@type":"ListItem","position":3,"name":"Đèn LED âm trần 9W","item":"https://kingled.com.vn/sp-0"}]}
</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Đèn LED âm trần 9W",
 "sku":"DL-9SS","image":"https://kingled.com.vn/a.jpg",
 "offers":{"@type":"Offer","price":"199000","priceCurrency":"VND"}}
</script>
</head><body>
<h1>Đèn LED âm trần 9W</h1>
<div class="desc"><h2>Ưu điểm nổi bật</h2><ul><li>Tiết kiệm điện</li></ul></div>
</body></html>
"""


@dataclass
class _Fetch:
    url: str
    html: str = TRANG
    ok: bool = True
    status: int = 200
    final_url: Optional[str] = None
    error: Optional[str] = None


class _FetcherDem:
    def __init__(self):
        self.calls: list[str] = []

    def fetch(self, url, **kwargs):
        self.calls.append(url)
        return _Fetch(url=url, final_url=url)


class _LLMDem(LLMProvider):
    """Provider gia: dem so lan goi, tra ve JSON toi thieu de ban ghi thanh OK.

    Cai duoc kiem chung trong ca file nay la CON SO NAY: mot pham vi da crawl
    du phai khong lam no nhuc nhich (task 5.10).
    """

    name = "dem"

    def __init__(self):
        self.calls = 0

    def generate_json(self, prompt, json_schema=None):
        self.calls += 1
        return '{"tags": {"cong_suat": "9W"}}'


@pytest.fixture
def kho(tmp_path):
    conn = connect(tmp_path / "crawl.db")
    yield CrawlStore(conn), JobStore(conn)
    conn.close()


def _crawl(kho_store, urls, **kwargs):
    fetcher, llm = _FetcherDem(), _LLMDem()
    crawl_product_urls(
        urls, llm_provider=llm, fetcher=fetcher, store=kho_store, workers=1, **kwargs
    )
    return fetcher, llm


def test_cancelling_midway_keeps_what_was_already_saved(kho):
    """Ban ghi da luu truoc luc huy GIU NGUYEN: chung da nam trong kho, va huy
    mot job khong phai la hoan tac nhung gi da lam duoc."""
    store, _ = kho
    da_lam: list[str] = []

    def dung_sau_hai_trang() -> bool:
        return len(da_lam) >= 2

    def ghi_nhan(so_da_lam, url):
        if url:
            da_lam.append(url)

    fetcher, _ = _crawl(store, URLS, on_progress=ghi_nhan, should_stop=dung_sau_hai_trang)

    assert len(fetcher.calls) < len(URLS)          # da dung giua chung
    assert len(store.current_records(DOMAIN)) >= 2  # phan lam duoc van con


def test_rerunning_after_a_cancel_only_crawls_what_is_left(kho):
    """5.9: chay lai dung pham vi do sau khi huy thi so can crawl bang so CON
    THIEU, khong phai toan bo pham vi."""
    store, _ = kho
    da_lam: list[str] = []
    _crawl(store, URLS,
           on_progress=lambda n, u: da_lam.append(u) if u else None,
           should_stop=lambda: len(da_lam) >= 2)
    xong_dot_mot = len(store.current_records(DOMAIN))
    assert 0 < xong_dot_mot < len(URLS)

    fetcher, _ = _crawl(store, URLS)

    assert len(fetcher.calls) == len(URLS) - xong_dot_mot
    assert len(store.current_records(DOMAIN)) == len(URLS)


def test_a_fully_crawled_scope_touches_neither_network_nor_llm(kho):
    """5.10: chay lai pham vi da du thi 0 request mang, 0 goi LLM. Day la tinh
    chat khien viec "bam chay lai" an toan ve chi phi."""
    store, _ = kho
    _crawl(store, URLS)
    assert len(store.current_records(DOMAIN)) == len(URLS)

    fetcher, llm = _crawl(store, URLS)

    assert fetcher.calls == []
    assert llm.calls == 0


def test_progress_counts_the_whole_scope_not_just_the_new_part(kho):
    """Nguoi dung bam "crawl 6 sản phẩm" thi ho doi thanh tien do chay tu 0 den
    6, du phan lon duoc tai su dung trong mot giay."""
    store, _ = kho
    _crawl(store, URLS[:4])
    moc: list[int] = []

    _crawl(store, URLS, on_progress=lambda n, u: moc.append(n))

    assert moc and moc[-1] == len(URLS)
    assert moc[0] > 1  # da tinh ca 4 ban tai su dung


def test_a_cancelled_job_ends_as_cancelled_with_a_reason(kho):
    """Trang thai cuoi phai NOI DUOC vi sao job dung - nguoi dung doc "Người
    dùng huỷ" khac han doc "Cạn quota LLM"."""
    _, jobs = kho
    job = jobs.enqueue("crawl", {DOMAIN: URLS})
    jobs.claim_next()
    jobs.report_progress(job.id, processed=2, current_url=URLS[2])

    jobs.request_cancel(job.id)
    jobs.finish(job.id, JobStatus.CANCELLED, reason="Người dùng huỷ", processed=2)

    xong = jobs.get(job.id)
    assert (xong.status, xong.processed) == (JobStatus.CANCELLED, 2)
    assert xong.stop_reason == "Người dùng huỷ"
