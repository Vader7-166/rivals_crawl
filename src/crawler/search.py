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

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Iterable, Mapping, Optional

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


# Nho ket qua: cung mot ten danh muc / ten san pham bi chuan hoa lai sau MOI
# phim nguoi dung go, va NFD decompose la phan dat nhat cua ca duong goi y. Do
# tren kho that (5.000 ten san pham, o goi y giu cache du lieu): 55-489ms moi
# lan go xuong con duoi 10ms. Ham thuan tuy nen nho ket qua la an toan tuyet
# doi; maxsize du cho toan bo kho hien tai va tu thai cai cu neu kho lon hon.
@lru_cache(maxsize=32768)
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


_WORD_SPLIT = re.compile(r"[^a-z0-9]+")


@lru_cache(maxsize=32768)
def _tokens_cached(text: Optional[str]) -> tuple[str, ...]:
    return tuple(t for t in _WORD_SPLIT.split(normalise(text)) if t)


def tokens(text: Optional[str]) -> list[str]:
    """Chuoi da chuan hoa -> danh sach tu. Tach tren MOI ky tu khong phai chu
    so/chu cai, nen `kingled.com.vn` va `vne-led` deu tach ra dung don vi.

    Tra ve list moi moi lan de ben goi khong sua nham vao ban da nho.
    """
    return list(_tokens_cached(text))


# Tu qua chung de MOT MINH no dinh danh duoc mot nhan hieu. Do that tren chinh
# tap nhan hieu dang co: `led` la chuoi con cua `kingled`, `denvinaled` va
# `vne-led`; `den` la chuoi con cua `denvinaled` va `denasia`.
#
# Khong co danh sach nay thi tu pho bien nhat cua ca nganh - `led` - bi phan
# loai thanh NHAN HIEU va nuot mat toan bo nhanh danh muc, vi nhan hieu duoc
# uu tien truoc (do tren kho: `led` -> [denvinaled.vn, kingled.com.vn], trong
# khi co 254 ten danh muc thi phan lon chua chu do).
#
# Chi chan khi TOAN BO tu khoa la tu chung: `vne led` van ra nhan hieu VNE, vi
# `vne` khong nam trong danh sach.
BRAND_STOPWORDS: frozenset[str] = frozenset(
    {"den", "led", "lighting", "group", "vietnam", "viet", "nam", "www", "com", "vn", "net"}
)


def _is_subsequence(haystack: list[str], needle: list[str]) -> bool:
    """`needle` xuat hien lien tiep trong `haystack` (so tung TU, khong phai
    tung ky tu)."""
    if not needle or len(needle) > len(haystack):
        return False
    return any(
        haystack[i : i + len(needle)] == needle for i in range(len(haystack) - len(needle) + 1)
    )


def match_brands(keyword: str) -> list[str]:
    """Domain co ten/bi danh khop tu khoa.

    Khop theo RANH GIOI TU, khong phai chuoi con: `led` khong duoc khop
    `kingled`, nhung `king led` van khop nho bi danh "King LED". Ban dau day la
    chuoi con hai chieu va no cho ra ket qua sai tren tu khoa pho bien nhat -
    xem `BRAND_STOPWORDS`.

    Van giu HAI CHIEU: go "kingled" phai ra `kingled.com.vn` (khoa chua tu
    khoa), va go "den philips" phai ra Philips (tu khoa chua khoa).
    """
    needle = tokens(keyword)
    if not needle or all(t in BRAND_STOPWORDS for t in needle):
        return []
    hits = []
    for domain, profile in SITE_PROFILES.items():
        for key in _brand_keys(domain, profile):
            key_tokens = tokens(key)
            if _is_subsequence(key_tokens, needle) or _is_subsequence(needle, key_tokens):
                hits.append(domain)
                break
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


