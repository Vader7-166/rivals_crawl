"""Tang API (capability `crawl-web-runtime`).

HAI LOAI ENDPOINT, va ranh gioi giua chung la mot RANG BUOC chu khong phai mot
cach sap xep cho gon:

    /api/...            CHI DOC kho du lieu. Khong endpoint nao o day ghi vao
                        `crawl.db` - co test chot dieu do (task 4.5).
    /api/jobs (POST)    Ghi DUY NHAT mot bang: `jobs`. Day la hang doi, khong
                        phai du lieu san pham.

Ly do: `crawl.db` chi chiu duoc MOT nguoi ghi, va nguoi do la worker. Api dat
viec vao hang doi roi buong ra; no khong bao gio tu crawl, tu trich xuat, hay
tu sua mot ban ghi san pham nao.

Api KHONG duoc bat che do nap lai trong Docker (design.md muc 4), nhung ly do o
day nhe hon ben worker: khong co build step nao de ma can nap lai - giao dien
la HTML+JS thuan, sua file roi bam F5.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..config import OUTPUT, STORE
from ..scope import SuggestionIndex, resolve
from ..search import ScopeKind
from ..sites.registry import SITE_PROFILES, brand_of
from ..store import (
    CategoryStore,
    CrawlStore,
    JobStatus,
    JobStore,
    connect,
    export_domain,
)
from ..discovery import tim_doi_thu, tim_lai_site, tu_danh_muc
from ..store.diff import DOI, HONG, VA, changes, diff, versions
from ..store.export import export_selection

logger = logging.getLogger("api")

GIAO_DIEN = Path(__file__).resolve().parent / "static"


def _read_only_connection() -> sqlite3.Connection:
    """Ket noi CHI DOC toi kho du lieu.

    `mode=ro` la mot rang buoc do SQLite ep, khong phai mot quy uoc trong ma
    nguon: mot endpoint viet nham cau UPDATE se hong NGAY va hong on ao, thay
    vi lang le tro thanh nguoi ghi thu hai.
    """
    conn = sqlite3.connect(f"file:{STORE.db_path}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


class _State:
    """Ket noi va cache dung chung cho ca vong doi tien trinh api.

    Hai ket noi chu KHONG phai mot: doc di qua ket noi chi-doc, con hang doi
    bat buoc phai ghi duoc. Tach ra thi rang buoc "api khong ghi du lieu san
    pham" duoc chinh SQLite giu, khong phu thuoc vao viec nguoi doc ma nho.
    """

    def __init__(self) -> None:
        self.read = _read_only_connection()
        self.crawl = CrawlStore(self.read)
        self.categories = CategoryStore(self.read)
        self.suggestions = SuggestionIndex(self.crawl, self.categories)

    @contextmanager
    def jobs(self) -> Iterator[JobStore]:
        """Ket noi GHI, mo va dong trong pham vi mot request.

        Khong giu mot ket noi ghi dung chung nhu ben doc, vi hai ly do doc lap:

        1. FastAPI chay endpoint dong bo tren threadpool, moi request mot luong
           khac nhau - mot doi tuong sqlite3 dung chung se nem
           "SQLite objects created in a thread can only be used in that same
           thread". Tat kiem tra do di thi doi lai phai tu serialise.
        2. Ghi o day chi la vai cau tren bang `jobs`, tinh bang mili giay. Giu
           mot ket noi ghi mo suot vong doi tien trinh de tiet kiem vai mili
           giay do la doi mot rui ro khoa lay mot khoan tiet kiem khong dang.
        """
        conn = connect(STORE.db_path)
        try:
            yield JobStore(conn)
        finally:
            conn.close()

    def close(self) -> None:
        self.read.close()


state: Optional[_State] = None


def get_state() -> _State:
    global state
    if state is None:
        state = _State()
    return state


app = FastAPI(title="Crawl đối thủ", docs_url="/api/docs")


@app.on_event("shutdown")
def _dong_ket_noi() -> None:
    if state is not None:
        state.close()


# -- tim kiem va pham vi (bao muc 3) -----------------------------------------


@app.get("/api/suggest")
def suggest(q: str = Query("", description="Từ khoá đang gõ"), limit: int = 8) -> dict:
    """Goi y khi dang go, tach nhom theo loai.

    Doc tu cache trong bo nho (`SuggestionIndex`): doc thang SQLite moi lan go
    phim mat 0,6-0,95s tren kho that, tuc khong dung duoc cho mot o tim kiem.
    """
    ket_qua = get_state().suggestions.suggest(q, limit=limit)
    return {
        "keyword": ket_qua.keyword,
        "brands": [_suggestion_json(s) for s in ket_qua.brands],
        "categories": [_suggestion_json(s) for s in ket_qua.categories],
        "products": [_suggestion_json(s) for s in ket_qua.products],
    }


def _suggestion_json(s) -> dict:
    return {
        "kind": s.kind.value,
        "label": s.label,
        # Chuoi de dien vao o tim kiem khi nguoi dung bam. Phai di KEM `kind`
        # lam `prefer`, neu khong mot goi y danh muc mang ten nhan hieu se ra
        # pham vi ca nhan hieu - xem docstring `search.Suggestion`.
        "query": s.query,
        "domains": list(s.domains),
        "products": s.products,
    }


@app.get("/api/scope")
def scope(
    q: str,
    prefer: Optional[str] = None,
    exclude: list[str] = Query(default=[]),
) -> dict:
    """Tu khoa -> pham vi KEM SO LIEU: tong / da co / con thieu, theo domain.

    `exclude` la cac URL danh muc nguoi dung tick BO. No di theo TUNG REQUEST
    va khong duoc luu o dau ca - do la mot lua chon luc dung, khong phai mot
    cau hinh phai bao tri (spec `crawl-scope-search`).
    """
    st = get_state()
    loai = ScopeKind(prefer) if prefer else None
    ket_qua = resolve(q, st.crawl, st.categories, prefer=loai,
                      exclude_categories=frozenset(exclude))
    return {
        "keyword": q,
        "kind": ket_qua.scope.kind.value,
        "reason": ket_qua.scope.reason,
        "alternatives": [k.value for k in ket_qua.scope.alternatives],
        "total": ket_qua.total,
        "have": ket_qua.have,
        "missing": ket_qua.missing,
        "domains": [
            {
                "domain": d.domain,
                "brand": d.brand,
                "total": d.total,
                "have": d.have,
                "missing": d.missing,
                # "Chưa dựng chỉ mục" KHAC HAN "không có sản phẩm nào" - hai
                # cai noi voi nguoi dung hai cau khac han (task 3.7).
                "needs_index": d.needs_index,
                "categories": [
                    {
                        "url": c.url, "name": c.name, "total": c.total,
                        "have": c.have, "missing": c.missing,
                        "ok": c.ok, "error": c.error,
                    }
                    for c in d.categories
                ],
            }
            for d in ket_qua.domains
        ],
    }


@app.get("/api/domains")
def domains() -> list[dict]:
    """Domain da dang ky kem trang thai: da probe chua, da dung chi muc chua,
    co bao nhieu ban ghi."""
    st = get_state()
    da_crawl = st.crawl.product_counts()
    ra = []
    for domain, profile in sorted(SITE_PROFILES.items()):
        ra.append({
            "domain": domain,
            "brand": profile.brand_name or domain,
            "products": da_crawl.get(domain, 0),
            "indexed": st.categories.has_index(domain),
        })
    # Domain co du lieu nhung chua dang ky ho so van phai hien ra - an di thi
    # nguoi dung khong hieu vi sao tong so khong khop.
    for domain, so_luong in sorted(da_crawl.items()):
        if domain not in SITE_PROFILES:
            ra.append({
                "domain": domain, "brand": brand_of(domain),
                "products": so_luong, "indexed": st.categories.has_index(domain),
            })
    return ra


@app.get("/api/domains/{domain}/products")
def products(
    domain: str,
    status: Optional[str] = None,
    needs_review: bool = False,
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """San pham cua mot domain, loc duoc theo trang thai va theo "can xu ly tay".

    "Can xu ly tay" dung dung dinh nghia cua duong xuat file (`export._needs_
    review`): hai o uu diem deu trong, hoac lay bang nhanh do tin thap. Hai
    dinh nghia song song la hai dinh nghia se lech nhau.
    """
    from ..store.export import _needs_review

    st = get_state()
    tat_ca = list(st.crawl.current_records(domain).values())
    loc = tat_ca
    if status:
        loc = [r for r in loc if r.crawl_status.value == status]
    if needs_review:
        loc = [r for r in loc if _needs_review(r) is not None]
    trang = loc[offset : offset + limit]
    return {
        "domain": domain,
        "total": len(tat_ca),
        "matched": len(loc),
        "products": [
            {
                "url": r.link_san_pham,
                "ten_san_pham": r.ten_san_pham,
                "ma_san_pham": r.ma_san_pham,
                "category_1": r.category_1,
                "gia": r.gia,
                "crawl_status": r.crawl_status.value,
                "crawl_error": r.crawl_error,
                "review_reason": _needs_review(r),
            }
            for r in trang
        ],
    }


# -- job ---------------------------------------------------------------------


class TaoJob(BaseModel):
    keyword: str
    prefer: Optional[str] = None
    exclude: list[str] = []


@app.post("/api/jobs")
def tao_job(body: TaoJob) -> dict:
    """Tao job crawl va tra ve dinh danh NGAY.

    Pham vi duoc CHOT thanh danh sach URL tai day chu khong tra cuu lai luc
    chay: nguoi dung vua nhin thay con so "còn thiếu N" va bam dong y voi chinh
    no. Tra cuu lai luc chay thi pham vi co the da khac.
    """
    st = get_state()
    loai = ScopeKind(body.prefer) if body.prefer else None
    pham_vi = resolve(body.keyword, st.crawl, st.categories, prefer=loai,
                      exclude_categories=frozenset(body.exclude))
    if pham_vi.scope.kind is ScopeKind.NONE or not pham_vi.domains:
        raise HTTPException(400, pham_vi.scope.reason or "Từ khoá không khớp phạm vi nào")

    can_crawl = {
        d.domain: st.crawl.urls_needing_crawl(d.product_urls)
        for d in pham_vi.domains
    }
    can_crawl = {k: v for k, v in can_crawl.items() if v}
    if not can_crawl:
        # HAI tinh huong khac han nhau, va gop chung lam mot la noi doi voi
        # nguoi dung: mot kho RONG bao "đã crawl đủ" thi ho di tim file ket qua
        # khong ton tai. Do chinh la ca da gap khi dung container lan dau.
        if pham_vi.total == 0:
            chua_chi_muc = [d.domain for d in pham_vi.domains if d.needs_index]
            raise HTTPException(409, (
                "Phạm vi này chưa có sản phẩm nào trong kho"
                + (f" và chưa dựng chỉ mục danh mục cho {', '.join(chua_chi_muc)}"
                   " — dựng chỉ mục trước (scripts/build_category_index.py) "
                   "rồi tìm lại." if chua_chi_muc else ".")
            ))
        raise HTTPException(409, "Phạm vi này đã crawl đủ — không có gì để chạy.")

    with st.jobs() as jobs:
        job = jobs.enqueue("crawl", can_crawl, keyword=body.keyword)
        return _job_json(job) | {"queued_behind_running_job": jobs.has_running()}


@app.get("/api/jobs")
def liet_ke_job(limit: int = 20) -> list[dict]:
    with get_state().jobs() as jobs:
        return [_job_json(j) for j in jobs.recent(limit)]


@app.get("/api/jobs/{job_id}")
def xem_job(job_id: int) -> dict:
    with get_state().jobs() as jobs:
        job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, f"Không có job {job_id}")
    return _job_json(job)


@app.post("/api/jobs/{job_id}/cancel")
def huy_job(job_id: int) -> dict:
    with get_state().jobs() as jobs:
        job = jobs.request_cancel(job_id)
    if job is None:
        raise HTTPException(404, f"Không có job {job_id}")
    return _job_json(job)


def _job_json(job) -> dict:
    return {
        "id": job.id,
        "kind": job.kind,
        "keyword": job.keyword,
        "status": job.status.value,
        "total": job.total,
        "processed": job.processed,
        "current_url": job.current_url,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "stop_reason": job.stop_reason,
        "domains": sorted(job.scope),
    }


@app.get("/api/jobs/{job_id}/events")
async def dong_su_kien(job_id: int) -> StreamingResponse:
    """Tien do dang SSE (`text/event-stream`) - day theo dong, khong hoi vong.

    Chon SSE chu khong phai WebSocket vi luong du lieu o day MOT CHIEU: worker
    bao tien do, trinh duyet chi nghe. `EventSource` phia trinh duyet tu noi
    lai khi dut, di qua proxy nhu HTTP thuong, va khong can thu vien nao
    (design.md muc 4b).

    Dong su kien DONG khi job ve trang thai cuoi - de mo thi trinh duyet cu
    noi lai mai mot job da xong.
    """
    st = get_state()
    with st.jobs() as jobs:
        if jobs.get(job_id) is None:
            raise HTTPException(404, f"Không có job {job_id}")

    async def phat() -> Iterator[str]:
        truoc_do = None
        while True:
            with st.jobs() as jobs:
                job = jobs.get(job_id)
            if job is None:
                break
            hien_tai = _job_json(job)
            # Chi gui khi CO DOI. Mot job 70 phut ma moi giay day mot goi giong
            # het nhau la 4.200 goi vo nghia.
            if hien_tai != truoc_do:
                yield f"data: {json.dumps(hien_tai, ensure_ascii=False)}\n\n"
                truoc_do = hien_tai
            if job.status.is_final:
                break
            await asyncio.sleep(1.0)

    return StreamingResponse(
        phat(),
        media_type="text/event-stream",
        # Proxy dem lai dong su kien thi tien do den theo tung cuc, hoac khong
        # den. Hai header nay tat viec do.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# -- so sanh hai phien ban trich xuat ----------------------------------------


@app.get("/api/domains/{domain}/versions")
def phien_ban(domain: str) -> list[dict]:
    """Cac nhan `extractor_version` da co cua mot domain, kem so snapshot."""
    return [
        {"version": v.version, "snapshots": v.snapshots}
        for v in versions(get_state().read, domain)
    ]


@app.get("/api/domains/{domain}/diff")
def so_sanh(domain: str, before: str, after: str) -> dict:
    """Bang dem ba nhom (vá được / làm hỏng / đổi khác) theo tung cot.

    Ba nhom tach rieng vi y nghia khac han nhau, va chinh su tach do la thu tra
    loi duoc cau "sửa vừa rồi lãi hay hại".
    """
    ket_qua = diff(get_state().read, domain, before, after)
    return {
        "domain": domain,
        "before": before,
        "after": after,
        "shared_snapshots": ket_qua.shared_snapshots,
        # Ban ghi khong co snapshot (nhap tu .xlsx cu) khong so duoc. Bao ro so
        # luong chu khong nuot (task 7.5).
        "skipped_without_snapshot": ket_qua.skipped_without_snapshot,
        # Co `message` nghia la phep so KHONG HOP LE - khac han "hop le va
        # khong co gi doi". Giao dien phai hien cau nay thay vi mot bang rong.
        "message": ket_qua.message,
        "columns": [
            {"field": ten, "va": c[VA], "hong": c[HONG], "doi": c[DOI]}
            for ten, c in ket_qua.counts.items()
        ],
    }


@app.get("/api/domains/{domain}/diff/cells")
def o_da_doi(
    domain: str,
    before: str,
    after: str,
    field: str,
    group: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    """DANH SACH DAY DU san pham cua mot nhom thay doi, kem gia tri truoc/sau.

    Khong gioi han mac dinh (task 7.6): "vá được 47 ô" ma chi xem duoc 3 thi 44
    o kia van phai mo SQLite tra tay - dung cai ma man so sanh sinh ra de khoi
    phai lam.

    Noi dung dai duoc cat CO BAO (`truncated`), khong cat am tham (task 7.7):
    mot o bi cat lang le doc y het mot o that su ngan di.
    """
    o = changes(get_state().read, domain, before, after,
                field_name=field, group=group, limit=limit)
    return {
        "domain": domain, "field": field, "group": group, "total": len(o),
        "cells": [
            {
                "url": c.url,
                "group": c.group,
                "before": _cat(c.before),
                "after": _cat(c.after),
                "truncated": _qua_dai(c.before) or _qua_dai(c.after),
            }
            for c in o
        ],
    }


# Do dai toi da cua mot o khi tra qua HTTP. Mot o "Thông số kỹ thuật" that co
# the dai hang chuc nghin ky tu; gui nguyen ca nghin o nhu vay lam trang so
# sanh nang len hang chuc MB.
_MAX_O = 4_000


def _qua_dai(value: Optional[str]) -> bool:
    return isinstance(value, str) and len(value) > _MAX_O


def _cat(value):
    if not _qua_dai(value):
        return value
    return value[:_MAX_O] + "\n[… đã cắt — mở URL sản phẩm để xem đầy đủ]"


# -- xuat file ---------------------------------------------------------------


@app.get("/api/export")
def xuat_file(
    q: str,
    prefer: Optional[str] = None,
    exclude: list[str] = Query(default=[]),
    order: list[str] = Query(default=[]),
) -> FileResponse:
    """Xuat pham vi dang chon ra .xlsx.

    XUAT DUOC ngay ca khi pham vi moi crawl mot phan: mot luot crawl la 33-70
    phut, bat cho xong moi duoc cam file la bat cho vo ich khi phan da co da
    dung duoc (Open Question 1, chot o day).

    So con thieu di kem trong header `X-Missing` chu khong bi nuot - nguoi nhan
    file phai biet minh dang cam ban day du hay ban mot phan.
    """
    st = get_state()
    loai = ScopeKind(prefer) if prefer else None
    pham_vi = resolve(q, st.crawl, st.categories, prefer=loai,
                      exclude_categories=frozenset(exclude))
    if pham_vi.scope.kind is ScopeKind.NONE or not pham_vi.domains:
        raise HTTPException(400, pham_vi.scope.reason or "Từ khoá không khớp phạm vi nào")

    duong_dan = OUTPUT.output_dir / f"{_ten_file(q)}.xlsx"
    duong_dan.parent.mkdir(parents=True, exist_ok=True)
    _, canh_bao = export_selection(
        st.crawl,
        {d.domain: d.product_urls for d in pham_vi.domains},
        duong_dan,
        keyword=q,
        sheet_by_brand=pham_vi.scope.kind is not ScopeKind.BRAND,
        brand_order=order or None,
    )
    return FileResponse(
        duong_dan,
        filename=duong_dan.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "X-Missing": str(pham_vi.missing),
            "X-Total": str(pham_vi.total),
            "X-Review-Rows": str(canh_bao),
        },
    )


def _ten_file(keyword: str) -> str:
    from ..search import normalise

    return normalise(keyword).replace(" ", "-") or "ket-qua"


# -- tim doi thu bang bo may tim kiem ----------------------------------------


@app.get("/api/discover")
def tim_doi_thu_moi(
    q: list[str] = Query(default=[], description="Từ khoá; để trống thì dựng từ kho"),
    top: int = 3,
    brand: Optional[str] = Query(None, description="Tìm LẠI site của nhãn này"),
) -> dict:
    """Top N site LED ứng viên, kèm điểm và LÝ DO từng tín hiệu.

    Endpoint nay GOI RA NGOAI (bo may tim kiem + trang chu ung vien) nen no
    cham hon moi endpoint khac han - tinh bang chuc giay. Giao dien phai bao
    "đang tìm" chu khong de nguoi dung tuong treo.

    KHONG ghi gi vao kho, va khong tu them domain nao vao registry: nguoi dung
    la ben duyet. Cung hinh voi man xac nhan pham vi.
    """
    st = get_state()
    if brand:
        ket_qua = tim_lai_site(brand, top=top)
    else:
        tu_khoa = list(q) or tu_danh_muc(
            [ten for _, ten, _ in st.crawl.category_counts()]
        )
        ket_qua = tim_doi_thu(truy_van=tu_khoa, top=top)
    return {
        "mode": "tim_lai" if brand else "tim_moi",
        "brand": brand,
        "queries": ket_qua.truy_van,
        "candidates": [
            {
                "domain": uv.domain,
                "title": uv.title,
                "url": uv.url,
                "score": uv.diem,
                "best_rank": uv.hang_tot_nhat,
                "queries": uv.truy_van,
                # Da co trong registry KHONG phai ly do an di: voi viec tim lai
                # site, chinh no con song la cau tra loi can biet.
                "already_registered": uv.da_dang_ky,
                "signals": [
                    {"name": t.ten, "score": t.diem, "reason": t.ly_do}
                    for t in uv.tin_hieu
                ],
            }
            for uv in ket_qua.ung_vien
        ],
        "dropped": [{"domain": d, "reason": ly} for d, ly in ket_qua.da_loai],
    }


# -- giao dien ---------------------------------------------------------------
#
# Phuc vu TINH tu thu muc `static/`, bind mount tu may chu khi chay Docker: sua
# file roi bam F5 la thay, khong dung lai image, khong build step, khong Node
# (design.md muc 4b).
#
# Dat o CUOI file: `StaticFiles` mount tai "/" nen no phai duoc dang ky sau moi
# route `/api/...`, neu khong no nuot het.
app.mount("/", StaticFiles(directory=GIAO_DIEN, html=True), name="giao-dien")


__all__ = ["app", "export_domain", "get_state"]
