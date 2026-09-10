"""Noi tang 1 (structured data) -> tang 1.5 (CSS fallback) -> tang 2 (LLM)
thanh 1 pipeline crawl 1 danh sach URL san pham thanh ProductRecord.

Dung chung cho moi site (khong rieng cho TLC) - xem src/crawler/sites/tlc.py
cho phan logic rieng cua TLC (tim URL san pham thuoc 1 category cu the).
"""
from __future__ import annotations

import logging

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional, Sequence
from urllib.parse import urlparse

from .config import CRAWL
from .extraction import (
    apply_css_fallback,
    extract_advantages,
    extract_categories,
    extract_structured_data,
    get_description_selector,
    get_noise_selector,
    get_spec_root_selector,
    is_placeholder_price,
)
from .fetch import StealthFetcher
from .llm.extractor import extract_tags_from_html
from .llm.provider import LLMProvider, LLMProviderError
from .llm.validate import ExtractionValidationError
from .llm.html_cleaner import extract_spec_text
from .record import CrawlStatus, ProductRecord, write_records_to_excel
from .store import CrawlStore

logger = logging.getLogger(__name__)

# Phien ban cua BO TRICH XUAT (tang 1 + 1.5 + 1.6 + 2), ghi kem moi ban ghi
# trong kho du lieu. PHAI tang khi doi hanh vi trich xuat - do la thu cho phep
# so hai lan chay tren cung mot snapshot de biet mot chinh sua va duoc may o va
# lam hong may o (scripts/diff_extractions.py). Khong tang thi hai lan chay lan
# vao nhau va phep so mat y nghia.
# v2 -> v3: cho `ten_san_pham` di qua tang 1.5 (truoc day lay thang tu tang 1,
# nen site khong co structured data va khong co OpenGraph thi mat ten).
# v1 -> v2: them danh muc doc tu DOM (DOMAIN_CATEGORY_SELECTORS), cot Gia doi
# chieu, va cho tang 1.5 va duoc ca `link_anh_san_pham`; doc duoc cap thong so
# co nhan la <strong> thay vi <label>; sua ranh gioi muc "Uu diem" khi mot the
# BOC de muc ke tiep thay vi LA de muc ke tiep.
EXTRACTOR_VERSION = "v3"


