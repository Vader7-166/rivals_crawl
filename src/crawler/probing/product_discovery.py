"""Tim URL san pham khi site KHONG co sitemap dung duoc. Tang 0, nhanh du phong.

Truoc file nay, nhanh khong-sitemap cua `prober.py` dung o giua duong: no xac
nhan duoc TRANG DANH MUC nhung khong ai bien trang danh muc thanh URL san pham,
nen `crawl_site.py` van dung voi "probe khong tra ve URL san pham nao". Do la
ly do 5 doi thu (Roman, Panasonic, MPE, Nanoco, VNE, Duhal) khong crawl duoc.

Tang 0.5 (`category_crawl.py`) KHONG thay the duoc cho viec nay: no nhan dien
san pham bang TAP URL SAN PHAM DA CO tu sitemap. Khong co sitemap thi tap do
rong, va moi trang deu "khong phai san pham".

Ba pha, moi pha giai mot bai toan da do duoc tren trang that:

PHA A - tim trang luoi, di TOI DA 2 CHANG tu trang chu.
    Menu cua Roman khong tro thang toi trang luoi: `den-noi-that.html` trong
    menu la trang landing (do duoc 26 the <a> boc <img>, duoi nguong 30 cua
    `detection.CARD_LINK_THRESHOLD`), chinh no moi tro toi 13 trang luoi that
    (`den-downlight-led.html` do duoc 52). Vi vay trang KHONG phai luoi van
    duoc di tiep mot chang - nhung chi mot, de khong bien tang 0 thanh mot con
    crawler bo toan site.

PHA B - ung vien = LINK BOC ANH, hoac neu trang khong co the anh thi LINK
    LAP LAI CUNG MOT HINH DANG.
    Luoi san pham thuong la the anh. Loc theo `<a>` co chua `<img>` vut duoc
    menu/footer/chinh sach ma khong can biet gi ve site: do tren Roman, trang
    landing 26 the anh nhung tong so link la hang tram.

    Nhung khong phai theme nao cung boc anh trong the <a>: do tren VNE, trang
    danh muc `den-led-dan-dung/` co 100 link san pham ma chi 1 the anh - loc
    theo the anh thi ca site cho ra 0 ung vien. Voi nhung trang do, dau hieu
    thay the la SU LAP LAI: 100 link kia deu cung hinh dang
    `/index.php/product/*`, con menu/footer thi moi link mot hinh dang khac
    nhau. Chi dung khi trang khong co du the anh, de site nao boc anh tu te
    van di duong re.

PHA B2 - vut ung vien nam trong MENU (chi an khi site co the menu that).
    Roman de trang danh muc va trang san pham GIONG HET nhau duoi moi tin hieu
    cua `detection.py`: san pham `den-op-tran-led-roman-elt7128-12w.html` do
    duoc 11 so tien / 29 the anh, con danh muc `aptomat.html` cung co gia tren
    tung the hang. Thu tach duoc hai loai la VI TRI: danh muc nam trong menu
    dieu huong, san pham thi khong. Do tren Roman: menu trang chu chua
    `aptomat.html`, `chieu-sang-cong-nghiep.html`; menu cua chinh trang landing
    chua `am-sieu-toc.html`, `bo-den-tuyp-led.html` - ca 4 deu la danh muc bi
    cham nham la san pham truoc khi co buoc nay.

    Gia phai tra: site nao dat mot san pham cu the len menu thi san pham do bi
    bo qua. Doi lai la khong keo CA danh muc vao dataset - lech ve phia bo sot
    vai ban ghi, khong lech ve phia bia ra ban ghi rong.

PHA C - xac nhan theo HINH DANG URL, khong phai theo tung URL.
    Hinh dang = duong dan da thay doan cuoi bang `*` (vd `/index.php/product/*`
    cua VNE, `/danh-sach-san-pham/*` cua MPE). Site sach thi moi hinh dang
    thuan mot loai, lay mau 5 URL la du ket luan cho ca nhom -> re.
    Nhung Roman de URL PHANG: san pham `den-op-tran-led-roman-elt7128-12w.html`
    va danh muc `den-noi-that.html` cung hinh dang `/*.html`, khong tach duoc
    bang hinh dang. Nen khi ty le mau roi vao KHOANG GIUA, nhom do bi kiem
    TUNG URL thay vi doan bua cho ca nhom - dat hon nhung khong keo trang rac
    vao dataset (bug "559 thay vi 486", xem docs/pipeline.md).

Bat bien: pha nao cung CHI fetch, KHONG goi LLM. Ket qua di thang vao
`ProbeResult.product_urls`, tuc tang 0.5 va `crawl_site.py` dung duoc nguyen xi.
"""
from __future__ import annotations

