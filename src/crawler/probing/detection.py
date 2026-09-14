"""Bo phat hien "trang/URL san pham that" dung chung. Task 4.3.

Dung o 2 cho (theo specs/site-probing/spec.md):
(a) xac nhan trang danh muc ung vien khi crawl menu/breadcrumb du phong
(b) lay mau xac nhan URL khi cham diem do tin cay sitemap

Nguong CARD_LINK_THRESHOLD duoc chon dua tren du lieu thuc te da khao sat tren
Roman.vn (xem design.md): trang landing "bay" den-led-am-tran.html chi co 17
the <a> boc <img> (anh banner), trong khi trang luoi that den-downlight-led.html
co 52 - ca hai deu co pagination/structured-data gan giong nhau nen KHONG dung
duoc lam tin hieu phan biet chinh (Roman gan nham 1 JSON-LD kieu "Product" len
ca trang landing, va trang luoi that lai khong co structured data nao ca).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

# Nguong thuc nghiem: xem docstring o tren. Da thu ha nguong xuong ket hop voi
# has_pagination nhung ca 2 trang deu co pagination control nen khong tach
# duoc - phai dung rieng card_link_count lam tieu chi chinh.
CARD_LINK_THRESHOLD = 30

# Phai bat SO TIEN THAT, khong phai chu "giá". Chu "giá" xuat hien o menu/footer
# cua gan nhu moi trang tieng Viet (do banner "Bảng giá", "Giá tốt"...) nen dem
# chu "giá" khong tach duoc trang san pham khoi bai blog - chinh la loi da gap o
# TLC: sitemap_index.xml gom ca post-sitemap.xml (733 bai blog) van duoc cham
# 100% do tin cay. Do thuc te tren fixture that (xem docstring lop PageSignals).
#
# Khop tren TEXT da trich (khong phai HTML tho): WooCommerce tach chu so va ky
# hieu tien te ra 2 the khac nhau (`<bdi>166.000<span>₫</span></bdi>`) nen regex
# chay tren HTML tho se dem ra 0 cho chinh trang san pham TLC.
_PRICE_AMOUNT_RE = re.compile(
    r"\d[\d.,]*\s*(?:vnđ|vnd|đồng|₫|đ)(?![A-Za-zÀ-ỹ])", re.I
)
# TEN CAC TRUONG THONG SO cua mot bo den. Trang san pham liet ke nhieu truong;
# trang danh muc / landing thi khong.
#
# Day la thu duy nhat tach duoc hai loai o nhanh khong-sitemap, sau khi da do
# va LOAI bon ung cu vien khac tren trang that:
#   - gia:        Roman in gia len tung the hang o trang danh muc (aptomat.html
#                 do duoc 12 so tien), con san pham VNE lai ghi "Liên hệ" -> 0.
#   - so the anh: san pham Roman co bang "san pham lien quan" nen do duoc 26-37
#                 the, xap xi trang danh muc.
#   - og:type:    Roman de `article` cho MOI trang.
#   - so trang tro toi: do duoc danh muc 1-2, san pham 1 - trung nhau.
#   - tieu de "Thông số kỹ thuật": san pham VNE co bang thong so nhung KHONG co
#                 dong tieu de nao.
#
# Do tren 13 fixture that + 5 trang that (Roman, VNE): trang san pham dat 5-10
# truong, trang danh muc / landing dat 1-4.
#
# Moi truong mang them BAN TIENG ANH. Ly do do duoc: panasonic.net ban tieng
# Viet van ghi bang thong so bang tieng Anh ("Power Input | 75W", "System Lumen
# Output | 10710 lm", "Lifetime | 50000H") - regex tieng Viet chi khop 1/11
# truong nen tang do coi MOI trang san pham Panasonic la khong phai san pham,
# va ca site tra ve 0 URL sau khi fetch 107 trang.
#
# Cac ban tieng Anh deu la cum HAI TU dac thu bang thong so ("power input",
# "beam angle", "lamp base"), khong phai tu don pho thong - de trang danh muc
# khong vo tinh dat nguong chi vi noi ve den.
_SPEC_FIELD_RES = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"c[ôo]ng su[âấ]t|power input|wattage",
        r"quang th[ôo]ng|lumen output|luminous flux",
        r"[đd]i[eệ]n [áa]p|power voltage",
        r"nhi[eệ]t [đd][ộo] m[àa]u|\bcct\b|colou?r temperature",
        r"ho[àa]n m[àa]u|cri",
        r"tu[ổo]i th[ọo]|lifetime|life ?span",
        r"ch[ỉi] s[ốo] ip|ip\d\d|ip code",
        r"k[íi]ch th[ưu][ớơ]c|dimensions",
        r"b[ảa]o h[àa]nh|warranty",
        r"đui|lamp base",
        r"g[óo]c chi[ếe]u|beam angle",
    )
)

_PRODUCT_JSONLD_RE = re.compile(r'"@type"\s*:\s*"Product"')
_PRODUCT_MICRODATA_RE = re.compile(r'itemtype=["\']https?://schema\.org/Product["\']', re.I)
_PAGINATION_RE = re.compile(
    r'(class=["\'][^"\']*pag(e|ination)[^"\']*["\']|rel=["\']next["\']|[?&]page=\d+|/page/\d+|/paged/\d+)',
    re.I,
)


@dataclass
class PageSignals:
    price_amount_mentions: int
    product_structured_data_count: int
    card_link_count: int
    has_pagination: bool
    spec_field_count: int = 0

    @property
    def looks_like_single_product_page(self) -> bool:
        """Dung khi xac nhan 1 URL rieng le (vd mau tu sitemap) co phai trang
        san pham that hay khong.

        Nguong dua tren do thuc te tren 5 fixture that (3 trang san pham + 2
        "rac" that lay tu chinh sitemap cua TLC), dem tren text da trich:

            fixture                 so_tien  structured_data  la san pham?
            tlc_product.html              0                1  co
            kingled_product.html         34                8  co
            roman_product.html            9                0  co
            tlc_blog_post.html            0                0  KHONG
            tlc_static_page.html          0                0  KHONG

        `structured_data >= 1 or so_tien >= 1` tach dung ca 5 truong hop.

        LUU Y da thu va LOAI marker "Liên hệ" khoi cong thuc nay: no xuat hien
        o footer/menu cua MOI trang TLC (bai blog dem duoc 5, trang tinh 4) nen
        them vao se lam ca 2 fixture "rac" pass tro lai. Doi lai, 1 trang san
        pham vua khong co structured data vua ghi gia la "Liên hệ" se bi cham
        truot - chap nhan duoc vi day chi la buoc LAY MAU danh gia sitemap
        (nguong 80%, khong doi 100%), khong phai buoc quyet dinh gia tri Gia
        cua tung ban ghi (viec do thuoc record/price.py, van giu du 3 trang thai).
        """
        return self.product_structured_data_count >= 1 or self.price_amount_mentions >= 1

    @property
    def looks_like_product_listing(self) -> bool:
        """Dung khi phan loai 1 trang danh muc ung vien la luoi san pham that
        hay landing/noi dung rong (case Roman: trang landing co rat it the
        anh+link lap lai so voi trang luoi that). has_pagination/structured-data
        KHONG dung de ha nguong vi thuc te ca trang landing lan trang luoi that
        deu co the co ca 2 tin hieu nay (Roman gan nham JSON-LD Product len
        trang landing, va ca 2 deu co control phan trang trong menu chung)."""
        return self.card_link_count >= CARD_LINK_THRESHOLD


def analyze_page(html: str) -> PageSignals:
    soup = BeautifulSoup(html, "lxml")
    card_hrefs = {a["href"] for a in soup.find_all("a", href=True) if a.find("img")}
    text = soup.get_text(" ", strip=True)

    return PageSignals(
        price_amount_mentions=len(_PRICE_AMOUNT_RE.findall(text)),
        product_structured_data_count=(
            len(_PRODUCT_JSONLD_RE.findall(html)) + len(_PRODUCT_MICRODATA_RE.findall(html))
        ),
        card_link_count=len(card_hrefs),
        has_pagination=bool(_PAGINATION_RE.search(html)),
        spec_field_count=sum(1 for rx in _SPEC_FIELD_RES if rx.search(text)),
    )


def is_real_product_page(html: str) -> bool:
    return analyze_page(html).looks_like_single_product_page


def is_real_product_listing(html: str) -> bool:
    return analyze_page(html).looks_like_product_listing
