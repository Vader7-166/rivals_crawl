"""Tang 1.5: CSS selector fallback nhe theo domain. Tasks 6.1-6.2.

CHI vay nhung field con thieu sau tang 1 (structured data) - khong phai 1 bo
config crawl day du cho ca trang. Vi du kinh dien: Roman.vn khong co
structured data nao ca nhung gia lai nam o 1 vi tri CSS on dinh
(`div.price .val`) - re hon nhieu so voi goi LLM chi de lay 1 con so.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup

from ..record.price import InvalidPriceError, normalize_price

logger = logging.getLogger(__name__)


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
    # KingLED khai gia trong microdata Offer, nhung dung `price=0` lam gia tri
    # tram cho san pham khong niem yet gia (xem DOMAIN_PLACEHOLDER_PRICES).
    # Khi do tang 1 tra ve None va selector nay doc lai gia HIEN THI tren trang.
    # `div.price span p` chi khop khoi "Giá" that; khoi "Giá chiết khấu" ngay
    # duoi khong co the <p> nen khong bi nhat nham (no luon la "Liên hệ tư vấn"
    # - loi moi chat, khong phai gia doi chieu).
    "kingled.com.vn": [
        SelectorRule(field="gia", selector="div.price span p", is_price=True),
    ],
}


# Gia tri "gia" ma site dung lam CHO TRONG chu khong phai gia that. KingLED tra
# `<meta itemprop="price" content="0">` cho san pham khong niem yet gia, va
# trang cua chung khong render khoi gia nao ca. Ghi 0 vao cot Gia thi nguoi doc
# hieu la "mien phi" - sai han y cua nguon; con ep thanh "Liên hệ" thi la tu
# dat loi vao mieng site (trang khong he noi vay). Nen coi nhu CHUA phan giai
# duoc: tang 1.5 duoc quyen doc lai tu DOM, khong duoc thi de o trong va ban
# ghi tu roi xuong partial-missing-fields de nguoi review nhin thay.
DOMAIN_PLACEHOLDER_PRICES: dict[str, tuple[float, ...]] = {
    "kingled.com.vn": (0.0,),
}


def is_placeholder_price(domain: str, value) -> bool:
    """True neu `value` la gia tri gia "cho trong" da biet cua `domain`."""
    placeholders = DOMAIN_PLACEHOLDER_PRICES.get(domain)
    if not placeholders or not isinstance(value, float):
        return False
    return value in placeholders


# Khoi chua bang thong so ky thuat CUA CHINH san pham dang xem, cho nhung site
# khong trinh bay thong so bang <table> (html_cleaner khong tu nhan ra duoc).
# Cung tinh than voi DOMAIN_FALLBACK_RULES: chi ghi domain da khao sat that.
#
# KingLED: ca trang khong co the <table> nao, thong so nam trong bo cuc
# <label>/<span>. Nhung bo cuc do duoc dung lai cho ca khoi "san pham lien
# quan" o cuoi trang, nen pham vi phai khoanh vao dung tab "Thông số kỹ thuật"
# cua san pham dang xem - xem html_cleaner._definition_pair_lines.
DOMAIN_SPEC_ROOT_SELECTORS: dict[str, str] = {
    "kingled.com.vn": 'div.property[data-id="Property"]',
}


def get_spec_root_selector(domain: str) -> Optional[str]:
    """Selector khoanh vung bang thong so cua `domain`, None neu chua dang ky."""
    return DOMAIN_SPEC_ROOT_SELECTORS.get(domain)


# Khoi KHONG thuoc san pham dang xem, phai go bo TRUOC khi dua trang cho LLM.
# Khac voi DOMAIN_SPEC_ROOT_SELECTORS (khoanh vung cho field "Thong so ky
# thuat"), cai nay bao ve TANG 2: clean_html_for_llm van kem toan bo text con
# lai cua trang de model doc duoc thuoc tinh nam trong phan mo ta.
#
# Do that tren kingled.com.vn: trang `bo-nguon-150w` co khoi thong so rieng chi
# 4 dong va KHONG co dong bao hanh, nhung phan text con lai chua them 5 "Mã SP"
# + 5 "Bảo Hành" cua cac phu kien lien quan - va LLM da gan
# `bao_hanh="Đổi mới 2 năm"` lay tu mot phu kien khac vao chinh ban ghi nay.
# `div.item` boc dung cac khoi san pham lien quan (do tren 5 trang that: chua
# 36-71 the <label>, va KHONG bao gio boc khoi thong so cua san pham chinh).
DOMAIN_NOISE_SELECTORS: dict[str, str] = {
    "kingled.com.vn": "div.item",
}


def get_noise_selector(domain: str) -> Optional[str]:
    """Selector cac khoi phai go truoc khi dua trang cho LLM, None neu khong co."""
    return DOMAIN_NOISE_SELECTORS.get(domain)


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
        if rule.is_price:
            # normalize_price nem loi thay vi doan bua khi gap chuoi la - dung
            # y do, nhung o day 1 trang di dang khong duoc phep giet ca dot
            # crawl vai tram san pham. Bo qua field va de ban ghi roi xuong
            # partial-missing-fields, giu nguyen tinh than "khong doan bua".
            try:
                result[rule.field] = normalize_price(raw_value)
            except InvalidPriceError:
                logger.warning(
                    "Bỏ qua giá không phân giải được ở %s (%s): %r",
                    domain, rule.selector, raw_value,
                )
        else:
            result[rule.field] = raw_value

    return result