# -- goi y khi dang go -------------------------------------------------------
#
# `classify()` tra loi cau hoi "go xong bam Enter thi crawl gi", nen no phai TAT
# DINH va khop CHAT. Goi y tra loi mot cau hoi khac han: "go hai chu roi thi co
# the y nguoi dung la gi". Cho nen luat khop o day LONG hon co chu dich:
#
#     go `led`  ->  classify: khong phai nhan hieu (xem BRAND_STOPWORDS)
#                   goi y:    nhan hieu KingLED, VinaLED, VNE
#                             danh muc  Đèn LED Âm Trần, Đèn LED Dây, ...
#
# Hai luat khac nhau khong mau thuan, vi chung cam ket hai thu khac nhau: goi y
# khong chon gi thay nguoi dung, no chi bay ra de nguoi dung bam. Khop long o
# cho khong cam ket la re; khop long o cho cam ket 30-70 phut crawl thi khong.


@dataclass
class Suggestion:
    """Mot dong trong danh sach goi y.

    `query` la thu duoc dien vao o tim kiem khi nguoi dung bam. Hop dong cua no:

        classify(s.query, categories, prefer=s.kind).kind == s.kind

    tuc phai di kem `prefer`, KHONG duoc goi classify tran. Ly do la mot ca
    that: goi y danh muc `Đèn LED Âm Trần VinaLED` neu classify tran se ra NHAN
    HIEU VinaLED (nhan hieu duoc uu tien truoc, va ten danh muc cua site nay co
    kem ten nhan) - tuc bam mot danh muc 166 san pham lai duoc pham vi 668 san
    pham cua ca nhan.

    `prefer` da co san tu task 3.4 cho viec nguoi dung chuyen loai; bam goi y
    dung lai chinh duong do, nen bam goi y khong phai mot duong song song phai
    bao tri rieng.
    """

    kind: ScopeKind
    label: str
    query: str
    domains: tuple[str, ...] = ()
    # So san pham DA CO trong kho. 0 nghia la chua crawl - van hien de nguoi
    # dung biet minh sap la nguoi dau tien crawl no, khong phai an di.
    products: int = 0


@dataclass
class Suggestions:
    keyword: str
    brands: list[Suggestion] = field(default_factory=list)
    categories: list[Suggestion] = field(default_factory=list)
    products: list[Suggestion] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.brands or self.categories or self.products)


def _loose_match(keyword: str, target: Optional[str]) -> bool:
    """Moi tu cua tu khoa la CHUOI CON cua chuoi dich.

    Long hon `matches_all_tokens` dung mot bac: ben kia doi tu khoa la mot tu
    tron ven trong chuoi dich, ben nay chi doi no co mat. Day la thu cho `led`
    keo ra `KingLED` va `am` keo ra `âm trần` khi nguoi dung moi go duoc 2 chu.
    """
    haystack = normalise(target)
    if not haystack:
        return False
    parts = tokens(keyword)
    return bool(parts) and all(part in haystack for part in parts)


def _rank(keyword: str, label: str, products: int) -> tuple:
    """Khop DAU TU len truoc, roi den so san pham giam dan, roi theo alphabet.

    Khop dau tu truoc vi khi go `am` thi `Đèn âm trần` sat y hon `Đèn nam
    châm`, du ca hai deu chua chuoi `am`. So san pham lam thuoc do thu hai vi
    danh muc nhieu hang la danh muc nguoi dung hay hoi hon.
    """
    words = tokens(label)
    starts = any(word.startswith(part) for part in tokens(keyword) for word in words)
    return (0 if starts else 1, -products, normalise(label))


