"""Tu khoa -> top N site LED ung vien, kem diem va ly do.

Ghep ba tang: `queries` (go gi), `engine` (hoi ai), `scoring` (tin ai). Tang
nay khong tu quyet dinh gi - no gom ket qua, goi cham diem, xep hang, va tra
ve. Nguoi dung la ben duyet.

HAI DUONG DUNG, cung mot bo may:

    tim_doi_thu()   tim doi thu MOI chua co trong danh sach
    tim_lai_site()  mot domain da dang ky chet/doi ten mien -> tim dia chi moi
                    cua chinh nhan do
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional

import httpx

from ..search import normalise
from ..sites.registry import SITE_PROFILES
from .engine import BingEngine, SearchEngine, SearchHit
from .queries import tim_lai_nhan, tu_danh_muc
from .scoring import UngVien, cham_diem, ly_do_loai

logger = logging.getLogger(__name__)

# Trang cua chinh minh. Khai o day chu khong suy ra: cong cu nay tim DOI THU,
# va trang cua chinh minh dung hang 2 cho "đèn led âm trần" (do that) nen
# khong loai la mat mot suat trong top 3 o gan nhu moi truy van.
CUA_MINH: tuple[str, ...] = ("rangdong.com.vn", "rangdong.vn")

_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class KetQuaTim:
    truy_van: list[str]
    ung_vien: list[UngVien]
    da_loai: list[tuple[str, str]]  # (domain, ly do)

    @property
    def top(self) -> list[UngVien]:
        return self.ung_vien


def _tai(url: str, timeout: float = 15.0) -> Optional[str]:
    """Tai mot trang de cham diem. Tra None neu khong tai duoc.

    Dung httpx thuan chu KHONG dung StealthFetcher: o day ta chi can vai tin
    hieu tho tren HTML de xep hang ung vien, con StealthFetcher dung mot
    browser that (vai giay moi trang, mot tien trinh Chromium) - qua dat cho
    mot buoc sang loc. Site chi render bang JS se bi cham thap oan, va do la
    danh doi da biet: no chi keo tut MOT bac trong danh sach de nguoi duyet,
    khong loai ai ca.
    """
    try:
        r = httpx.get(url, headers={"User-Agent": _UA}, timeout=timeout,
                      follow_redirects=True)
        return r.text if r.status_code == 200 else None
    except httpx.HTTPError as exc:
        logger.debug("Không tải được %s: %s", url, exc)
        return None


def _ten_nhan_da_biet() -> list[str]:
    ra = []
    for profile in SITE_PROFILES.values():
        ra.extend(t for t in [profile.brand_name, *profile.brand_aliases] if t)
    return sorted(set(ra))


def _gom(hits: Iterable[SearchHit], *, cua_minh: Iterable[str]) -> tuple[dict, list]:
    gom: dict[str, UngVien] = {}
    da_loai: list[tuple[str, str]] = []
    loai_roi: set[str] = set()

    for hit in hits:
        if hit.domain in loai_roi:
            continue
        ly_do = ly_do_loai(hit.domain, cua_minh=cua_minh)
        if ly_do:
            loai_roi.add(hit.domain)
            da_loai.append((hit.domain, ly_do))
            continue
        uv = gom.get(hit.domain)
        if uv is None:
            uv = gom[hit.domain] = UngVien(
                domain=hit.domain, title=hit.title, url=hit.url,
                da_dang_ky=hit.domain in SITE_PROFILES,
            )
        if hit.query not in uv.truy_van:
            uv.truy_van.append(hit.query)
        uv.hang_tot_nhat = min(uv.hang_tot_nhat, hit.rank)
    return gom, da_loai


def _xep_hang(
    gom: dict[str, UngVien],
    top: int,
    *,
    tai_trang: bool,
    ten_nhan_can_tim: Optional[str] = None,
) -> list[UngVien]:
    ten_nhan = _ten_nhan_da_biet()
    # Cham so bo theo thu hang truoc de chi PHAI TAI TRANG cho nhung ung vien
    # co co hoi vao top. Tai het moi domain la vai chuc request cho mot ket qua
    # ma phan lon se bi bo di.
    so_bo = sorted(gom.values(), key=lambda u: (u.hang_tot_nhat, -len(u.truy_van)))
    ung_vien: list[UngVien] = []
    for uv in so_bo[: max(top * 3, top)]:
        trang_chu = _tai(f"https://{uv.domain}/") if tai_trang else None
        trang_mau = _tai(uv.url) if (tai_trang and uv.url) else None
        ung_vien.append(cham_diem(
            uv, html_trang_chu=trang_chu, html_trang_mau=trang_mau,
            ten_nhan_da_biet=ten_nhan, ten_nhan_can_tim=ten_nhan_can_tim,
        ))
    ung_vien.extend(so_bo[max(top * 3, top):])
    ung_vien.sort(key=lambda u: (-u.diem, u.hang_tot_nhat))
    return ung_vien[:top]


def tim_doi_thu(
    *,
    truy_van: Optional[list[str]] = None,
    ten_danh_muc: Iterable[str] = (),
    engine: Optional[SearchEngine] = None,
    top: int = 3,
    moi_truy_van: int = 10,
    tai_trang: bool = True,
    cua_minh: Iterable[str] = CUA_MINH,
) -> KetQuaTim:
    """Tim doi thu LED moi. Tra ve top N ung vien kem diem va ly do.

    `truy_van` de trong thi tu dung tu ten danh muc trong kho - tu vung that
    cua nganh, do chinh doi thu viet (xem `queries.tu_danh_muc`).
    """
    engine = engine or BingEngine()
    truy_van = truy_van or tu_danh_muc(ten_danh_muc)

    hits: list[SearchHit] = []
    for q in truy_van:
        hits.extend(engine.search(q, limit=moi_truy_van))

    gom, da_loai = _gom(hits, cua_minh=cua_minh)
    return KetQuaTim(
        truy_van=list(truy_van),
        ung_vien=_xep_hang(gom, top, tai_trang=tai_trang),
        da_loai=da_loai,
    )


def tim_lai_site(
    ten_nhan: str,
    *,
    engine: Optional[SearchEngine] = None,
    top: int = 3,
    tai_trang: bool = True,
    loai_hang: Optional[str] = None,
) -> KetQuaTim:
    """Tim lai dia chi moi cua mot nhan da biet (domain cu chet hoac doi).

    Khac `tim_doi_thu` o mot cho quan trong: domain DA DANG KY khong bi loai va
    khong bi tru diem. Neu no van dung dau, do chinh la cau tra loi - site cu
    van song, khong co gi phai doi.
    """
    engine = engine or BingEngine()

    # Dung ca BI DANH da khai trong registry, khong chi chuoi nguoi dung go.
    # Ly do do duoc: "VNE" mot minh la ma co phieu (VNECO) va cho ra
    # vietstock/cafef/vnetrust, trong khi bi danh "VNE Led" da khai san trong
    # `SiteProfile` thi tro dung nganh. Bi danh ton tai chinh vi ten chinh
    # khong du phan biet - bo qua chung o day la vut di cong khai bao.
    ten = [ten_nhan]
    for profile in SITE_PROFILES.values():
        moi_cach_goi = [profile.brand_name, *profile.brand_aliases]
        if any(normalise(t) == normalise(ten_nhan) for t in moi_cach_goi if t):
            # Dai truoc: mot bi danh dai hon thi cu the hon, va truy van cu the
            # hon la thu dang can khi ten chinh da truot.
            ten += sorted(
                (t for t in moi_cach_goi
                 if t and normalise(t) != normalise(ten_nhan)),
                key=len, reverse=True,
            )
            break

    truy_van: list[str] = []
    for cach_goi in ten[:2]:
        for q in tim_lai_nhan(cach_goi, loai_hang=loai_hang):
            if q not in truy_van:
                truy_van.append(q)

    hits: list[SearchHit] = []
    for q in truy_van:
        hits.extend(engine.search(q, limit=10))

    gom, da_loai = _gom(hits, cua_minh=())
    ket_qua = _xep_hang(gom, top, tai_trang=tai_trang, ten_nhan_can_tim=ten_nhan)
    return KetQuaTim(truy_van=truy_van, ung_vien=ket_qua, da_loai=da_loai)


__all__ = ["CUA_MINH", "KetQuaTim", "tim_doi_thu", "tim_lai_site"]
