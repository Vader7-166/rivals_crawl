"""Hang doi job nam trong chinh `crawl.db` (capability `crawl-job-runner`).

Ly do khong dung broker rieng: design.md Open Question 4. Tom tat - rang buoc
MOT NGUOI GHI da loai bo phan kho cua bai toan hang doi, nen viec con lai rut
thanh "lay job cho lau nhat", thu SQLite lam dung trong mot transaction.

RANH GIOI voi hai store kia:

    crawl_store.py      LICH SU (snapshot + trich xuat) - khong bao gio ghi de
    category_store.py   CACHE DAN XUAT - xoa dung lai duoc
    job_store.py (day)  TRANG THAI VAN HANH - job dang cho / dang chay / da xong

AN TOAN LUONG: khac hai file tren, file nay duoc ghi tu HAI tien trinh - api
tao job, worker nhan va cap nhat tien do. Do la ly do `claim_next()` phai la
mot cau UPDATE dieu kien chu khong phai doc-roi-ghi: hai worker cung hoi mot
luc thi dung mot worker thang, va chuyen do dung ngay ca khi ta chi dinh chay
mot worker (khoi dong lai trong luc ban cu chua chet han).

Cac dong ghi vao day KHONG dung chung ket noi voi crawl_store: moi tien trinh
mo ket noi cua rieng no (WAL cho phep doc song song voi mot nguoi ghi).
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    # Nguoi dung da bam huy nhung worker chua doc toi. Trang thai TRUNG GIAN nay
    # bat buoc phai co: api khong the giet worker, no chi dat duoc mot la co, va
    # worker la ben duy nhat biet luc nao dung an toan (giua hai trang, sau khi
    # ban ghi vua lam xong da vao kho).
    CANCELLING = "cancelling"

    @property
    def is_final(self) -> bool:
        return self in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED)


# Job 'running' ma khong co nhip tim nao trong khoang nay duoc coi la cua mot
# worker da chet. Rong rai co chu dich: mot vong lap crawl co the ket o mot lan
# fetch cham (timeout cua StealthFetcher tinh bang chuc giay) va thu hoi nham
# mot job dang song thi hai worker cung ghi - dung cai ma ca thiet ke nay tranh.
DEAD_AFTER = timedelta(minutes=5)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: Optional[datetime] = None) -> str:
    return (moment or _now()).isoformat(timespec="seconds")


@dataclass
class Job:
    id: int
    kind: str
    keyword: Optional[str]
    # domain -> danh sach URL da chot luc TAO job.
    scope: dict[str, list[str]] = field(default_factory=dict)
    status: JobStatus = JobStatus.QUEUED
    total: int = 0
    processed: int = 0
    current_url: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    stop_reason: Optional[str] = None

    @property
    def urls(self) -> list[str]:
        return [url for urls in self.scope.values() for url in urls]


def _to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        kind=row["kind"],
        keyword=row["keyword"],
        scope=json.loads(row["scope_json"]),
        status=JobStatus(row["status"]),
        total=row["total"],
        processed=row["processed"],
        current_url=row["current_url"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        stop_reason=row["stop_reason"],
    )


class JobStore:
    """Boc mot ket noi SQLite. Khong tu mo/dong - ben goi quyet dinh vong doi."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    # -- phia api ----------------------------------------------------------

    def enqueue(
        self,
        kind: str,
        scope: dict[str, list[str]],
        *,
        keyword: Optional[str] = None,
    ) -> Job:
        """Them mot job vao hang doi. Tra ve job da co dinh danh, NGAY - ben goi
        khong duoc cho crawl xong (33-70 phut) de tra loi mot request HTTP."""
        total = sum(len(urls) for urls in scope.values())
        cur = self._conn.execute(
            "INSERT INTO jobs (kind, keyword, scope_json, status, total, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (kind, keyword, json.dumps(scope, ensure_ascii=False),
             JobStatus.QUEUED.value, total, _iso()),
        )
        self._conn.commit()
        return self.get(cur.lastrowid)

    def get(self, job_id: int) -> Optional[Job]:
        row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _to_job(row) if row else None

    def recent(self, limit: int = 20) -> list[Job]:
        return [
            _to_job(r)
            for r in self._conn.execute(
                "SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,)
            )
        ]

    def request_cancel(self, job_id: int) -> Optional[Job]:
        """Dat la co huy. KHONG giet gi ca.

        Job con trong hang doi thi huy duoc ngay - chua co gi chay. Job dang
        chay chi chuyen sang CANCELLING; chinh worker se dung o diem an toan va
        chot lai thanh CANCELLED. Ban ghi da luu truoc do GIU NGUYEN, va do la
        hanh vi dung: chung da nam trong kho, huy job khong phai la hoan tac.
        """
        job = self.get(job_id)
        if job is None or job.status.is_final:
            return job
        moi = JobStatus.CANCELLED if job.status is JobStatus.QUEUED else JobStatus.CANCELLING
        finished = _iso() if moi is JobStatus.CANCELLED else None
        self._conn.execute(
            "UPDATE jobs SET status = ?, stop_reason = ?, finished_at = ? WHERE id = ?",
            (moi.value, "Người dùng huỷ", finished, job_id),
        )
        self._conn.commit()
        return self.get(job_id)

    # -- phia worker -------------------------------------------------------

    def claim_next(self) -> Optional[Job]:
        """Nhan job cho lau nhat, hoac None neu hang doi rong.

        MOT cau UPDATE co dieu kien chu khong phai doc-roi-ghi: hai worker cung
        hoi mot luc thi dung mot ben thay `rowcount == 1`. Diem nay quyet dinh
        tinh dung cua ca hang doi, nen no khong duoc "don gian hoa" thanh
        SELECT roi UPDATE.
        """
        # `NOT EXISTS (... dang chay ...)` la co che XEP HANG, nam ngay trong
        # cau nhan job chu khong phai mot buoc kiem tra rieng truoc do: tach ra
        # thi giua luc kiem va luc nhan van con khe cho job thu hai chen vao, va
        # hai job chay song song la HAI NGUOI GHI - dung dieu ma ca thiet ke kho
        # du lieu cam.
        cur = self._conn.execute(
            "UPDATE jobs SET status = ?, started_at = ?, heartbeat_at = ? "
            "WHERE id = (SELECT id FROM jobs WHERE status = ? ORDER BY id LIMIT 1) "
            "AND NOT EXISTS (SELECT 1 FROM jobs WHERE status IN (?, ?))",
            (JobStatus.RUNNING.value, _iso(), _iso(), JobStatus.QUEUED.value,
             JobStatus.RUNNING.value, JobStatus.CANCELLING.value),
        )
        self._conn.commit()
        if not cur.rowcount:
            return None
        row = self._conn.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY started_at DESC, id DESC LIMIT 1",
            (JobStatus.RUNNING.value,),
        ).fetchone()
        return _to_job(row) if row else None

    def report_progress(self, job_id: int, *, processed: int, current_url: Optional[str]) -> None:
        """Cap nhat tien do TRONG LUC chay, khong phai luc xong.

        Cung la nhip tim: mot job dang tien la mot job dang song, khong can mot
        duong bao song thu hai co the lech voi su that.
        """
        self._conn.execute(
            "UPDATE jobs SET processed = ?, current_url = ?, heartbeat_at = ? WHERE id = ?",
            (processed, current_url, _iso(), job_id),
        )
        self._conn.commit()

    def is_cancelling(self, job_id: int) -> bool:
        row = self._conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return bool(row) and row["status"] in (
            JobStatus.CANCELLING.value, JobStatus.CANCELLED.value
        )

    def finish(
        self,
        job_id: int,
        status: JobStatus,
        *,
        reason: Optional[str] = None,
        processed: Optional[int] = None,
    ) -> Optional[Job]:
        """Chot trang thai cuoi. `reason` phai noi duoc job dung VI SAO - "cạn
        quota LLM" khac "bị chặn" khac "người dùng huỷ"."""
        if processed is None:
            self._conn.execute(
                "UPDATE jobs SET status = ?, stop_reason = ?, finished_at = ?, "
                "current_url = NULL WHERE id = ?",
                (status.value, reason, _iso(), job_id),
            )
        else:
            self._conn.execute(
                "UPDATE jobs SET status = ?, stop_reason = ?, finished_at = ?, "
                "processed = ?, current_url = NULL WHERE id = ?",
                (status.value, reason, _iso(), processed, job_id),
            )
        self._conn.commit()
        return self.get(job_id)

    def reclaim_dead(
        self,
        *,
        dead_after: timedelta = DEAD_AFTER,
        now: Optional[datetime] = None,
    ) -> list[int]:
        """Tra cac job cua worker da chet ve hang doi. Tra ve danh sach id.

        Khong co buoc nay thi mot worker chet giua chung khoa hang doi vinh
        vien: job cua no o 'running' mai mai va khong worker nao nhan job moi
        (xep hang: mot job chay mot luc).

        An toan vi crawl-lai-co-chon-loc: chay lai la CHAY TIEP, nhung URL da
        vao kho khong bi fetch lai.
        """
        # `now` tiem vao duoc de test khong phai ngu that 5 phut. Mac dinh la
        # dong ho that; khong ben goi nao trong ma san xuat truyen tham so nay.
        cutoff = _iso((now or _now()) - dead_after)
        rows = self._conn.execute(
            "SELECT id FROM jobs WHERE status = ? AND "
            "(heartbeat_at IS NULL OR heartbeat_at < ?)",
            (JobStatus.RUNNING.value, cutoff),
        ).fetchall()
        ids = [r["id"] for r in rows]
        if ids:
            holders = ", ".join("?" for _ in ids)
            self._conn.execute(
                f"UPDATE jobs SET status = ?, started_at = NULL, current_url = NULL, "
                f"stop_reason = ? WHERE id IN ({holders})",
                (JobStatus.QUEUED.value,
                 "Worker dừng giữa chừng — job được đưa lại vào hàng đợi", *ids),
            )
            self._conn.commit()
        return ids

    def has_running(self) -> bool:
        """Co job nao dang chay khong - de api tra loi "job cua ban dang xep
        hang sau mot job khac" thay vi de nguoi dung tuong he thong treo."""
        row = self._conn.execute(
            "SELECT 1 FROM jobs WHERE status IN (?, ?) LIMIT 1",
            (JobStatus.RUNNING.value, JobStatus.CANCELLING.value),
        ).fetchone()
        return row is not None


__all__ = ["DEAD_AFTER", "Job", "JobStatus", "JobStore"]
