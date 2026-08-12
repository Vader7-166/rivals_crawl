"""Lam sach HTML truoc khi dua vao LLM (task 7.5) va trich rieng bang thong so
ky thuat sach cho field `Thông số kỹ thuật` cua product-record-schema.

2 ham public phuc vu 2 muc dich khac nhau, KHONG dung chung 1 output:
- clean_html_for_llm: dua het ngu canh (bang + mo ta) cho LLM de tang 2 tach
  duoc cang nhieu thuoc tinh cang tot - chap nhan hoi "rong" vi day chi la
  input cho model, khong phai gia tri luu vao ban ghi.
- extract_spec_text: CHI lay dung cac dong "label: value" tu bang 2 cot doi
  xung (bang thong so ky thuat that) - bo qua moi bang khac hinh dang (vd
  bang "san pham tuong tu"/so sanh) va toan bo text con lai cua trang. Day
  moi la gia tri duoc ghi vao cot "Thông số kỹ thuật" - khong duoc phep la
  ban dump toan bo trang (bug da gap: field dai 4000 ky tu vi lay ca menu
  danh muc + mo ta marketing cua trang).
"""
from __future__ import annotations

from bs4 import BeautifulSoup

_STRIP_TAGS = (
    "script", "style", "nav", "aside", "footer", "header", "noscript", "svg", "iframe",
)
# LUU Y: KHONG strip the <form> - ASP.NET WebForms (case Roman.vn) boc TOAN
# BO trang trong 1 <form id="form1"> duy nhat, khong chi cac form nho (tim
# kiem/lien he) nhu gia dinh ban dau. Strip form o day tung xoa sach hoan
# toan noi dung trang tren Roman (bao gom ca bang thong so ky thuat that).


def _cell_lines(cell) -> list[str]:
    text = cell.get_text("\n", strip=True)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return lines or [""]


def _spec_pair_lines(table) -> list[str]:
    """Dong "label: value" tu 1 bang 2 cot doi xung ve so dong con - dung cho
    ca truong hop 1 hang duy nhat voi nhieu cap gop boi <br> (TLC) lan nhieu
    hang moi hang 1 cap (Roman). Bang khong khop hinh dang nay (vd bang so
    sanh nhieu cot) tra ve [] - bi loai khoi "Thông số kỹ thuật"."""
    lines: list[str] = []
    rows = table.find_all("tr") or [table]
    for row in rows:
        cells = row.find_all(["td", "th"]) if row.name == "tr" else row.find_all("td")
        if len(cells) != 2:
            continue
        label_lines, value_lines = _cell_lines(cells[0]), _cell_lines(cells[1])
        if len(label_lines) == len(value_lines):
            lines.extend(f"{label}: {value}" for label, value in zip(label_lines, value_lines))
    return lines


def _table_to_lines(table) -> list[str]:
    """Nhu _spec_pair_lines nhung giu lai ca bang khong khop hinh dang 2 cot
    (join bang " | ") - dung khi dua ngu canh cho LLM (clean_html_for_llm),
    noi ngu canh du thua khong sao vi model tu loc, khac voi extract_spec_text
    la gia tri luu thang vao ban ghi nen phai sach."""
    spec_lines = _spec_pair_lines(table)
    if spec_lines:
        return spec_lines
    rows = table.find_all("tr") or [table]
    lines: list[str] = []
    for row in rows:
        cells = row.find_all(["td", "th"]) if row.name == "tr" else row.find_all("td")
        if not cells:
            continue
        lines.append(" | ".join(" ".join(_cell_lines(c)) for c in cells))
    return lines


def clean_html_for_llm(html: str, max_chars: int = 12_000) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()

    table_lines: list[str] = []
    for table in soup.find_all("table"):
        table_lines.extend(_table_to_lines(table))
        table.decompose()

    body = soup.body or soup
    remaining_text = body.get_text("\n", strip=True)

    combined = "\n".join(table_lines + [remaining_text])
    return combined[:max_chars]


def extract_spec_text(html: str, max_chars: int = 3000) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()

    lines: list[str] = []
    for table in soup.find_all("table"):
        lines.extend(_spec_pair_lines(table))

    return "\n".join(lines)[:max_chars]