def crawl_product_urls(
    urls: Sequence[str],
    *,
    llm_provider: LLMProvider,
    fetcher: Optional[StealthFetcher] = None,
    existing: Optional[dict[str, ProductRecord]] = None,
    workers: Optional[int] = None,
    checkpoint_path: Optional[Path] = None,
    checkpoint_every: int = 15,
    fetch_options: Optional[dict] = None,
    store: Optional[CrawlStore] = None,
    extractor_version: str = EXTRACTOR_VERSION,
) -> list[ProductRecord]:
    """Crawl danh sach URL san pham, tai su dung ban ghi da OK thay vi crawl
    lai (crawl-lai-co-chon-loc).

    Trang thai lay tu `store` neu co; `existing` chi de ghi de tuong minh (test,
    hoac goi tu code chua dung kho du lieu).

    `workers` > 1 thi fetch van TUAN TU (1 browser duy nhat) nhung phan xu ly
    tang 1/1.5/2 chay song song va chong len phan fetch - xem _crawl_pipelined
    de biet vi sao KHONG song song hoa phan fetch.

    `checkpoint_path` CHI con tac dung khi KHONG co `store` (duong chay cu).
    Co kho du lieu thi moi ban ghi duoc commit ngay khi xong - diem khoi phuc
    day hon, va viec ghi Excel lui han ve buoc ket xuat cuoi.

    Neu `checkpoint_path` duoc truyen (va khong co store), ket qua tam duoc ghi ra .xlsx
    do sau moi `checkpoint_every` san pham MOI crawl (khong tinh cac ban ghi
    tai su dung tu `existing`) - moi mot pipeline chay lau (hang chuc phut cho
    ca category, ~35 phut cho ca site) co the bi ngat giua chung boi tien trinh
    ben ngoai (mat dien/timeout/kill/can quota LLM), va vi ghi Excel von chi
    xay ra 1 lan o cuoi nen tung bi mat toan bo tien do da crawl. Checkpoint
    bien "chay lai tu dau" thanh "chay lai tiep tuc" nho co che
    crawl-lai-co-chon-loc da co san.

    `fetch_options` duoc truyen thang cho `fetcher.fetch()` (vd `wait_selector`
    / `click_selectors` cho site chi render thong so sau khi JS chay - case
    KingLED). De rong thi fetch mac dinh nhu cu.

    `store` (tuy chon) la kho du lieu: HTML duoc luu NGAY SAU khi fetch, ket qua
    trich xuat luu sau do kem `extractor_version`. Ca hai deu ghi tu DUY NHAT
    main thread - worker chi tinh toan roi tra ban ghi ve. De None thi pipeline
    chay y nhu truoc khi co kho du lieu.
    """
    fetch_options = fetch_options or {}
    workers = CRAWL.workers if workers is None else workers
    # Nguon trang thai la KHO DU LIEU, khong con la file .xlsx doc nguoc. Khac
    # biet quan trong: khong phu thuoc vao su ton tai cua file nao ca, nen cai
    # bay cu ("xoa file .xlsx truoc khi chay lai, neu khong se khong co gi thay
    # doi" - docs/todo.md) bien mat. `existing` van nhan duoc de goi tu code cu
    # / test khong co kho van chay.
    if existing is None and store is not None and urls:
        # Gom theo MOI domain co mat chu khong chi domain cua URL dau: mot lan
        # chay thuong chi nham 1 site, nhung gia dinh do khong duoc phep im
        # lang - danh sach lai domain thi cac URL con lai se bi crawl lai het.
        existing = {}
        for site in {urlparse(u).netloc for u in urls}:
            existing.update(store.current_records(site))
    existing = existing or {}

    # Tach truoc: ban ghi da OK thi khong ton fetch lan goi LLM nao.
    results: list[Optional[ProductRecord]] = [None] * len(urls)
    todo: list[tuple[int, str]] = []
    for index, url in enumerate(urls):
        prior = existing.get(url)
        if prior is not None and prior.crawl_status == CrawlStatus.OK:
            results[index] = prior
        else:
            todo.append((index, url))

    def checkpoint(newly_crawled: int) -> None:
        # Co kho du lieu thi KHONG ghi tam ra .xlsx nua: moi ban ghi da duoc
        # commit ngay khi xong, tuc diem khoi phuc day hon han (tung ban ghi so
        # voi moi 40 ban). Ghi Excel gio chi con la buoc KET XUAT o cuoi
        # (store/export.py), khong con la co che chong mat tien do.
        if store is not None:
            return
        if checkpoint_path is None or newly_crawled % checkpoint_every:
            return
        logger.info(
            "Checkpoint: đã crawl mới %d sản phẩm, ghi tạm ra %s",
            newly_crawled, checkpoint_path,
        )
        write_records_to_excel([r for r in results if r is not None], checkpoint_path)

    if todo:
        logger.info(
            "Cần crawl %d/%d URL (%d tái sử dụng từ lần trước), %d luồng xử lý",
            len(todo), len(urls), len(urls) - len(todo), max(1, workers),
        )
        owned = None
        if fetcher is None:
            owned = StealthFetcher()
            owned.__enter__()
            fetcher = owned
        try:
            if workers > 1:
                _crawl_pipelined(
                    todo, results, fetcher, llm_provider, workers, checkpoint,
                    fetch_options, store, extractor_version,
                )
            else:
                for done, (index, url) in enumerate(todo, start=1):
                    fetch_result = fetcher.fetch(url, **fetch_options)
                    # Luu HTML TRUOC khi trich xuat: tang 2 no loi hay tien
                    # trinh bi kill giua chung thi trang van con de chay lai.
                    snapshot_id = store.save_snapshot(url, fetch_result) if store else None
                    record = _build_record(
                        url, fetch_result, str(index + 1), llm_provider
                    )
                    results[index] = record
                    if store is not None:
                        store.save_extraction(
                            record, snapshot_id=snapshot_id,
                            extractor_version=extractor_version,
                        )
                    checkpoint(done)
        finally:
            if owned is not None:
                owned.__exit__(None, None, None)

    return [r for r in results if r is not None]


