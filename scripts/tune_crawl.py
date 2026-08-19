"""Do de tim TRAN phu hop cho he thong, roi chot cau hinh theo so lieu that.

Chay:  .venv/bin/python scripts/tune_crawl.py [so_san_pham_moi_muc]

Vi sao can cong cu nay thay vi doan: tran cua pipeline nay KHONG nam o may minh
ma nam o 2 phia ben ngoai, va ca hai deu khong biet truoc:
  - server doi thu  -> bop bang thong theo ket noi dong thoi (fetch)
  - quota Vertex AI -> gioi han theo gio/ngay (goi LLM)
Ca hai deu thay doi theo thoi diem, nen phai DO lai moi khi muon chot lai muc.

Script cham moi cau hinh tren CA HAI truc, vi nhanh ma hong du lieu thi vo nghia:
  TOC DO      : giay/san pham
  CHAT LUONG  : ty le san pham loi, so tag trung binh, ty le tag co CAN CU
                (gia tri tag that su xuat hien trong text nguon - chong bia)
"""
from __future__ import annotations

import json
import logging
import re
import statistics
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import requests  # noqa: E402

from crawler.llm import LLMProviderError, build_default_llm_provider  # noqa: E402
from crawler.pipeline import crawl_product_urls  # noqa: E402
from crawler.record import CrawlStatus  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("tune_crawl")

SITEMAP = "https://tlclighting.com.vn/product-sitemap.xml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9",
}
# Nghi giua cac muc de quota/server hoi lai - neu khong, muc do sau se bi thiet
# thoi vi muc truoc vua vet sach quota, va ket qua so sanh se vo nghia.
REST_BETWEEN_RUNS = 45


def _norm(s: str) -> str:
    return re.sub(r"[\s ]+", "", unicodedata.normalize("NFC", str(s)).lower())


def grounding_rate(records) -> float:
    """Ty le gia tri tag thuc su xuat hien trong text nguon cua chinh trang do.

    Day la thuoc do CHONG BIA: LLM co the tra ve tag dep de nhung bia ra thi
    gia tri se khong co trong nguon. Dung `Thông số kỹ thuật` + ten san pham
    lam nguon doi chieu (khong hoan hao - cot nay rong o ~9% san pham - nen chi
    dung de SO SANH giua cac cau hinh, khong doc nhu ty le tuyet doi.
    """
    total = hit = 0
    for r in records:
        source = _norm((r.thong_so_ky_thuat or "") + " " + (r.ten_san_pham or ""))
        if not source:
            continue
        for value in (r.tags or {}).values():
            total += 1
            pieces = [p for p in re.split(r"[/,;()]+", _norm(value)) if p]
            if pieces and all(p in source for p in pieces):
                hit += 1
    return hit / total if total else 0.0


def measure(urls, workers, llm_provider) -> dict:
    started = time.time()
    records = crawl_product_urls(urls, llm_provider=llm_provider, workers=workers)
    elapsed = time.time() - started

    failed = [r for r in records if r.crawl_status != CrawlStatus.OK]
    tag_counts = [len(r.tags or {}) for r in records]
    return {
        "workers": workers,
        "secs_per_product": elapsed / len(urls),
        "total_secs": elapsed,
        "fail_rate": len(failed) / len(records) if records else 1.0,
        "avg_tags": statistics.mean(tag_counts) if tag_counts else 0.0,
        "grounding": grounding_rate(records),
    }


def main() -> None:
    sample_size = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    levels = [1, 2, 4, 8]

    try:
        llm_provider = build_default_llm_provider()
    except LLMProviderError as exc:
        logger.error("Chưa cấu hình LLM provider: %s", exc)
        raise SystemExit(1)

    sitemap = requests.get(SITEMAP, timeout=20, headers=HEADERS).text
    all_urls = [u for u in re.findall(r"<loc>(.*?)</loc>", sitemap) if "/san-pham/" in u]
    if len(all_urls) < sample_size:
        raise SystemExit(f"Sitemap chỉ có {len(all_urls)} URL sản phẩm")

    print(f"Đo {len(levels)} mức worker, mỗi mức {sample_size} sản phẩm.")
    print("Mỗi mức dùng SẢN PHẨM KHÁC NHAU để không hưởng lợi từ cache của lần trước.\n")

    rows = []
    for i, workers in enumerate(levels):
        urls = all_urls[i * sample_size : (i + 1) * sample_size]
        print(f"  đang đo {workers} luồng...", flush=True)
        rows.append(measure(urls, workers, llm_provider))
        if i < len(levels) - 1:
            time.sleep(REST_BETWEEN_RUNS)

    print()
    print(f"{'luồng':>6} {'giây/SP':>9} {'tỷ lệ lỗi':>10} {'tag TB':>8} {'có căn cứ':>10}")
    print("-" * 48)
    for r in rows:
        print(f"{r['workers']:>6} {r['secs_per_product']:>9.2f} "
              f"{r['fail_rate']*100:>9.0f}% {r['avg_tags']:>8.1f} {r['grounding']*100:>9.0f}%")

    # Chon muc nhanh nhat trong so cac muc GIU DUOC chat luong. Nhanh ma hong
    # du lieu thi khong tinh la toi uu.
    best_quality = max(r["avg_tags"] for r in rows)
    ok = [
        r for r in rows
        if r["fail_rate"] <= 0.05 and r["avg_tags"] >= best_quality * 0.95
    ]
    print()
    if ok:
        best = min(ok, key=lambda r: r["secs_per_product"])
        print(f"ĐỀ XUẤT: CRAWL_WORKERS={best['workers']} "
              f"({best['secs_per_product']:.2f}s/SP, lỗi {best['fail_rate']*100:.0f}%, "
              f"{best['avg_tags']:.1f} tag/SP)")
        print(f"  -> 559 sản phẩm ≈ {best['secs_per_product']*559/60:.0f} phút")
    else:
        print("KHÔNG mức nào đạt ngưỡng chất lượng (lỗi ≤5% và tag ≥95% mức tốt nhất).")
        print("Nhiều khả năng quota Vertex đang cạn - nghỉ vài giờ rồi đo lại.")

    out = Path("output/tune_results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSố liệu chi tiết: {out}")


if __name__ == "__main__":
    main()