import logging
import random
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable, Optional
from urllib.parse import parse_qsl, urljoin, urlparse

from bs4 import BeautifulSoup

from .category_crawl import page_links, pagination_candidates
from .detection import analyze_page
from .menu_crawl import nav_links

logger = logging.getLogger(__name__)

# Tran so trang duoc fetch cho CA luot do. Day la tran AN TOAN (chan mot site
# sinh URL vo han), khong phai tran tiet kiem: mot lan do la 1 fetch/trang va
# KHONG goi LLM, con luot crawl that sau do la 1 fetch + 1 luot LLM cho tung
# san pham - dat hon nhieu lan. Ket qua lai duoc cache 30 ngay theo domain.
#
# Da tung dat 400 va do thay CA BA site deu bi cat ngang: Roman 139 URL,
# Duhal 82, MPE 180 - deu bao `(CHAM TRAN)`, tuc danh sach con thieu. Chi VNE
# (29 trang) va Nanoco (54 trang) la ve dich trong 400.
DEFAULT_PAGE_BUDGET = 1500

# So chang toi da tinh tu trang chu. 2 = trang chu -> landing -> luoi, dung
# bang do sau da do tren Roman (xem PHA A). Sau hon nua thi tang 0 lan sang bai
# blog / trang tin, la thu khong bao gio dan toi san pham.
MAX_LISTING_DEPTH = 2

# So truong thong so toi thieu de coi mot trang la trang san pham. Do tren 13
# fixture + 5 trang that: san pham 5-10 truong, danh muc/landing 1-4 (xem
# `detection._SPEC_FIELD_RES`).
MIN_SPEC_FIELDS = 5

# Duong dan co NGAY THANG trong no: quy uoc permalink mac dinh cua WordPress
# cho bai viet (`/2022/08/05/<slug>/`). Khong san pham nao duoc dat URL theo
# ngay xuat ban, nen day la mot cach loai bai blog ma khong ton luot fetch.
# Do tren VNE: 5 bai viet ve den LED liet ke du truong thong so nen cham dat
# nhu trang san pham - dau hieu duy nhat con lai de phan biet la duong dan.
_DATE_IN_PATH_RE = re.compile(r"/(?:19|20)\d{2}/\d{1,2}(?:/\d{1,2})?/")

# Duoi file KHONG phai trang HTML. Trang san pham hay lightbox anh: the <a> boc
# <img> tro thang toi file anh. Do tren Roman: 122 ung vien la `/pic/Product/
# *.jpg` va `*.png` - moi cai ton mot luot fetch de ket luan dieu da biet truoc
# tu duoi file, va chinh 122 luot do lam luot do cham tran 400 trang.
_NON_HTML_SUFFIXES = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".7z", ".mp4", ".mp3", ".avi", ".dwg", ".ies",
)

# So the anh toi thieu de tin rang trang nay dung the anh cho san pham. Duoi
# muc do thi chuyen sang dau hieu "link lap lai cung hinh dang" (xem PHA B).
CARD_LINK_MIN = 6

# So lan mot hinh dang phai lap lai tren MOT trang de duoc coi la mot khoi san
# pham. Do: VNE lap 100 lan; menu/footer moi link mot hinh dang.
REPEATED_SHAPE_MIN = 6

# So URL lay mau cho MOT hinh dang: 5, hoac 10% nhom neu nhom lon, toi da 20.
#
# Co dinh 5 la KHONG DU, do duoc tren Roman: nhom `/*.html` co 94 ung vien vua
# san pham vua danh muc, 5 URL dau tinh co deu la san pham -> cham 5/5 -> nhan
# ca nhom, keo theo `bo-den-tuyp-led.html` va 12 trang danh muc khac vao danh
# sach san pham. Mau cang lon thi nhom LAN LON cang kho gia trang thuan.
SHAPE_SAMPLE_MIN = 5
SHAPE_SAMPLE_MAX = 20
SHAPE_SAMPLE_FRACTION = 0.1

# Tren nguong tren: nhan ca nhom. Duoi nguong duoi: loai ca nhom. O giua: nhom
# LAN LON (case Roman URL phang) -> kiem tung URL. Hai nguong dat lech han nhau
# de "o giua" la mot vung that su rong, vi doan bua o vung do chinh la cach
# trang rac lot vao dataset.
SHAPE_ACCEPT_RATIO = 0.8
SHAPE_REJECT_RATIO = 0.2


