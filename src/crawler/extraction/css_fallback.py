"""Tang 1.5: CSS selector fallback nhe theo domain. Tasks 6.1-6.2.

CHI vay nhung field con thieu sau tang 1 (structured data) - khong phai 1 bo
config crawl day du cho ca trang. Vi du kinh dien: Roman.vn khong co
structured data nao ca nhung gia lai nam o 1 vi tri CSS on dinh
(`div.price .val`) - re hon nhieu so voi goi LLM chi de lay 1 con so.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup

from ..record.price import normalize_price


@dataclass(frozen=True)
class SelectorRule:
    field: str
    selector: str
    attr: Optional[str] = None  # None -> lay text noi dung; vd "src"/"href" -> lay attribute
    is_price: bool = False  # True -> chay qua normalize_price truoc khi gan


# Dang ky fallback selector toi thieu theo domain. Chi them entry khi tang 1
# (structured-data-extraction) khong co du lieu cho field do tren chinh domain
# nay - khong suy doan truoc cho site chua khao sat.
DOMAIN_FALLBACK_RULES: dict[str, list[SelectorRule]] = {
    "roman.vn": [
        SelectorRule(field="gia", selector="div.price .val", is_price=True),
        SelectorRule(field="ma_san_pham", selector="div.code .val"),
    ],
}


def apply_css_fallback(html: str, current: dict, domain: str) -> dict:
    """Vay cac field con thieu (falsy) trong `current` bang selector da dang
    ky cho `domain`. Tra ve dict moi, khong sua doi `current` tai cho."""
    rules = DOMAIN_FALLBACK_RULES.get(domain)
    if not rules:
        return current

    soup = BeautifulSoup(html, "lxml")
    result = dict(current)
    for rule in rules:
        if result.get(rule.field):
            continue
        el = soup.select_one(rule.selector)
        if el is None:
            continue
        raw_value = el.get(rule.attr) if rule.attr else el.get_text(strip=True)
        if not raw_value:
            continue
        result[rule.field] = normalize_price(raw_value) if rule.is_price else raw_value

    return result
