"""Mot o tim kiem -> mot pham vi crawl. Capability `crawl-scope-search`.

Day la thu THAY THE cho mot cay nganh hang chuan hoa. Quyet dinh do ghi day du
o design.md muc 1; tom tat ly do de khong ai dung lai bang anh xa:

    Anh xa nganh hang KHONG di vao file ket qua - cot `category 1/2/3` giu
    nguyen van cua site nguon. No chi dung de CHON crawl cai gi. Nen anh xa sai
    chi lam crawl thua (gan nhu mien phi o lan chay sau) hoac crawl thieu (thay
    duoc ngay tren man xac nhan), va gia sua la go lai tu khoa. Dung mot quy
    trinh curation co vet audit de chong mot loi gia do la sai co cong cu.

Nguyen tac rut ra, dang giu cho cac quyet dinh sau: DUNG BIEN DU LIEU DAN XUAT
THANH DU LIEU CHU QUAN.

Khong goi LLM o tang nay. Ket qua phai tat dinh va giai thich duoc ("tu khoa
nay khop vao 3 danh muc sau"), va phai tra loi tuc thi.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional

from .sites.registry import SITE_PROFILES


class ScopeKind(str, Enum):
    BRAND = "brand"
    CATEGORY = "category"
    PRODUCT_NAME = "product_name"
    NONE = "none"


# Thu tu uu tien khi mot tu khoa khop nhieu loai. CO DINH va dinh truoc, vi
# ket qua phai on dinh giua cac lan go cung mot tu khoa.
#
# Nhan hieu truoc danh muc: tap nhan hieu nho (vai chuc) va la ten rieng, nen
# mot cu khop vao do gan nhu chac chan la co y. Ten danh muc thi dai va nhieu
# tu chung ("den", "led"), de khop tinh co hon.
#
# Nguoi dung KHONG bi ket vao lua chon nay: ket qua luon mang theo `alternatives`
# de giao dien cho chuyen loai ma khong phai go lai (task 3.4).
PRIORITY: tuple[ScopeKind, ...] = (ScopeKind.BRAND, ScopeKind.CATEGORY, ScopeKind.PRODUCT_NAME)


def normalise(text: Optional[str]) -> str:
    """Bo dau tieng Viet, ve chu thuong, gom khoang trang.

    Ly do bat buoc, lay tu du lieu that: cung mot loai san pham duoc cac doi thu
    viet la `ĐÈN DOWNLIGHT ÂM TRẦN`, `Đèn LED âm trần`, `Đèn LED âm trần khối
    đúc`. Bat nguoi dung go dung dau va dung kieu hoa thuong la bat ho doan xem
    doi thu go the nao.

    Dung NFD roi bo dau ket hop: chu `đ`/`Đ` KHONG tach ra bang cach nay (no la
    mot ky tu rieng, khong phai `d` + dau) nen phai thay tay - thieu buoc do thi
    `den` khong bao gio khop `đèn`, tuc hong dung tu pho bien nhat.
    """
    if not text:
        return ""
    lowered = text.lower().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", lowered)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.split())


@dataclass
class CategoryMatch:
    domain: str
    category_url: str
    category_name: Optional[str]


@dataclass
class Scope:
    """Pham vi suy ra tu mot tu khoa.

    `kind == NONE` mang `reason` noi ro vi sao khong khop - de giao dien noi
    duoc mot cau that thay vi hien mot bang rong (task 3.5).
    """

    keyword: str
    kind: ScopeKind
    domains: list[str] = field(default_factory=list)
    categories: list[CategoryMatch] = field(default_factory=list)
    # Cac loai KHAC ma tu khoa nay cung khop. Giao dien dung de cho chuyen loai
    # mà khong phai go lai tu khoa.
    alternatives: list[ScopeKind] = field(default_factory=list)
    reason: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        return self.kind is ScopeKind.NONE


def _brand_keys(domain: str, profile) -> list[str]:
    """Moi cach goi cua mot domain, da chuan hoa: ten nhan, cac bi danh, va
    chinh domain (nguoi dung hay dan URL vao o tim kiem)."""
    keys = [domain, domain.split(".")[0]]
    if profile.brand_name:
        keys.append(profile.brand_name)
    keys.extend(profile.brand_aliases)
    return [normalise(k) for k in keys if k]


def match_brands(keyword: str) -> list[str]:
    """Domain co ten/bi danh khop tu khoa."""
    needle = normalise(keyword)
    if not needle:
        return []
    hits = []
    for domain, profile in SITE_PROFILES.items():
        keys = _brand_keys(domain, profile)
        # Khop hai chieu: go "kingled" phai ra "kingled.com.vn" (khoa chua tu
        # khoa), va go "kingled.com.vn" phai ra ca khi nhan ten la "KingLED"
        # (tu khoa chua khoa).
        if any(needle in key or key in needle for key in keys):
            hits.append(domain)
    return sorted(hits)


def matches_all_tokens(keyword: str, haystack: Optional[str]) -> bool:
    """MOI tu cua tu khoa deu co mat trong chuoi dich (khong can lien nhau).

    So chuoi con thang thi qua chat cho truy van nhieu tu, va truot ngay tren
    cap pho bien nhat cua chinh du lieu nay:

        go     "den am tran"
        ten    "Đèn LED âm trần"  -> chuan hoa "den led am tran"
        chuoi con: TRUOT vi chu "led" chen vao giua.

    Doi sang "moi tu deu xuat hien" thi cap tren khop, va `downlight` van khop
    dung mot minh `ĐÈN DOWNLIGHT ÂM TRẦN`. Doi lai, thu tu tu bi bo qua - chap
    nhan duoc: ten danh muc cua doi thu khong co thu tu chuan nao ("Đèn LED âm
    trần khối đúc" vs "Đèn LED khối đúc âm trần" deu la cach ho co the viet).
    """
    target = normalise(haystack)
    if not target:
        return False
    return all(token in target for token in normalise(keyword).split())


def match_categories(
    keyword: str, categories: Iterable[tuple[str, str, Optional[str]]]
) -> list[CategoryMatch]:
    """Danh muc co ten khop tu khoa.

    `categories` la (domain, url, ten) - lay tu `CategoryStore.category_names()`.
    Khop tren TEN danh muc do chinh site dat, khong tren mot cay chuan hoa nao.
    """
    if not normalise(keyword):
        return []
    return [
        CategoryMatch(domain=domain, category_url=url, category_name=name)
        for domain, url, name in categories
        if matches_all_tokens(keyword, name or url)
    ]


def classify(
    keyword: str,
    categories: Iterable[tuple[str, str, Optional[str]]] = (),
    *,
    prefer: Optional[ScopeKind] = None,
) -> Scope:
    """Tu khoa -> pham vi, theo thu tu uu tien `PRIORITY`.

    `prefer` cho ben goi ep mot loai cu the - duong ma giao dien dung khi nguoi
    dung chuyen loai, de khong phai go lai tu khoa (task 3.4).

    Khong khop nhan hieu lan danh muc thi coi la TEN SAN PHAM: do la nhanh mac
    dinh chu khong phai nhanh that bai. Chi khi ca ba deu khong ra gi moi tra
    ve `NONE` kem ly do.
    """
    keyword = (keyword or "").strip()
    categories = list(categories)
    if not normalise(keyword):
        return Scope(
            keyword=keyword, kind=ScopeKind.NONE,
            reason="Chưa nhập từ khoá nào.",
        )

    brands = match_brands(keyword)
    matched_categories = match_categories(keyword, categories)

    found: dict[ScopeKind, Scope] = {}
    if brands:
        found[ScopeKind.BRAND] = Scope(keyword=keyword, kind=ScopeKind.BRAND, domains=brands)
    if matched_categories:
        found[ScopeKind.CATEGORY] = Scope(
            keyword=keyword,
            kind=ScopeKind.CATEGORY,
            domains=sorted({c.domain for c in matched_categories}),
            categories=matched_categories,
        )

    if prefer is not None and prefer in found:
        chosen = found[prefer]
        chosen.alternatives = [k for k in PRIORITY if k in found and k is not prefer]
        return chosen

    for kind in PRIORITY:
        if kind in found:
            chosen = found[kind]
            chosen.alternatives = [k for k in PRIORITY if k in found and k is not kind]
            return chosen

    # Khong khop tap dong nao -> tim tren ten san pham trong kho.
    return Scope(keyword=keyword, kind=ScopeKind.PRODUCT_NAME)


__all__ = [
    "CategoryMatch",
    "PRIORITY",
    "Scope",
    "ScopeKind",
    "classify",
    "match_brands",
    "match_categories",
    "matches_all_tokens",
    "normalise",
]
