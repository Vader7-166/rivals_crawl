"""Lay ket qua tu mot bo may tim kiem.

Tang nay chi lam MOT viec: tu khoa -> danh sach (thu hang, domain, tieu de,
url). Moi phan doan "day co phai site LED cua nha san xuat khong" nam o
`scoring.py` - tach ra vi hai thu doi hai kieu kiem chung khac han: cai nay
kiem bang "co parse duoc trang ket qua khong", cai kia bang "co xep dung site
that khong".

Vi sao Bing lam mac dinh, do ngay 11/09/2026 tren chinh may nay:

    bing                 HTTP 200, 123.521 ky tu, 16 domain  -> DUNG DUOC
    html.duckduckgo.com  HTTP 200,  33.340 ky tu,  0 domain  -> trang chan
    lite.duckduckgo.com  HTTP 200,  26.697 ky tu,  0 domain  -> trang chan

Bing khong doi khoa API, con Google thi doi (CSE co han muc 100 truy van/ngay
mien phi). Nhung Bing la mot trang HTML co the doi bat cu luc nao - do la ly do
co `SearchEngine` truu tuong o day: ngay no chan, cam mot khoa Google/Serper
vao la xong, khong tang nao ben tren phai sua.
"""
from __future__ import annotations

import base64
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Trinh duyet that. Bing tra ve mot trang rut gon cho user-agent la thu vien
# HTTP, va trang rut gon do khong co `li.b_algo` nao.
_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Nghi giua hai truy van. Mot dot do thuong 5-10 truy van nen tong do tre khong
# dang ke, doi lai khong bi chan giua chung - va bi chan thi ca dot hong chu
# khong phai cham di.
NGHI_GIUA_HAI_TRUY_VAN = 1.5


@dataclass
class SearchHit:
    rank: int
    domain: str
    title: str
    url: str
    query: str


class SearchEngine(ABC):
    name: str = "unknown"

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[SearchHit]:
        """Tra ve ket qua da bo trung domain, giu THU HANG goc."""
        raise NotImplementedError


class BingEngine(SearchEngine):
    name = "bing"

    def __init__(self, *, timeout: float = 25.0, nghi: float = NGHI_GIUA_HAI_TRUY_VAN):
        self._timeout = timeout
        self._nghi = nghi
        self._lan_cuoi = 0.0

    def search(self, query: str, limit: int = 10) -> list[SearchHit]:
        cho = self._nghi - (time.monotonic() - self._lan_cuoi)
        if cho > 0:
            time.sleep(cho)
        try:
            r = httpx.get(
                "https://www.bing.com/search",
                params={"q": query, "count": 20},
                headers={"User-Agent": _UA},
                timeout=self._timeout,
                follow_redirects=True,
            )
            r.raise_for_status()
        except httpx.HTTPError as exc:
            # KHONG nem tiep: mot truy van hong khong duoc lam hong ca dot do.
            # Ben goi thay danh sach rong cho tu khoa nay va van co ket qua cua
            # cac tu khoa khac.
            logger.warning("Truy vấn %r hỏng: %s", query, exc)
            return []
        finally:
            self._lan_cuoi = time.monotonic()

        return self._doc(r.text, query, limit)

    def _doc(self, html: str, query: str, limit: int) -> list[SearchHit]:
        ra: list[SearchHit] = []
        da_co: set[str] = set()
        for li in BeautifulSoup(html, "lxml").select("li.b_algo"):
            the = li.select_one("h2 a[href]")
            if the is None:
                continue
            url = go_lop_boc(the["href"])
            domain = urlparse(url).netloc
            # Bo trung theo DOMAIN chu khong theo URL: mot site chiem 4 vi tri
            # dau van chi la mot ung vien, va giu ca 4 se lam tran `limit` bang
            # mot site duy nhat.
            if not domain or domain in da_co:
                continue
            da_co.add(domain)
            ra.append(SearchHit(
                rank=len(ra) + 1, domain=domain,
                title=the.get_text(" ", strip=True), url=url, query=query,
            ))
            if len(ra) >= limit:
                break
        if not ra:
            # Trang khong co ket qua nao THUONG la dau hieu bi chan, khong phai
            # "tu khoa khong co ket qua" - noi ra de nguoi chay biet ma doi
            # engine, thay vi tuong nganh nay khong co site nao.
            logger.warning(
                "Không đọc được kết quả nào cho %r — có thể Bing đã đổi bố cục "
                "hoặc đang chặn. Cân nhắc cắm một engine có khoá API.", query,
            )
        return ra


def go_lop_boc(href: str) -> str:
    """URL that tu link boc cua Bing.

    Bing tra ve `https://www.bing.com/ck/a?...&u=a1<base64url>` chu khong tra
    URL that. Khong go lop boc thi MOI ket qua deu co domain `www.bing.com` -
    tuc ca tang chon loc ben tren khong co gi de lam viec.
    """
    if "bing.com/ck/" not in href:
        return href
    u = parse_qs(urlparse(href).query).get("u", [""])[0]
    if not u.startswith("a1"):
        return href
    raw = u[2:]
    raw += "=" * (-len(raw) % 4)  # base64url cua Bing bi cat dau "="
    try:
        that = base64.urlsafe_b64decode(raw).decode("utf-8", "replace")
    except (ValueError, UnicodeDecodeError):
        return href
    # PHAI kiem lai hinh dang: `b64decode` mac dinh BO QUA ky tu khong hop le
    # thay vi nem loi, nen mot chuoi rac giai ma "thanh cong" ra chuoi rong.
    # Tra ve chuoi rong thi domain rong, va ung vien bien mat khong dau vet.
    return that if that.startswith(("http://", "https://")) else href


class StaticEngine(SearchEngine):
    """Engine gia cho test: tra ve danh sach da khai san.

    Co mat trong ma nguon that (khong phai trong tests/) vi no cung la duong
    chay lai mot dot do cu tu ket qua da luu, khong cham mang.
    """

    name = "static"

    def __init__(self, ket_qua: dict[str, list[str]]):
        self._ket_qua = ket_qua

    def search(self, query: str, limit: int = 10) -> list[SearchHit]:
        return [
            SearchHit(rank=i, domain=d, title=d, url=f"https://{d}/", query=query)
            for i, d in enumerate(self._ket_qua.get(query, [])[:limit], start=1)
        ]


__all__ = ["BingEngine", "SearchEngine", "SearchHit", "StaticEngine", "go_lop_boc"]