def _crawl_pipelined(
    todo: list[tuple[int, str]],
    results: list[Optional[ProductRecord]],
    fetcher: StealthFetcher,
    llm_provider: LLMProvider,
    workers: int,
    checkpoint: Callable[[int], None],
    fetch_options: dict,
    store: Optional[CrawlStore] = None,
    extractor_version: str = EXTRACTOR_VERSION,
) -> None:
    """Fetch TUAN TU (1 browser) nhung xu ly SONG SONG, 2 phan chong len nhau.

    Kien truc BAT DOI XUNG nay dua tren do thuc te, khong phai suy luan - va no
    nguoc voi truc giac "song song hoa tat ca":

    Fetch song song lam CHAM DI (tlclighting.com.vn, 24 san pham):
        1 luong 3.38s/SP | 4 luong 4.04s/SP (0.84x) | 8 luong 5.77s/SP (0.59x)
    kem theo timeout 30s -> MAT san pham. Server doi thu bop bang thong theo so
    ket noi dong thoi; may minh (12 core, CPU rank ranh) khong phai nut that.

    Nguoc lai, goi LLM song song thi CO an that (phia Google):
        1 luong 16.6 SP/phut | 3 luong 28.8 | 6 luong 39.5

    Nen: main thread fetch tung trang mot (lich su voi server ho), moi trang
    fetch xong duoc day ngay vao pool de tang 1/1.5/2 chay nen. Trong luc worker
    dang goi LLM cho san pham N thi main thread da fetch san pham N+1 - thoi
    gian LLM bi "giau" sau thoi gian fetch. Tran moi la phan fetch tuan tu, va
    do la tran KHONG the pha bo them ma khong lam phien server doi thu.
    """
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = []
        snapshot_ids: list[Optional[int]] = []  # song song voi `futures`
        collected = 0  # so future da thu hoach, cung la so dem cho checkpoint

        def harvest(block: bool) -> None:
            """Thu hoach future da xong o DAU hang doi, theo dung thu tu submit.

            Chi lay tu dau ve nen `results` luon duoc lap day thanh 1 doan lien
            tuc - file checkpoint ghi ra la 1 tien do lien tuc chu khong phai
            tap hop lo cho rai rac.
            """
            nonlocal collected
            while collected < len(futures) and (block or futures[collected].done()):
                index, record = futures[collected].result()
                results[index] = record
                # Diem ghi DON LUONG: harvest() chi chay tren main thread. Ghi
                # tu trong worker se cho nhieu luong cung dung mot ket noi
                # SQLite - vua sai vua de dinh `database is locked`.
                if store is not None:
                    store.save_extraction(
                        record, snapshot_id=snapshot_ids[collected],
                        extractor_version=extractor_version,
                    )
                collected += 1
                checkpoint(collected)

        for index, url in todo:
            # Chi buoc nay chiem main thread; submit() tra ve ngay lap tuc nen
            # vong lap chay tiep sang URL ke tiep trong khi worker dang xu ly.
            fetch_result = fetcher.fetch(url, **fetch_options)
            # Van la main thread -> ghi kho du lieu duoc. Luu HTML ngay bay gio,
            # truoc khi day sang worker: fetch da ton thoi gian roi, khong duoc
            # phep mat no chi vi tang 2 no loi o buoc sau.
            snapshot_ids.append(store.save_snapshot(url, fetch_result) if store else None)
            futures.append(
                pool.submit(
                    _record_from_fetch, index, url, fetch_result,
                    str(index + 1), llm_provider,
                )
            )
            # Thu hoach NGAY trong vong lap fetch, khong doi submit xong het.
            # Ban dau viec thu hoach nam sau ca vong lap nay, va hau qua la
            # checkpoint KHONG BAO GIO chay giua chung: ca dot 549 san pham
            # (~70 phut) chi ghi ra file o nhung giay cuoi cung. Do la dung thu
            # ma checkpoint sinh ra de chong (mat dien / bi kill / can quota
            # giua chung) - lan chay TLC 485 san pham truoc do khong he co 1
            # dong "Checkpoint" nao trong log dung vi ly do nay.
            # `block=False`: chi nhat future da xong, khong lam cham vong fetch.
            harvest(block=False)

        harvest(block=True)


def _record_from_fetch(
    index: int,
    url: str,
    fetch_result,
    fallback_product_id: str,
    llm_provider: LLMProvider,
) -> tuple[int, ProductRecord]:
    """Ban chay trong worker pool: nhan HTML da fetch san, chi lam tang 1/1.5/2.

    Tra kem `index` de ben goi ghep lai dung thu tu URL ban dau.
    """
    return index, _build_record(url, fetch_result, fallback_product_id, llm_provider)


