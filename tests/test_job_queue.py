"""Hang doi job trong chinh crawl.db (capability `crawl-job-runner`).

Quyet dinh "hang doi nam trong SQLite, khong dung broker rieng" o design.md
Open Question 4. Cac test duoi day chot dung nhung tinh chat ma mot broker
thuong lo ho: nhan job doc quyen, xep hang, huy an toan, va thu hoi job cua
worker da chet.
"""
from datetime import datetime, timedelta, timezone

import pytest

from crawler.store import JobStatus, JobStore, connect

SCOPE = {"kingled.com.vn": ["https://kingled.com.vn/a", "https://kingled.com.vn/b"]}


@pytest.fixture
def jobs(tmp_path):
    conn = connect(tmp_path / "t.db")
    yield JobStore(conn)
    conn.close()


def test_enqueue_returns_an_id_immediately(jobs):
    """Ben goi khong duoc cho crawl xong (33-70 phut) de tra loi mot request."""
    job = jobs.enqueue("crawl", SCOPE, keyword="kingled")

    assert job.id and job.status is JobStatus.QUEUED
    assert job.total == 2
    assert job.urls == SCOPE["kingled.com.vn"]


def test_scope_is_frozen_at_creation_time(jobs):
    """Pham vi chot luc TAO chu khong tra cuu lai luc chay: nguoi dung da nhin
    con so "còn thiếu N" va bam dong y voi chinh no."""
    job = jobs.enqueue("crawl", SCOPE)

    assert jobs.get(job.id).scope == SCOPE


def test_only_one_claimer_wins(jobs):
    """Diem quyet dinh tinh dung cua ca hang doi: hai worker cung hoi mot luc
    thi dung MOT ben nhan duoc job."""
    jobs.enqueue("crawl", SCOPE)

    first = jobs.claim_next()
    second = jobs.claim_next()

    assert first is not None and first.status is JobStatus.RUNNING
    assert second is None


def test_jobs_are_claimed_oldest_first(jobs):
    a = jobs.enqueue("crawl", SCOPE, keyword="a")
    b = jobs.enqueue("crawl", SCOPE, keyword="b")

    assert jobs.claim_next().id == a.id
    jobs.finish(a.id, JobStatus.DONE)
    assert jobs.claim_next().id == b.id


def test_a_second_job_waits_instead_of_running_in_parallel(jobs):
    """5.5: xep hang. Hai job chay song song la hai nguoi ghi - dung cai ma ca
    thiet ke kho du lieu cam."""
    jobs.enqueue("crawl", SCOPE)
    jobs.enqueue("crawl", SCOPE)

    jobs.claim_next()

    assert jobs.has_running() is True
    assert jobs.claim_next() is None


def test_progress_is_reported_while_running_not_at_the_end(jobs):
    job = jobs.enqueue("crawl", SCOPE)
    jobs.claim_next()

    jobs.report_progress(job.id, processed=1, current_url="https://kingled.com.vn/a")

    giua_chung = jobs.get(job.id)
    assert (giua_chung.processed, giua_chung.status) == (1, JobStatus.RUNNING)
    assert giua_chung.current_url == "https://kingled.com.vn/a"


def test_cancelling_a_queued_job_is_immediate(jobs):
    """Chua co gi chay thi huy duoc ngay, khong phai doi worker doc la co."""
    job = jobs.enqueue("crawl", SCOPE)

    assert jobs.request_cancel(job.id).status is JobStatus.CANCELLED


def test_cancelling_a_running_job_goes_through_the_worker(jobs):
    """api khong giet duoc worker - no chi dat la co. Worker la ben duy nhat
    biet luc nao dung an toan (sau khi ban ghi vua lam xong da vao kho)."""
    job = jobs.enqueue("crawl", SCOPE)
    jobs.claim_next()

    assert jobs.request_cancel(job.id).status is JobStatus.CANCELLING
    assert jobs.is_cancelling(job.id) is True

    jobs.finish(job.id, JobStatus.CANCELLED, reason="Người dùng huỷ", processed=1)

    xong = jobs.get(job.id)
    assert xong.status is JobStatus.CANCELLED
    assert xong.processed == 1  # ban ghi da luu truoc luc huy KHONG bi bo di


def test_a_finished_job_cannot_be_cancelled_back(jobs):
    job = jobs.enqueue("crawl", SCOPE)
    jobs.claim_next()
    jobs.finish(job.id, JobStatus.DONE)

    assert jobs.request_cancel(job.id).status is JobStatus.DONE


def test_stop_reason_survives_so_the_user_can_read_why(jobs):
    """5.7: "cạn quota LLM" khac "bị chặn" khac "người dùng huỷ"."""
    job = jobs.enqueue("crawl", SCOPE)
    jobs.claim_next()

    jobs.finish(job.id, JobStatus.FAILED, reason="Cạn quota LLM")

    assert jobs.get(job.id).stop_reason == "Cạn quota LLM"


def test_a_dead_workers_job_goes_back_to_the_queue(jobs):
    """Khong co buoc nay thi mot worker chet giua chung khoa hang doi vinh
    vien: job cua no o 'running' mai mai va khong job moi nao chay duoc."""
    job = jobs.enqueue("crawl", SCOPE)
    jobs.claim_next()

    mot_gio_sau = datetime.now(timezone.utc) + timedelta(hours=1)
    assert jobs.reclaim_dead(now=mot_gio_sau) == [job.id]
    assert jobs.get(job.id).status is JobStatus.QUEUED
    assert jobs.claim_next().id == job.id


def test_a_live_worker_is_not_reclaimed(jobs):
    """Doi chung. Thu hoi nham mot job dang song thi hai worker cung ghi - dung
    cai ma ca thiet ke nay tranh."""
    job = jobs.enqueue("crawl", SCOPE)
    jobs.claim_next()
    jobs.report_progress(job.id, processed=1, current_url=None)

    assert jobs.reclaim_dead() == []
    assert jobs.get(job.id).status is JobStatus.RUNNING
