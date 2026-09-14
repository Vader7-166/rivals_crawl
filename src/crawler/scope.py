"""Tu khoa -> pham vi CO SO LIEU: khop gi, da co bao nhieu, con thieu bao nhieu.

`search.py` lo phan thuan tuy (khop chu, khong biet gi ve kho du lieu). File nay
noi ket qua do voi chi muc danh muc va kho du lieu de ra con so ma nguoi dung
can THAY TRUOC KHI bam crawl - vi mot luot crawl la 30-70 phut, ho phai biet
minh sap tieu bao nhieu.

"Con thieu" o day KHONG duoc tinh lai: no di qua dung
`CrawlStore.urls_needing_crawl()`, cung ham ma pipeline dung de quyet dinh crawl
gi. Hai duong tinh song song la hai duong se lech nhau.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .search import (
    Scope,
    ScopeKind,
    Suggestions,
    classify,
    matches_all_tokens,
    normalise,
    suggest,
)
from .sites.registry import brand_of
from .store.category_store import CategorySummary, CategoryStore
from .store.crawl_store import CrawlStore


@dataclass
class DomainScope:
    """Pham vi trong pham vi mot domain."""

    domain: str
    brand: str
    categories: list[CategorySummary] = field(default_factory=list)
    product_urls: list[str] = field(default_factory=list)
    total: int = 0
    have: int = 0
    missing: int = 0
    # Domain nam trong pham vi nhung chua dung chi muc danh muc. PHAI phan biet
    # voi "domain khong co san pham nao" - hai cai noi voi nguoi dung hai cau
    # khac han (task 3.7).
    needs_index: bool = False


@dataclass
class ResolvedScope:
    scope: Scope
    domains: list[DomainScope] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(d.total for d in self.domains)

    @property
    def have(self) -> int:
        return sum(d.have for d in self.domains)

    @property
    def missing(self) -> int:
        return sum(d.missing for d in self.domains)

    @property
    def is_fully_crawled(self) -> bool:
        return self.total > 0 and self.missing == 0


def _domain_scope(
    crawl_store: CrawlStore,
    domain: str,
    urls: list[str],
    categories: Optional[list[CategorySummary]] = None,
) -> DomainScope:
    missing = crawl_store.urls_needing_crawl(urls) if urls else []
    return DomainScope(
        domain=domain,
        brand=brand_of(domain),
        categories=categories or [],
        product_urls=urls,
        total=len(urls),
        have=len(urls) - len(missing),
        missing=len(missing),
    )


def resolve(
    keyword: str,
    crawl_store: CrawlStore,
    category_store: CategoryStore,
    *,
    prefer: Optional[ScopeKind] = None,
    exclude_categories: frozenset[str] = frozenset(),
) -> ResolvedScope:
    """Tu khoa -> pham vi day du so lieu.

    `exclude_categories` la cac URL danh muc nguoi dung tick BO tren man xac
    nhan. No duoc truyen vao TUNG LAN GOI va khong luu o dau ca - do la mot
    lua chon luc dung, khong phai mot cau hinh phai bao tri (spec
    `crawl-scope-search`, requirement "Xac nhan pham vi truoc khi chay").
    """
    scope = classify(keyword, category_store.category_names(), prefer=prefer)
    resolved = ResolvedScope(scope=scope)

    if scope.kind is ScopeKind.NONE:
        return resolved

    if scope.kind is ScopeKind.BRAND:
        for domain in scope.domains:
            if not category_store.has_index(domain):
                # Chua dung chi muc -> chua biet danh muc, nhung VAN biet san
                # pham nao da co trong kho. Bao co de giao dien moi dung chi
                # muc, khong bao "khong co san pham nao".
                known = list(crawl_store.current_records(domain))
                domain_scope = _domain_scope(crawl_store, domain, known)
                domain_scope.needs_index = True
                resolved.domains.append(domain_scope)
                continue
            summaries = category_store.summarise(crawl_store, domain)
            urls = category_store.product_urls_in(
                domain, [s.url for s in summaries if s.url not in exclude_categories]
            )
            resolved.domains.append(_domain_scope(crawl_store, domain, urls, summaries))
        return resolved

    if scope.kind is ScopeKind.CATEGORY:
        by_domain: dict[str, list[str]] = {}
        for match in scope.categories:
            if match.category_url in exclude_categories:
                continue
            by_domain.setdefault(match.domain, []).append(match.category_url)
        for domain, category_urls in sorted(by_domain.items()):
            summaries = category_store.summarise(crawl_store, domain, category_urls)
            urls = category_store.product_urls_in(domain, category_urls)
            resolved.domains.append(_domain_scope(crawl_store, domain, urls, summaries))
        return resolved

    # ScopeKind.PRODUCT_NAME - tim tren ten san pham DA CO trong kho.
    #
    # Khac hai nhanh tren o mot diem quan trong: no chi thay duoc thu da crawl.
    # San pham chua crawl thi chua co ten de ma khop - do la gioi han that cua
    # nhanh nay, khong phai loi.
    by_domain_urls: dict[str, list[str]] = {}
    for domain in crawl_store.domains():
        for url, record in crawl_store.current_records(domain).items():
            if matches_all_tokens(keyword, record.ten_san_pham):
                by_domain_urls.setdefault(domain, []).append(url)
    for domain, urls in sorted(by_domain_urls.items()):
        resolved.domains.append(_domain_scope(crawl_store, domain, urls))
    if not resolved.domains:
        scope.reason = (
            f"Không khớp nhãn hiệu, danh mục hay tên sản phẩm nào cho “{keyword}”."
        )
        scope.kind = ScopeKind.NONE
    return resolved


class SuggestionIndex:
    """Nguon goi y da nap san bo nho. MOT lan doc kho, N lan go phim.

    Ly do ton tai, do tren kho that (9.818 ban ghi, 254 danh muc): doc thang tu
    SQLite moi lan goi mat 0,6-0,95s. Voi mot o tim kiem goi sau moi phim thi
    do la khong dung duoc - trong khi chinh du lieu ay chi la vai tram dong,
    nam gon trong bo nho va khop het duoi 1ms.

    Vong doi cache: nap luc khoi dong, `refresh()` sau moi lan crawl hoac dung
    chi muc xong. KHONG tu het han theo thoi gian - du lieu chi doi khi co mot
    job chay xong, va tang goi biet dieu do chinh xac hon bat ky khoang thoi
    gian doan truoc nao.
    """

    def __init__(self, crawl_store: CrawlStore, category_store: CategoryStore):
        self._crawl = crawl_store
        self._categories = category_store
        self._category_rows: list[tuple[str, str, int]] = []
        self._product_counts: dict[str, int] = {}
        self._product_names: list[tuple[str, str]] = []
        self.refresh()

    def refresh(self) -> None:
        stored = self._crawl.category_counts()
        indexed = [
            (domain, name, 0)
            for domain, _url, name in self._categories.category_names()
            if name
        ]
        self._category_rows = stored + indexed
        self._product_counts = self._crawl.product_counts()
        self._product_names = self._crawl.product_names()

    def suggest(self, keyword: str, *, limit: int = 8) -> Suggestions:
        return suggest(
            keyword,
            categories=self._category_rows,
            product_counts=self._product_counts,
            product_names=self._product_names,
            limit=limit,
        )


def suggestions(
    keyword: str,
    crawl_store: CrawlStore,
    category_store: CategoryStore,
    *,
    limit: int = 8,
) -> Suggestions:
    """Goi y khi dang go, nap tu CA HAI nguon danh muc - duong MOT PHAT.

    Doc kho moi lan goi, nen chi dung cho CLI/test. O tim kiem that phai dung
    `SuggestionIndex`.


    Hai nguon khong thay the nhau:

        chi muc tang 0.5   biet ca danh muc CHUA crawl, nhung phai duyet trang
                           danh muc cua doi thu moi co
        cot `category_1`   chi biet cai da crawl, nhung co san va mien phi

    Danh muc chi co trong chi muc vao voi so 0 - hien ra la "chua crawl", dung
    voi su that, va do chinh la dong nguoi dung can bam de tao job. Ten trung
    nhau giua hai nguon duoc `suggest()` gop lai nen khong nhan doi dong nao.
    """
    stored = crawl_store.category_counts()
    indexed = [
        (domain, name, 0)
        for domain, _url, name in category_store.category_names()
        if name
    ]
    return suggest(
        keyword,
        categories=stored + indexed,
        product_counts=crawl_store.product_counts(),
        product_names=crawl_store.product_names(),
        limit=limit,
    )


__all__ = ["DomainScope", "ResolvedScope", "SuggestionIndex", "resolve", "suggestions"]