def _build_record(
    url: str, fetch_result, fallback_product_id: str, llm_provider: LLMProvider
) -> ProductRecord:
    """Tang 1 -> tang 1.5 -> tang 2 tren HTML da co san (khong fetch nua)."""
    domain = urlparse(url).netloc

    if not fetch_result.ok or not fetch_result.html:
        logger.warning("Fetch thất bại cho %s: %s", url, fetch_result.error)
        record = ProductRecord(product_id=fallback_product_id, link_san_pham=url)
        record.mark_error(fetch_result.error or f"HTTP {fetch_result.status}")
        return record

    html = fetch_result.html
    # Site khong trinh bay thong so bang <table> can 1 selector khoanh vung
    # rieng; None voi domain chua dang ky (html_cleaner chi doc <table> nhu cu).
    spec_root_selector = get_spec_root_selector(domain)
    # Khoi "san pham lien quan" lap lai dung bo cuc thong so cua san pham chinh
    # -> phai go truoc khi dua trang cho tang 2, neu khong LLM nhat thong so cua
    # san pham khac gan vao ban ghi nay (da do duoc tren kingled.com.vn).
    noise_selector = get_noise_selector(domain)
    structured = extract_structured_data(html, url)

    # Gia "cho trong" cua site (vd KingLED khai price=0 cho san pham khong niem
    # yet gia) phai duoc coi la CHUA phan giai truoc khi vao tang 1.5, vi
    # apply_css_fallback chi va nhung field con thieu - 0.0 khong phai gia tri
    # thieu nen se chan mat co hoi doc lai gia hien thi tren DOM.
    gia_tang1 = None if is_placeholder_price(domain, structured.gia) else structured.gia

    patched = apply_css_fallback(
        html,
        {
            "gia": gia_tang1,
            "gia_doi_chieu": None,
            "ma_san_pham": structured.ma_san_pham,
            "link_anh_san_pham": structured.link_anh_san_pham,
            # Ten san pham cung phai di qua tang 1.5. Truoc day khong: no lay
            # thang tu tang 1, nen site nao khong co structured data VA khong
            # phat OpenGraph thi mat ten du ten hien ro trong <h1> - do tren
            # vne-led.vn, 120/120 ban ghi mat ten vi dung ly do do. Ten con la
            # dau vao cua tang 2, nen mat no lam hong ca viec chuan hoa tags.
            "ten_san_pham": structured.ten_san_pham,
        },
        domain,
    )
    gia = patched.get("gia", gia_tang1)
    ma_san_pham = patched.get("ma_san_pham") or structured.ma_san_pham

    tags: dict = {}
    advantage_anchor: Optional[str] = None
    llm_error: Optional[str] = None
    try:
        extraction = extract_tags_from_html(
            patched.get("ten_san_pham") or "", html, llm_provider,
            spec_root_selector=spec_root_selector,
            noise_selector=noise_selector,
        )
        tags = extraction.tags
        ma_san_pham_llm = extraction.ma_san_pham
        advantage_anchor = extraction.muc_uu_diem
    except (LLMProviderError, ExtractionValidationError) as exc:
        logger.warning("Tầng 2 (LLM) thất bại cho %s: %s", url, exc)
        ma_san_pham_llm = None
        llm_error = str(exc)

    return _assemble_record(
        url, html, fallback_product_id,
        structured=structured, gia=gia,
        gia_doi_chieu=patched.get("gia_doi_chieu"),
        link_anh_san_pham=patched.get("link_anh_san_pham"),
        ma_san_pham=ma_san_pham,
        ten_san_pham=patched.get("ten_san_pham") or structured.ten_san_pham,
        noise_selector=noise_selector, spec_root_selector=spec_root_selector,
        tags=tags, ma_san_pham_llm=ma_san_pham_llm, anchor=advantage_anchor,
        llm_error=llm_error,
    )


def rebuild_record_from_html(
    url: str,
    html: str,
    fallback_product_id: str,
    *,
    tags: Optional[dict] = None,
    ma_san_pham_llm: Optional[str] = None,
    anchor: Optional[str] = None,
) -> ProductRecord:
    """Chay lai tang 1 / 1.5 / 1.6 tren HTML da luu, KHONG goi LLM.

    Ket qua tang 2 (`tags`, `ma_san_pham_llm`, `anchor`) duoc TRUYEN VAO tu lan
    trich xuat truoc da luu trong kho - chung la dau ra cua mot lan goi mang da
    tra tien roi, khong co ly do goi lai. Do that: 549 trang trong 203 giay
    (370 ms/trang), so voi ~35 phut cua mot luot crawl lai.
    """
    domain = urlparse(url).netloc
    spec_root_selector = get_spec_root_selector(domain)
    noise_selector = get_noise_selector(domain)
    structured = extract_structured_data(html, url)

    gia_tang1 = None if is_placeholder_price(domain, structured.gia) else structured.gia
    patched = apply_css_fallback(
        html,
        {
            "gia": gia_tang1,
            "gia_doi_chieu": None,
            "ma_san_pham": structured.ma_san_pham,
            "link_anh_san_pham": structured.link_anh_san_pham,
            # Ten san pham cung phai di qua tang 1.5. Truoc day khong: no lay
            # thang tu tang 1, nen site nao khong co structured data VA khong
            # phat OpenGraph thi mat ten du ten hien ro trong <h1> - do tren
            # vne-led.vn, 120/120 ban ghi mat ten vi dung ly do do. Ten con la
            # dau vao cua tang 2, nen mat no lam hong ca viec chuan hoa tags.
            "ten_san_pham": structured.ten_san_pham,
        },
        domain,
    )
    return _assemble_record(
        url, html, fallback_product_id,
        structured=structured,
        gia=patched.get("gia", gia_tang1),
        gia_doi_chieu=patched.get("gia_doi_chieu"),
        link_anh_san_pham=patched.get("link_anh_san_pham"),
        ma_san_pham=patched.get("ma_san_pham") or structured.ma_san_pham,
        ten_san_pham=patched.get("ten_san_pham") or structured.ten_san_pham,
        noise_selector=noise_selector, spec_root_selector=spec_root_selector,
        tags=tags or {}, ma_san_pham_llm=ma_san_pham_llm, anchor=anchor,
        llm_error=None,
    )


