"""Tien trinh worker: nhan job tu hang doi va chay crawl (capability
`crawl-job-runner`).

TAI SAO LA MOT TIEN TRINH RIENG, khong phai mot luong trong api:

    `StealthFetcher` dung `sync_playwright()`, thu khong song chung duoc voi
    vong lap bat dong bo cua tang API. Day la rang buoc ky thuat cung, khong
    phai lua chon kien truc (design.md muc 4, bay so 1).

WORKER LA NGUOI GHI DUY NHAT vao `crawl.db`. Nhan ban worker len 2 la dinh
`database is locked` bat ke `busy_timeout` - hang doi da chan san bang cau
`claim_next()` (mot job chay mot luc), nhung dung dua vao mot minh no.

Worker KHONG duoc bat che do nap lai ma nguon: mot luot crawl 33-70 phut se bi
giet ngang moi lan co ai luu file.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from ..config import STORE
from ..fetch import StealthFetcher
from ..llm import LLMProviderError, build_default_llm_provider
from ..pipeline import crawl_product_urls
from ..sites import get_profile
from ..store import CrawlStore, Job, JobStatus, JobStore, connect

logger = logging.getLogger("worker")

# Chu ky hoi hang doi. Mot job keo 33-70 phut nen 1 giay la nhieu khong dang
# ke, va do cung la do tre te nhat khi bat dau mot job.
POLL_SECONDS = 1.0


def _classify_failure(exc: BaseException) -> str:
    """Ly do dung, viet cho NGUOI DUNG doc.

    "Cạn quota LLM" khac "bị chặn" khac "lỗi kỹ thuật" - ba tinh huong nay doi
    ba hanh dong khac han nhau, nen gop chung thanh "job failed" la vut di dung
    phan thong tin co ich (task 5.7).
    """
    if isinstance(exc, LLMProviderError):
        return f"Tầng 2 (LLM) không chạy được: {exc}"
    return f"Lỗi kỹ thuật: {type(exc).__name__}: {exc}"


def run_job(job: Job, jobs: JobStore, store: CrawlStore) -> JobStatus:
    """Chay mot job den khi xong, huy, hoac hong. Tra ve trang thai cuoi."""
    urls_theo_domain = job.scope
    tong = job.total
    da_xu_ly = 0

    try:
        llm = build_default_llm_provider()
    except Exception as exc:  # noqa: BLE001 - ly do phai den duoc nguoi dung
        jobs.finish(job.id, JobStatus.FAILED, reason=_classify_failure(exc))
        return JobStatus.FAILED

    with StealthFetcher() as fetcher:
        for domain, urls in urls_theo_domain.items():
            if jobs.is_cancelling(job.id):
                break
            if not urls:
                continue

            # `fetch_options` theo ho so domain - dung thu ma duong CLI dung,
            # khong phai mot ban sao co the lech (vd `wait_selector` cua
            # KingLED, thieu no thi bang thong so doc ra rong).
            profile = get_profile(domain)
            da_xong_truoc_domain = da_xu_ly

            def bao_tien_do(so_da_lam: int, url: Optional[str], _base=da_xong_truoc_domain) -> None:
                jobs.report_progress(
                    job.id, processed=_base + so_da_lam, current_url=url
                )

            try:
                crawl_product_urls(
                    urls,
                    llm_provider=llm,
                    fetcher=fetcher,
                    store=store,
                    fetch_options=profile.fetch_options,
                    on_progress=bao_tien_do,
                    should_stop=lambda: jobs.is_cancelling(job.id),
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Job %d hỏng ở domain %s", job.id, domain)
                jobs.finish(job.id, JobStatus.FAILED, reason=_classify_failure(exc),
                            processed=da_xu_ly)
                return JobStatus.FAILED

            da_xu_ly += len(urls)

    if jobs.is_cancelling(job.id):
        # Ban ghi da luu TRUOC luc huy giu nguyen: chung da nam trong kho, va
        # huy mot job khong phai la hoan tac nhung gi da lam duoc.
        jobs.finish(job.id, JobStatus.CANCELLED, reason="Người dùng huỷ",
                    processed=jobs.get(job.id).processed)
        return JobStatus.CANCELLED

    jobs.finish(job.id, JobStatus.DONE, processed=tong)
    return JobStatus.DONE


def serve(*, poll_seconds: float = POLL_SECONDS, once: bool = False) -> None:
    """Vong doi worker: thu hoi job chet -> nhan job -> chay -> lap lai.

    `once=True` chay dung mot vong (dung cho test va cho viec chay tay mot job).
    """
    conn = connect(STORE.db_path)
    jobs, store = JobStore(conn), CrawlStore(conn)
    logger.info("Worker sẵn sàng, kho dữ liệu %s", STORE.db_path)

    try:
        while True:
            # Truoc khi nhan viec moi: tra ve hang doi cac job cua worker da
            # chet. Khong co buoc nay thi mot lan bi kill giua chung khoa hang
            # doi vinh vien (xep hang: mot job chay mot luc).
            for job_id in jobs.reclaim_dead():
                logger.warning("Job %d bị bỏ dở — đã đưa lại vào hàng đợi", job_id)

            job = jobs.claim_next()
            if job is None:
                if once:
                    return
                time.sleep(poll_seconds)
                continue

            logger.info("Nhận job %d (%s, %d URL)", job.id, job.kind, job.total)
            ket_qua = run_job(job, jobs, store)
            logger.info("Job %d kết thúc: %s", job.id, ket_qua.value)
            if once:
                return
    finally:
        conn.close()


__all__ = ["POLL_SECONDS", "run_job", "serve"]
