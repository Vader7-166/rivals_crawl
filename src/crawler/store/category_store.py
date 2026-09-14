"""Doc/ghi chi muc danh muc (tang 0.5) tren kho du lieu.

Ranh gioi voi `crawl_store.py`: file kia lo LICH SU (snapshot + trich xuat, hai
dong lich su khong duoc gop). File nay lo CACHE DAN XUAT - xoa sach roi dung
lai tu site doi thu la ra ket qua nhu cu. Hai thu khac ban chat nen khong dung
chung lop.

AN TOAN LUONG: giong `CrawlStore`, moi ham ghi o day phai duoc goi tu DUY NHAT
MOT luong (va tu duy nhat mot tien trinh khi chay tren Docker).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

from .crawl_store import CrawlStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class CategorySummary:
    """Mot danh muc kem so lieu pham vi.

    `ok=False` nghia la CHUA BIET GI ve danh muc nay (fetch hong), khong phai
    "danh muc rong" - xem chu thich trong schema.sql.
    """

    domain: str
    url: str
    name: Optional[str]
    total: int = 0
    have: int = 0
    missing: int = 0
    ok: bool = True
    error: Optional[str] = None


# Nhan cua nhom san pham co trong sitemap nhung khong xuat hien tren trang danh
# muc nao. KHONG duoc vut di: chung van crawl duoc o pham vi toan domain, va
# chinh so luong cua chung la tin hieu bao trang danh muc liet ke thieu.
UNCATEGORISED = "(chưa xác định danh mục)"


class CategoryStore:
    """Boc mot ket noi SQLite. Khong tu mo/dong - ben goi quyet dinh vong doi."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    # -- ghi ---------------------------------------------------------------

    def save_category(self, domain: str, result) -> None:
        """Luu ket qua duyet 1 danh muc (`CategoryCrawlResult`).

        GHI DE canh cu cua chinh danh muc do: day la cache dan xuat, trang thai
        moi nhat cua site la trang thai dung. Khac han `save_extraction()` -
        ben do khong bao gio ghi de vi lich su moi la thu can giu.
        """
        self._conn.execute(
            "INSERT INTO category_pages (domain, url, name, indexed_at, pages_fetched, ok, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(domain, url) DO UPDATE SET "
            "name = excluded.name, indexed_at = excluded.indexed_at, "
            "pages_fetched = excluded.pages_fetched, ok = excluded.ok, error = excluded.error",
            (domain, result.category_url, result.category_name, _now(),
             result.pages_fetched, 1 if result.ok else 0, result.error),
        )
        self._conn.execute(
            "DELETE FROM category_products WHERE domain = ? AND category_url = ?",
            (domain, result.category_url),
        )
        if result.product_urls:
            self._conn.executemany(
                "INSERT INTO category_products (domain, category_url, product_url) "
                "VALUES (?, ?, ?)",
                [(domain, result.category_url, url) for url in result.product_urls],
            )
        self._conn.commit()

    def clear_domain(self, domain: str) -> None:
        """Xoa sach chi muc cua 1 domain. An toan theo dinh nghia: du lieu nay
        dung lai duoc hoan toan tu site doi thu."""
        self._conn.execute("DELETE FROM category_products WHERE domain = ?", (domain,))
        self._conn.execute("DELETE FROM category_pages WHERE domain = ?", (domain,))
        self._conn.commit()

    # -- doc ---------------------------------------------------------------

    def has_index(self, domain: str) -> bool:
        """Domain da dung chi muc chua. Phan biet "chua dung chi muc" voi "khong
        co san pham nao" - hai cai nay noi voi nguoi dung hai cau khac han."""
        row = self._conn.execute(
            "SELECT 1 FROM category_pages WHERE domain = ? LIMIT 1", (domain,)
        ).fetchone()
        return row is not None

    def category_names(self, domain: Optional[str] = None) -> list[tuple[str, str, Optional[str]]]:
        """(domain, url danh muc, ten) - nguyen lieu cho viec khop tu khoa."""
        if domain is None:
            rows = self._conn.execute(
                "SELECT domain, url, name FROM category_pages ORDER BY domain, url"
            )
        else:
            rows = self._conn.execute(
                "SELECT domain, url, name FROM category_pages WHERE domain = ? ORDER BY url",
                (domain,),
            )
        return [(r["domain"], r["url"], r["name"]) for r in rows]

    def product_urls_in(self, domain: str, category_urls: Iterable[str]) -> list[str]:
        """URL san pham thuoc BAT KY danh muc nao trong danh sach (hop, khong
        trung lap - mot san pham thuoc nhieu danh muc la binh thuong)."""
        category_urls = list(category_urls)
        if not category_urls:
            return []
        holders = ", ".join("?" for _ in category_urls)
        rows = self._conn.execute(
            f"SELECT DISTINCT product_url FROM category_products "
            f"WHERE domain = ? AND category_url IN ({holders}) ORDER BY product_url",
            (domain, *category_urls),
        )
        return [r["product_url"] for r in rows]

    def uncategorised_urls(self, domain: str, all_product_urls: Iterable[str]) -> list[str]:
        """San pham co trong sitemap ma khong trang danh muc nao liet ke.

        Task 2.8. Do la trang thai BINH THUONG (san pham moi, san pham chi vao
        duoc tu tim kiem), khong phai loi - nhung so luong cua no la tin hieu
        canh bao neu tang bat thuong (xem `coverage_gap`).
        """
        indexed = {
            r["product_url"]
            for r in self._conn.execute(
                "SELECT DISTINCT product_url FROM category_products WHERE domain = ?", (domain,)
            )
        }
        return [url for url in all_product_urls if url not in indexed]

    def summarise(
        self,
        crawl_store: CrawlStore,
        domain: str,
        category_urls: Optional[Iterable[str]] = None,
    ) -> list[CategorySummary]:
        """So lieu pham vi cho tung danh muc: tong / da co / con thieu.

        "Con thieu" KHONG duoc tinh lai o day - no di qua dung
        `CrawlStore.urls_needing_crawl()`, cung ham ma pipeline dung de quyet
        dinh crawl gi. Hai duong tinh song song la hai duong se lech nhau.
        """
        wanted = set(category_urls) if category_urls is not None else None
        out: list[CategorySummary] = []
        for row in self._conn.execute(
            "SELECT url, name, ok, error FROM category_pages WHERE domain = ? ORDER BY url",
            (domain,),
        ):
            if wanted is not None and row["url"] not in wanted:
                continue
            urls = self.product_urls_in(domain, [row["url"]])
            missing = crawl_store.urls_needing_crawl(urls) if urls else []
            out.append(
                CategorySummary(
                    domain=domain,
                    url=row["url"],
                    name=row["name"],
                    total=len(urls),
                    have=len(urls) - len(missing),
                    missing=len(missing),
                    ok=bool(row["ok"]),
                    error=row["error"],
                )
            )
        return out

    def coverage_gap(self, domain: str, all_product_urls: Iterable[str]) -> tuple[int, int]:
        """(so URL tu sitemap, so URL co mat trong chi muc). Task 2.10.

        Chenh lech phai duoc BAO RA chu khong nuot: no la dau hieu trang danh
        muc liet ke thieu (site chi hien hang con ban, hoac nap them bang JS) -
        rui ro da ghi trong design.md. Nuot di thi pham vi thieu am tham.
        """
        all_urls = list(all_product_urls)
        uncategorised = self.uncategorised_urls(domain, all_urls)
        return len(all_urls), len(all_urls) - len(uncategorised)


__all__ = ["CategoryStore", "CategorySummary", "UNCATEGORISED"]