@dataclass
class ShapeVerdict:
    """Ket luan cho mot hinh dang URL - de doc lai duoc vi sao mot nhom bi loai."""

    shape: str
    candidates: int
    sampled: int
    hits: int
    decision: str  # "nhan-ca-nhom" | "loai-ca-nhom" | "kiem-tung-url"
    accepted: int


@dataclass
class DiscoveryReport:
    product_urls: list[str] = field(default_factory=list)
    listing_urls: list[str] = field(default_factory=list)
    flagged_urls: list[str] = field(default_factory=list)
    pages_fetched: int = 0
    budget_exhausted: bool = False
    shapes: list[ShapeVerdict] = field(default_factory=list)


def url_shape(url: str) -> str:
    """Hinh dang cua mot URL: duong dan voi doan CUOI thay bang `*`.

    Doan cuoi la danh tinh cua tung trang; phan con lai moi la thu chung cua ca
    nhom. Giu lai duoi file (`.html`) va TEN cac tham so truy van (khong giu
    gia tri) vi ca hai deu la dau hieu phan loai that:

        /index.php/product/den-x/  -> /index.php/product/*
        /den-op-tran-elt7128.html  -> /*.html
        /products/plist.php?lay3=A -> /products/*.php?lay3
    """
    parsed = urlparse(url)
    segments = [s for s in parsed.path.split("/") if s]
    last = segments[-1] if segments else ""
    prefix = "/".join(segments[:-1])
    suffix = f".{last.rsplit('.', 1)[1]}" if "." in last else ""
    keys = sorted({k for k, _ in parse_qsl(parsed.query)})
    query = f"?{','.join(keys)}" if keys else ""
    return f"/{prefix}/*{suffix}{query}" if prefix else f"/*{suffix}{query}"


def card_links(html: str, page_url: str) -> list[str]:
    """Link BOC ANH cung domain - the san pham tren mot trang luoi.

    Cung tieu chi ma `detection.analyze_page` dung de dem `card_link_count`, nen
    trang duoc cham la "luoi san pham" va tap ung vien lay ra tu no la MOT phep
    do, khong phai hai heuristic roi nhau.
    """
    soup = BeautifulSoup(html, "lxml")
    domain = urlparse(page_url).netloc

    out: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        if not a.find("img"):
            continue
        href = a["href"].strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        absolute = urljoin(page_url, href).split("#", 1)[0]
        if urlparse(absolute).netloc != domain:
            continue
        if absolute not in seen:
            seen.add(absolute)
            out.append(absolute)
    return out


def _non_dominant_links(links: list[str]) -> list[str]:
    """Link co hinh dang KHAC hinh dang chiem da so trong danh sach."""
    if not links:
        return []
    counts: dict[str, int] = {}
    for link in links:
        counts[url_shape(link)] = counts.get(url_shape(link), 0) + 1
    dominant = max(counts, key=lambda shape: counts[shape])
    return [link for link in links if url_shape(link) != dominant]


def _skip(url: str) -> bool:
    """URL biet truoc la khong phai trang san pham, khong ton luot fetch de kiem."""
    path = urlparse(url).path.lower()
    return bool(_DATE_IN_PATH_RE.search(path)) or path.endswith(_NON_HTML_SUFFIXES)


def _sample(shape: str, urls: list[str]) -> list[str]:
    """Mau NGAU NHIEN tren ca nhom, gieo hat theo chinh hinh dang URL.

    Khong lay N URL dau: thu tu ung vien la thu tu xuat hien tren trang luoi,
    nen mau bi don vao mot goc cua nhom - dung chinh cho da lam nhom `/*.html`
    cua Roman cham 5/5 trong khi nhom do lan 13 trang danh muc.

    Cung khong lay theo buoc nhay deu: buoc deu tren mot nhom xen ke deu se roi
    het vao mot phia (do duoc trong test), tuc van la mot goc, chi kin dao hon.
    Gieo hat theo `shape` giu ket qua LAP LAI DUOC giua cac lan chay - cung mot
    site cho cung mot ket luan, khong phai hen xui theo tung luot.
    """
    size = min(SHAPE_SAMPLE_MAX, max(SHAPE_SAMPLE_MIN, int(len(urls) * SHAPE_SAMPLE_FRACTION)))
    if len(urls) <= size:
        return list(urls)
    return random.Random(shape).sample(urls, size)