def suggest(
    keyword: str,
    *,
    categories: Iterable[tuple[str, str, int]] = (),
    product_counts: Optional[Mapping[str, int]] = None,
    product_names: Iterable[tuple[str, str]] = (),
    limit: int = 8,
) -> Suggestions:
    """Tu khoa dang go -> goi y, tach theo LOAI.

    Dau vao la du lieu da nap san, khong phai ket noi kho: ham nay duoc goi moi
    lan go phim nen no phai chay tren bo nho. Ben goi (tang API) giu cache va
    lam moi sau moi lan crawl - do la ly do chu ky song cua cache nam o do chu
    khong o day.

    - `categories`: (domain, ten danh muc, so san pham da co). Gop TAT CA nguon
      danh muc dang co - chi muc tang 0.5 (biet ca danh muc chua crawl) lan cot
      `category_1` cua kho (biet cai da crawl). Danh muc chua crawl vao voi so 0.
    - `product_counts`: domain -> so san pham trong kho, de xep hang nhan hieu.
    - `product_names`: (domain, ten san pham). Ben goi gioi han so luong.
    """
    product_counts = product_counts or {}
    result = Suggestions(keyword=keyword)
    if not normalise(keyword):
        return result

    # Nhan hieu: gop theo TEN NHAN chu khong theo domain. Philips co hai site
    # (philipsvietnam.com va www.lighting.philips.com.vn) nhung voi nguoi dung
    # do la MOT nhan - hien hai dong chi bat ho chon giua hai thu ho khong phan
    # biet duoc.
    by_brand: dict[str, Suggestion] = {}
    for domain, profile in SITE_PROFILES.items():
        keys = [domain, profile.brand_name, *profile.brand_aliases]
        if not any(_loose_match(keyword, k) for k in keys if k):
            continue
        name = profile.brand_name or domain
        entry = by_brand.setdefault(
            name, Suggestion(kind=ScopeKind.BRAND, label=name, query=name)
        )
        entry.domains = tuple(sorted(set(entry.domains) | {domain}))
        entry.products += product_counts.get(domain, 0)
    result.brands = sorted(
        by_brand.values(), key=lambda s: _rank(keyword, s.label, s.products)
    )[:limit]

    # Danh muc: gop cac ten TRUNG NHAU sau chuan hoa. "Đèn đường" co mat o 5
    # site - gop lai thanh mot dong keo theo 5 nhan hieu thi dung voi cau hoi
    # that cua nguoi dung ("lay hang den duong cua cac doi thu"), con de rieng
    # 5 dong la bat ho bam 5 lan cho cung mot y.
    by_category: dict[str, Suggestion] = {}
    # Ten hien thi cua mot dong da gop: cac site viet cung mot danh muc theo
    # cac kieu khac nhau (`ĐÈN LED ÂM TRẦN` vs `Đèn LED âm trần`), phai chon
    # MOT. Chon theo so san pham lon nhat, hoa thi theo alphabet - tat dinh,
    # khong phu thuoc thu tu du lieu nap vao.
    best: dict[str, tuple[int, str]] = {}
    for domain, name, count in categories:
        if not name or not _loose_match(keyword, name):
            continue
        key = normalise(name)
        entry = by_category.setdefault(
            key, Suggestion(kind=ScopeKind.CATEGORY, label=name, query=name)
        )
        entry.domains = tuple(sorted(set(entry.domains) | {domain}))
        entry.products += count
        if key not in best or (count, name) > best[key]:
            best[key] = (count, name)
            entry.label = entry.query = name
    result.categories = sorted(
        by_category.values(), key=lambda s: _rank(keyword, s.label, s.products)
    )[:limit]

    seen: set[str] = set()
    for domain, name in product_names:
        if not name or not _loose_match(keyword, name) or normalise(name) in seen:
            continue
        seen.add(normalise(name))
        result.products.append(
            Suggestion(kind=ScopeKind.PRODUCT_NAME, label=name, query=name, domains=(domain,))
        )
    result.products = sorted(
        result.products, key=lambda s: _rank(keyword, s.label, 0)
    )[:limit]
    return result


__all__ = [
    "BRAND_STOPWORDS",
    "CategoryMatch",
    "PRIORITY",
    "Scope",
    "ScopeKind",
    "Suggestion",
    "Suggestions",
    "classify",
    "match_brands",
    "match_categories",
    "matches_all_tokens",
    "normalise",
    "suggest",
    "tokens",
]