def _assemble_record(
    url: str,
    html: str,
    fallback_product_id: str,
    *,
    structured,
    gia,
    gia_doi_chieu,
    link_anh_san_pham: Optional[str],
    ma_san_pham: Optional[str],
    ten_san_pham: Optional[str],
    noise_selector: Optional[str],
    spec_root_selector: Optional[str],
    tags: dict,
    ma_san_pham_llm: Optional[str],
    anchor: Optional[str],
    llm_error: Optional[str],
) -> ProductRecord:
    """Phan SAU tang 2: tang 1.6 + dung ban ghi. Dung chung cho ca duong crawl
    that lan duong chay lai tren snapshot, de hai duong khong the lech nhau."""
    ma_san_pham = ma_san_pham or ma_san_pham_llm

    # Danh muc: breadcrumb cua structured data la mac dinh, nhung domain co
    # dang ky selector danh muc thi selector THANG - viec dang ky chinh la ket
    # luan "breadcrumb cua site nay sai/vang" (xem DOMAIN_CATEGORY_SELECTORS).
    cat_1, cat_2, cat_3 = extract_categories(html, urlparse(url).netloc)
    if cat_1 is None:
        cat_1, cat_2, cat_3 = (
            structured.category_1, structured.category_2, structured.category_3,
        )

    # Cum mo ta san pham -> 2 cot "Ưu điểm" cua khuon tham chieu. Co che tong
    # quat cho moi site (tim heading chua chu "ưu điểm"), khong co config rieng
    # theo domain - xem extraction/advantages.py.
    # `anchor` la 1 DONG do tang 2 chi ra de dinh vi muc uu diem khi tu khoa
    # khong bat duoc (tieu de muc nay khong co chuan nao: "Đặc điểm nổi bật",
    # "Lợi ích khi sử dụng", "Tại sao nên dùng...", hoac khong co tieu de).
    # Khong ton them request nao - dung ket qua cua chinh loi goi tang 2 o tren.
    advantages = extract_advantages(
        html,
        noise_selector=noise_selector,
        anchor=anchor,
        # Duong cuoi khi trang khong co MUC uu diem nao: lay ca khoi mo ta cua
        # site. Chi bat cho domain da dang ky - xem DOMAIN_DESCRIPTION_SELECTORS.
        description_selector=get_description_selector(urlparse(url).netloc),
    )

    record = ProductRecord(
        product_id=structured.raw_id or fallback_product_id,
        ten_san_pham=ten_san_pham,
        ma_san_pham=ma_san_pham,
        category_1=cat_1,
        category_2=cat_2,
        category_3=cat_3,
        tags=tags,
        gia=gia,
        gia_doi_chieu=gia_doi_chieu,
        link_san_pham=url,
        link_anh_san_pham=link_anh_san_pham,
        tom_tat_uu_diem_tinh_nang=advantages.tom_tat,
        noi_dung_uu_diem_sp=advantages.noi_dung,
        uu_diem_nguon=advantages.nguon,
        uu_diem_la_ban=anchor,
        thong_so_ky_thuat=extract_spec_text(
            html, spec_root_selector=spec_root_selector, noise_selector=noise_selector
        ) or None,
    )
    # `tags` rong (do llm_error) lam recompute_status() ha trang thai xuong
    # PARTIAL_MISSING_FIELDS - ban ghi tu dong thanh ung vien crawl lai. Ghi
    # them ly do de log/debug, khong xuat ra Excel.
    record.recompute_status()
    if llm_error is not None:
        record.crawl_error = f"Tầng 2 (LLM) thất bại: {llm_error}"
    return record