def repeated_shape_links(html: str, page_url: str) -> list[str]:
    """Link noi bo co hinh dang LAP LAI nhieu lan tren cung mot trang."""
    domain = urlparse(page_url).netloc
    internal = [
        link
        for link in page_links(html, page_url)
        if urlparse(link).netloc == domain and link.rstrip("/") != page_url.rstrip("/")
    ]
    counts: dict[str, int] = {}
    for link in internal:
        counts[url_shape(link)] = counts.get(url_shape(link), 0) + 1

    out: list[str] = []
    seen: set[str] = set()
    for link in internal:
        if counts[url_shape(link)] >= REPEATED_SHAPE_MIN and link not in seen:
            seen.add(link)
            out.append(link)
    return out


def _candidate_links(html: str, page_url: str) -> list[str]:
    """The anh neu trang co du the anh, khong thi link lap lai (xem PHA B)."""
    cards = card_links(html, page_url)
    if len(cards) >= CARD_LINK_MIN:
        return cards
    return cards + repeated_shape_links(html, page_url)


class _Budget:
    """Bo dem so trang da fetch, dung chung cho ca ba pha."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.used = 0

    @property
    def exhausted(self) -> bool:
        return self.used >= self.limit


def _co_the_la_san_pham(url: str, pattern: Optional[str]) -> bool:
    """Site chua khai `product_url_pattern` -> khong loai gi (True cho moi URL).
    Khai roi -> URL khong chua chuoi do khong the la trang san pham."""
    return not pattern or pattern in url


def _is_product_page(signals) -> bool:
    """San pham o nhanh khong-sitemap: trang liet ke du nhieu TRUONG THONG SO.

    `looks_like_single_product_page` mot minh KHONG dung duoc o day. No hoi "co
    gia hay structured data khong" - o Roman thi trang danh muc cung co gia
    (`aptomat.html`: 12 so tien), con o VNE thi trang san pham lai ghi "Liên hệ"
    nen khong co gia nao. Cong thuc do van giu nguyen cho viec cham diem
    sitemap, chi la khong dung o nhanh nay.

    Bon tin hieu khac da do va loai, ghi lai o `detection._SPEC_FIELD_RES`.
    Nguong 5 truong tach dung ca hai site: Roman san pham 7-8 / danh muc 1-4,
    VNE san pham 7 / danh muc 4.

    KHONG them dieu kien "khong phai trang luoi": `tlc_product.html` la trang
    san pham that nhung co 30+ the anh (bang san pham lien quan) nen bi cham la
    trang luoi - dieu kien do se vut chinh no.
    """
    return signals.spec_field_count >= MIN_SPEC_FIELDS


def _fetch(fetcher, url: str, options: dict, budget: _Budget) -> Optional[str]:
    if budget.exhausted:
        return None
    budget.used += 1
    result = fetcher.fetch(url, **options)
    if not getattr(result, "ok", False):
        return None
    return getattr(result, "html", "") or None


def discover_product_urls(
    base_url: str,
    fetcher,
    *,
    seed_urls: Iterable[str] = (),
    page_budget: int = DEFAULT_PAGE_BUDGET,
    listing_fetch_options: Optional[dict] = None,
    product_fetch_options: Optional[dict] = None,
    product_url_pattern: Optional[str] = None,
) -> DiscoveryReport:
    """URL san pham cua mot domain khong co sitemap dung duoc. Xem docstring module.

    `product_url_pattern` (tu `SiteProfile`) la mot cau khang dinh cua site:
    URL san pham chua chuoi nay. Truoc day no chi duoc dung SAU khi do xong, de
    loc danh sach cuoi. Dung ngay trong luc do thi manh hon nhieu: trang khong
    khop KHONG THE la san pham, nen thay vi dung lai o do, tang do di tiep qua
    no nhu mot tram trung chuyen.

    Do tren panasonic.net: 32 trang danh muc `plist.php?lay3=` deu liet ke san
    pham kem thong so nen dat nguong 5 truong va bi cham la SAN PHAM. Tang do
    dung ngay tai chung, khong bao gio xuong toi `pspec.php?id=` - ca site tra
    ve 33 URL ma sau khi loc theo pattern thi con 0.
    """
    domain = urlparse(base_url).netloc
    listing_options = listing_fetch_options or {}
    product_options = product_fetch_options or {}
    budget = _Budget(page_budget)
    report = DiscoveryReport()

    # Ket qua phan loai cua MOI trang da fetch, khoa da bo dau `/` cuoi. Vua de
    # khong fetch lai, vua de pha C khong phai cham diem lai trang da biet.
    classified: dict[str, bool] = {}
    products: dict[str, str] = {}  # khoa so trung -> URL nguyen van
    # Moi URL da thay trong menu dieu huong cua BAT KY trang nao da fetch. Thu
    # nay chi de LOAI ung vien (pha B2), khong dung de di tiep.
    nav_urls: set[str] = set()
    candidates: dict[str, None] = {}  # dict thay set: giu thu tu gap tren trang

    # Cua vao khai san (`SiteProfile.listing_seed_urls`) va trang chu deu la
    # CHANG 0: chung la diem xuat phat ngang hang, khong phai mot chang da di.
    queue: deque[tuple[str, int]] = deque([(base_url, 0)])
    for url in seed_urls:
        queue.append((url, 0))

    # PHA A + B: di tim trang luoi, thu the san pham tren do.
    while queue and not budget.exhausted:
        url, depth = queue.popleft()
        key = url.rstrip("/")
        if key in classified or urlparse(url).netloc != domain or _skip(url):
            continue

        html = _fetch(fetcher, url, listing_options, budget)
        if html is None:
            continue

        signals = analyze_page(html)
        classified[key] = _co_the_la_san_pham(url, product_url_pattern) and _is_product_page(signals)
        page_nav = nav_links(html, url)
        # Loai thi phai dung menu THAT (`require_container`): trang khong co the
        # menu nao ma van lay ca trang lam menu thi moi ung vien deu bi vut.
        nav_urls.update(
            link.rstrip("/") for link in nav_links(html, url, require_container=True)
        )

        # The anh cua MOI trang deu la ung vien, khong rieng trang duoc cham la
        # "luoi san pham". Nguong `CARD_LINK_THRESHOLD` (30 the) duoc hieu
        # chinh tren Roman - site lon, luoi that do duoc 52 the - va no qua cao
        # cho site nho: do tren VNE, KHONG trang nao dat 30 the nen truoc thay
        # doi nay ca site cho ra 0 ung vien. Viec cham "co phai luoi khong" gio
        # chi con quyet dinh CO PHAN TRANG TIEP HAY KHONG; con URL nao la san
        # pham thi pha C xac nhan bang cach do that tren tung trang.
        for link in _candidate_links(html, url):
            candidates.setdefault(link)

        if signals.looks_like_product_listing:
            report.listing_urls.append(url)
            # Trang con cua phan trang la CUNG mot danh muc, khong tinh la mot
            # chang moi - neu tinh thi danh muc nao qua 2 trang se bi cat cut.
            for nxt in sorted(pagination_candidates(page_links(html, url), url)):
                if nxt.rstrip("/") not in classified:
                    queue.append((nxt, depth))
            # Di tiep xuong DANH MUC CON. Cay danh muc sau hon mot tang thi
            # truoc day khong toi duoc: do tren Nanoco, tu mot cua vao chi ra
            # 17 san pham vi cac danh muc con cua no khong bao gio duoc mo.
            #
            # Chi di theo link co hinh dang KHAC hinh dang chiem da so tren
            # chinh trang nay. Hinh dang chiem da so la cac the san pham
            # (Nanoco: 30 link `/default/san-pham/*`), va di theo chung thi
            # tang 0 fetch het moi san pham - dung thu ma phep lay mau theo
            # nhom o pha C sinh ra de tranh. Phan con lai
            # (`/default/danh-muc/*`: 8 link) moi la danh muc con.
            #
            # Gia dinh "hinh dang chiem da so = the san pham" DUNG voi Nanoco
            # nhung LON NGUOC o panasonic.net: tren `wlist.php`, hinh dang
            # chiem da so chinh la 32 link DANH MUC `plist.php?lay3=`. Bo qua
            # chung thi khong bao gio toi duoc `pspec.php?id=` - ca site tra ve
            # 0 URL. Khi site da khai `product_url_pattern`, link khong khop
            # KHONG THE la san pham, nen no chac chan la mot tram trung chuyen
            # va phai di tiep bat ke hinh dang co chiem da so hay khong.
            if depth < MAX_LISTING_DEPTH:
                cands = _candidate_links(html, url)
                di_tiep = list(_non_dominant_links(cands))
                if product_url_pattern:
                    da_co = {u.rstrip("/") for u in di_tiep}
                    di_tiep += [
                        u for u in cands
                        if not _co_the_la_san_pham(u, product_url_pattern)
                        and u.rstrip("/") not in da_co
                    ]
                for nxt in di_tiep:
                    if nxt.rstrip("/") not in classified:
                        queue.append((nxt, depth + 1))
            continue

        if classified[key]:
            # Gap san pham ngay tren duong di (menu tro thang vao 1 san pham -
            # do duoc o Roman). KHONG nhan luon: no van phai qua ket luan theo
            # nhom o pha C, neu khong thi mot trang le cham dat se lot qua ca
            # ket luan "loai ca nhom" cua chinh nhom no. Da fetch roi nen buoc
            # xac nhan o pha C khong ton them luot fetch nao.
            candidates.setdefault(url)
            continue

        report.flagged_urls.append(url)
        if depth < MAX_LISTING_DEPTH:
            for link in page_nav + card_links(html, url):
                if link.rstrip("/") not in classified:
                    queue.append((link, depth + 1))

    if budget.exhausted:
        report.budget_exhausted = True
        logger.warning(
            "Cham tran %d trang khi do %s - danh sach san pham co the chua day du",
            page_budget, domain,
        )

    # PHA C: xac nhan ung vien theo hinh dang URL.
    by_shape: dict[str, list[str]] = {}
    for url in candidates:
        key = url.rstrip("/")
        if key in nav_urls:
            # Nam trong menu -> la danh muc, khong phai san pham (pha B2).
            continue
        if _skip(url):
            continue
        by_shape.setdefault(url_shape(url), []).append(url)

    for shape, urls in sorted(by_shape.items()):
        sample = _sample(shape, urls)
        hits = [
            u for u in sample
            if _is_product(fetcher, u, product_options, budget, classified, product_url_pattern)
        ]
        ratio = len(hits) / len(sample) if sample else 0.0

        if ratio >= SHAPE_ACCEPT_RATIO:
            decision = "nhan-ca-nhom"
            accepted = urls
        elif ratio <= SHAPE_REJECT_RATIO:
            # Loai CA nhom, ke ca nhung URL trong mau vua cham dat. Ket luan cua
            # ca nhom la bang chung manh hon mot lan cham le: do tren VNE, nhom
            # bai blog `/index.php/2022/08/05/*` cham 1/5 - dung mot bai viet ve
            # den LED liet ke du truong thong so. Giu lai "hit" do la de mot bai
            # blog thanh mot ban ghi san pham.
            decision = "loai-ca-nhom"
            accepted = []
        else:
            decision = "kiem-tung-url"
            rest = [u for u in urls if u not in set(sample)]
            accepted = hits + [
                u for u in rest
                if _is_product(
                    fetcher, u, product_options, budget, classified, product_url_pattern
                )
            ]

        for url in accepted:
            products.setdefault(url.rstrip("/"), url)
        report.shapes.append(
            ShapeVerdict(shape, len(urls), len(sample), len(hits), decision, len(accepted))
        )
        logger.info(
            "Hinh dang %s: %d ung vien, mau %d/%d la san pham -> %s (%d URL)",
            shape, len(urls), len(hits), len(sample), decision, len(accepted),
        )

    if budget.exhausted:
        report.budget_exhausted = True
    report.pages_fetched = budget.used
    report.product_urls = sorted(products.values())
    return report


def _is_product(
    fetcher, url: str, options: dict, budget: _Budget, classified: dict,
    product_url_pattern: Optional[str] = None,
) -> bool:
    key = url.rstrip("/")
    if key in classified:
        return classified[key]
    if budget.exhausted:
        # Het tran KHONG phai la "khong phai san pham" - dung ghi vao
        # `classified`, neu khong mot lan cham tran se dong bang thanh ket luan
        # sai cho phan con lai cua luot do. `budget_exhausted` trong bao cao la
        # cho de doc ra rang danh sach chua day du.
        return False
    html = _fetch(fetcher, url, options, budget)
    classified[key] = (
        bool(html)
        and _co_the_la_san_pham(url, product_url_pattern)
        and _is_product_page(analyze_page(html))
    )
    return classified[key]


__all__ = [
    "DEFAULT_PAGE_BUDGET",
    "MAX_LISTING_DEPTH",
    "DiscoveryReport",
    "ShapeVerdict",
    "card_links",
    "discover_product_urls",
    "url_shape",
]
