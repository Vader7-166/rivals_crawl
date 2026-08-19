"""Kiem dinh cac o TRONG trong file da crawl: site that su khong co, hay minh bo sot?

Vi sao can script rieng thay vi tin vao pipeline: neu dung lai chinh
`extraction/` de kiem tra thi chi la TU XAC NHAN - o nao pipeline bo sot thi
kiem tra cung bo sot y het. Script nay co tinh dung DUONG KHAC:
  - doc thang JSON-LD (`offers.price`, `sku`, `image`) trong the <script>
  - quet vung tom tat san pham (`.summary`) bang selector rieng
  - bat so tien bang regex tren text da trich

Chay: .venv/bin/python scripts/verify_missing_fields.py [file.xlsx]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bs4 import BeautifulSoup  # noqa: E402

from crawler.fetch import StealthFetcher  # noqa: E402
from crawler.record import load_existing_records  # noqa: E402

DEFAULT_PATH = Path("output/tlclighting_all.xlsx")

# So tien kem don vi tien te - dung tren TEXT da trich chu khong phai HTML tho
# (WooCommerce tach so va ky hieu tien ra 2 the khac nhau).
_MONEY = re.compile(r"\d[\d.,]*\s*(?:vnđ|vnd|đồng|₫|đ)\b", re.IGNORECASE)
_CONTACT = re.compile(r"li[êe]n\s*h[ệe]", re.IGNORECASE)
# Vung tom tat san pham cua WooCommerce - KHONG lay ca trang, vi menu/footer
# cua TLC co chu "Liên hệ" tren MOI trang, quet ca trang se bao dong gia.
_SUMMARY_SELECTORS = ("div.summary", "div.entry-summary", "div.product-info")


def _json_ld_nodes(soup: BeautifulSoup):
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                yield node
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)


def _summary(soup: BeautifulSoup):
    for selector in _SUMMARY_SELECTORS:
        found = soup.select_one(selector)
        if found:
            return found
    return None


def check_price(soup: BeautifulSoup) -> tuple[bool, str]:
    """(tim thay gia?, bang chung)."""
    for node in _json_ld_nodes(soup):
        if node.get("@type") == "Offer" or "price" in node:
            price = node.get("price")
            if price not in (None, "", 0, "0"):
                return True, f"JSON-LD offers.price = {price!r}"

    summary = _summary(soup)
    price_el = (summary or soup).select_one("p.price, .price, .woocommerce-Price-amount")
    price_text = price_el.get_text(" ", strip=True) if price_el else ""
    if _MONEY.search(price_text):
        return True, f"ô giá có số tiền: {price_text[:60]!r}"
    if price_text and _CONTACT.search(price_text):
        return True, f"ô giá ghi liên hệ: {price_text[:60]!r}"

    if summary is not None and _MONEY.search(summary.get_text(" ", strip=True)):
        hit = _MONEY.search(summary.get_text(" ", strip=True))
        return True, f"vùng tóm tắt có số tiền: {hit.group(0)!r}"

    if price_el is None:
        return False, "không có ô giá nào trên trang"
    return False, f"ô giá tồn tại nhưng RỖNG ({price_text!r})"


def _wordpress_post_id(soup: BeautifulSoup) -> str | None:
    """ID bai viet WordPress, doc tu class cua <body> (vd `postid-6689`)."""
    body = soup.find("body")
    for css_class in (body.get("class") or []) if body else []:
        match = re.fullmatch(r"postid-(\d+)", css_class)
        if match:
            return match.group(1)
    return None


def check_sku(soup: BeautifulSoup) -> tuple[bool, str]:
    # CANH BAO da kiem chung tren TLC: JSON-LD `sku` o site nay KHONG phai ma
    # san pham ma la POST ID cua WordPress (`sku`=6689 <-> body class
    # `postid-6689`). San pham co ma that "TLC-AECA-VB-10W" cung co sku=13178 =
    # post id cua no - ma that nam trong bang thong so chu khong nam o JSON-LD.
    # Neu tin `sku` la ma san pham thi se ghi so post id vao cot Ma San Pham -
    # bia du lieu. Chi chap nhan khi sku KHAC post id.
    post_id = _wordpress_post_id(soup)
    for node in _json_ld_nodes(soup):
        for key in ("sku", "mpn", "productID"):
            value = node.get(key)
            if value in (None, "", "N/A"):
                continue
            if key == "sku" and str(value) == post_id:
                continue  # post id, khong phai ma san pham
            return True, f"JSON-LD {key} = {value!r}"

    sku_el = soup.select_one(".sku, span.sku, .sku_wrapper")
    sku_text = sku_el.get_text(" ", strip=True) if sku_el else ""
    if sku_text and sku_text.lower() not in ("n/a", "sku:"):
        return True, f".sku = {sku_text[:60]!r}"

    text = soup.get_text(" ", strip=True)
    match = re.search(r"M[ãa]\s*(?:sản phẩm|SP)\s*:?\s*([A-Z0-9][A-Z0-9\-/. ]{2,30})", text, re.I)
    if match:
        return True, f"nhãn 'Mã sản phẩm' có giá trị: {match.group(1).strip()!r}"

    return False, "không có .sku, không có JSON-LD sku, không có nhãn 'Mã sản phẩm' kèm giá trị"


def check_image(soup: BeautifulSoup) -> tuple[bool, str]:
    candidates: list[str] = []
    for node in _json_ld_nodes(soup):
        image = node.get("image")
        if isinstance(image, str):
            candidates.append(image)
        elif isinstance(image, dict) and image.get("url"):
            candidates.append(image["url"])
        elif isinstance(image, list):
            candidates += [i for i in image if isinstance(i, str)]

    og = soup.select_one('meta[property="og:image"]')
    if og and og.get("content"):
        candidates.append(og["content"])

    gallery = soup.select_one(".woocommerce-product-gallery img, .images img, .product img")
    if gallery:
        candidates.append(gallery.get("data-src") or gallery.get("src") or "")

    real = [c for c in candidates if c and "placeholder" not in c.lower()]
    if real:
        return True, f"có ảnh thật: {real[0][:70]}"
    if candidates:
        return False, f"chỉ có ảnh placeholder của WooCommerce: {candidates[0][-45:]}"
    return False, "không có ảnh nào"


CHECKS = {
    "gia": ("Giá", check_price),
    "ma_san_pham": ("Mã Sản Phẩm", check_sku),
    "link_anh_san_pham": ("Link ảnh sản phẩm", check_image),
}


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    records = load_existing_records(path)
    flagged = [r for r in records.values() if r.missing_required_fields()]
    print(f"Kiểm định {len(flagged)} sản phẩm bị gắn cờ trong {path}\n")

    wrong: list[tuple[str, str, str]] = []
    confirmed = 0
    with StealthFetcher() as fetcher:
        for i, record in enumerate(flagged, start=1):
            result = fetcher.fetch(record.link_san_pham)
            if not result.ok or not result.html:
                print(f"[{i}/{len(flagged)}] FETCH LỖI  {record.link_san_pham} ({result.error})")
                continue
            soup = BeautifulSoup(result.html, "lxml")

            missing = [f for f in record.missing_required_fields() if f in CHECKS]
            for field_name in missing:
                label, check = CHECKS[field_name]
                found, evidence = check(soup)
                if found:
                    wrong.append((record.link_san_pham, label, evidence))
                    print(f"[{i}/{len(flagged)}] ❗ {label:<18} CÓ trên trang! {evidence}")
                    print(f"          {record.link_san_pham}")
                else:
                    confirmed += 1
                    print(f"[{i}/{len(flagged)}] ✓ {label:<18} đúng là không có — {evidence}")

    print(f"\n{'='*70}")
    print(f"Xác nhận site THẬT SỰ không có: {confirmed} ô")
    if wrong:
        print(f"BỎ SÓT (site có mà crawler không lấy được): {len(wrong)} ô")
        for url, label, evidence in wrong:
            print(f"  {label:<18} {evidence}\n    {url}")
    else:
        print("BỎ SÓT: 0 — mọi ô trống đều do site nguồn không có dữ liệu.")


if __name__ == "__main__":
    main()
