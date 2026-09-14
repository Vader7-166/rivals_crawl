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
from .categories import anchor_categories

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SelectorRule:
    field: str
    selector: str
    attr: Optional[str] = None  # None -> lay text noi dung; vd "src"/"href" -> lay attribute
    is_price: bool = False  # True -> chay qua normalize_price truoc khi gan
    # Nhan mo dau bi site gop chung vao o gia tri, phai cat truoc khi gan. Ca
    # nhan lan dau ":" deu bi cat, vd dienquang.com de ma san pham trong khoi
    # gia duoi dang "Mã sản phẩm: ALLEY 3 - 150" - khong tach the rieng cho
    # con so nen selector nao cung dinh ca nhan.
    strip_prefix: Optional[str] = None


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
    # dienquang.com (Haravan) khai microdata `price=0` cho MOI san pham - ke ca
    # san pham co niem yet gia that (do tren 8 trang: 3 co gia hien thi, 8/8
    # deu khai 0). Gia that chi co trong khoi hien thi `#price-preview`, noi
    # cung chua luon gia truoc giam (`<del>`) va - voi hang cong trinh khong
    # niem yet gia - ma san pham.
    #
    # Hai rule cho `gia` theo dung thu tu tren trang: the <span> dau tien la
    # gia BAN, `<del>` ngay sau moi la gia truoc giam. Rule sau chi co tac dung
    # khi rule truoc khong khop (apply_css_fallback bo qua field da co gia tri).
    "dienquang.com": [
        SelectorRule(
            field="gia",
            selector="#price-preview span.font-24px",
            is_price=True,
        ),
        # Khoi gia co ba hinh dang tren cung mot site: (1) co niem yet gia ->
        # `span.font-24px` + `<del>` gia truoc giam; (2) hang cong trinh ->
        # `span.sku` (ma san pham) + `span.font-24px` chua "Liên hệ"; (3) mot
        # `<span>` tran duy nhat chua "Liên hệ". Rule tren bat (1) va (2), rule
        # nay bat (3) - `:not(.sku)` de khong nhat ma san pham lam gia.
        SelectorRule(
            field="gia",
            selector="#price-preview > span:not(.sku)",
            is_price=True,
        ),
        SelectorRule(
            field="gia_doi_chieu",
            selector="#price-preview del",
            is_price=True,
        ),
        SelectorRule(
            field="ma_san_pham",
            selector="#price-preview span.sku",
            strip_prefix="Mã sản phẩm",
        ),
        # Hang cong trinh (danh muc "nhom-san-pham-cong trinh") duoc render
        # bang mot template KHAC: khong itemscope Product, khong og:image -
        # tang 1 tut xuong OpenGraph va mat luon anh. Anh van con trong the
        # `<meta itemprop="image">` dung tren template do, chi la khong co
        # itemscope bao ngoai nen khong bo parse structured data nao thay.
        SelectorRule(
            field="link_anh_san_pham",
            selector='meta[itemprop="image"]',
            attr="content",
        ),
    ],
    # denvinaled.vn (WooCommerce + Flatsome) KHONG co structured data san pham
    # nao: Yoast chi phat WebPage/BreadcrumbList, con WooCommerce thi tat khoi
    # Product JSON-LD. Tang 1 tut xuong tan OpenGraph - chi con ten va anh, mat
    # ca gia lan ma san pham du hai thu do deu hien ro tren trang.
    #
    # `p.price` co hai hinh dang: dang giam gia (<del> gia goc + <ins> gia ban)
    # va dang thuong (mot con so tran). Rule 1 bat dang giam gia, rule 2 bat
    # dang thuong - dat rule <ins> TRUOC vi o dang giam gia thi con so dau tien
    # trong `p.price` la gia GOC, lay nham thanh gia ban la sai ~35%.
    "denvinaled.vn": [
        SelectorRule(
            field="gia",
            selector=".product-info.summary p.price ins .woocommerce-Price-amount",
            is_price=True,
        ),
        SelectorRule(
            field="gia",
            selector=".product-info.summary p.price .woocommerce-Price-amount",
            is_price=True,
        ),
        SelectorRule(
            field="gia_doi_chieu",
            selector=".product-info.summary p.price del .woocommerce-Price-amount",
            is_price=True,
        ),
        SelectorRule(field="ma_san_pham", selector=".product_meta .sku"),
    ],
    # vne-led.vn (WooCommerce + Astra). JSON-LD duy nhat tren trang la
    # BreadcrumbList - khong co khoi Product nao, va trang cung KHONG phat the
    # OpenGraph nao, nen tang 1 tut het duong va tra ve moi mot category_1:
    # do tren 89 ban ghi dot dau, 89/89 mat ten san pham va anh du ca hai deu
    # hien ro tren trang. Ba rule duoi lay lai chung tu DOM WooCommerce chuan.
    #
    # KHONG dang ky rule `gia`: `.summary .price` co that nhung RONG tren moi
    # trang da do - VNE khong niem yet gia. De trong moi dung.
    #
    # Anh lay `data-large_image` (2560px) thay vi `src` - `src` chi la thumbnail
    # 600x600 do WooCommerce sinh ra, khong phai anh goc.
    # www.nanoco.com.vn (Next.js). JSON-LD duy nhat la BreadcrumbList; the
    # OpenGraph co nhung tang 1 khong dung duoc: `og:image` tro toi LOGO cong
    # ty (nanoco.com.vn/logo/nanoco.png) chu khong phai anh san pham - dang ky
    # no thi ca 48 san pham deu mang chung mot anh logo.
    #
    # Anh that lay bang link CDN TRUC TIEP. Trang con mot ban sao cua chinh anh
    # do qua proxy `/_next/image?url=...&w=3840` (URL da encode, kem tham so
    # kich thuoc) - bat theo tien to cloudfront thi luon duoc ban goc. Do:
    # 47/48 trang co, 48/48 trang co <h1>.
    #
    # Gia nam trong khoi vien cam "Gia ban le (chua VAT) : 187.273 VND". Day la
    # gia THAT do site cong bo, khong phai gia tham khao - nhung no CHUA VAT,
    # khac quy uoc cua cac site con lai (deu niem yet gia da gom VAT). Ghi
    # nguyen con so site cong bo, khong tu cong thue vao: quy doi la viec cua
    # nguoi doc so lieu, tool cong them 10% la tu bia ra mot con so khong site
    # nao noi. Do: 48/48 trang doc duoc.
    "www.nanoco.com.vn": [
        SelectorRule(field="ten_san_pham", selector="h1"),
        SelectorRule(
            field="gia",
            selector="div.border-orange-500 p b",
            is_price=True,
        ),
        SelectorRule(
            field="link_anh_san_pham",
            selector='img[src^="https://dk6k5ontqg6tx.cloudfront.net/variant-images/"]',
            attr="src",
        ),
    ],
    # www.mpe.com.vn: gia hien ro duoi nhan "Gia ban" nhung khong co structured
    # data nao mang no. `b.current` la con so dang ban; dat trong `p.price` de
    # khong nhat nham con so nao khac tren trang. Do: 90/90 trang doc duoc.
    "www.mpe.com.vn": [
        SelectorRule(
            field="gia",
            selector="div.product-price p.price b.current",
            is_price=True,
        ),
    ],
    # duhal.com.vn: khong co structured data san pham. Anh nam o `img.imgzoom`
    # (564/579 trang) va la anh GOC. Trang cung phat `og:image` tren 579/579
    # trang - nhung do la ban thu nho qua duong `/thumb/250x250/...`, dung no
    # thi ca dataset chi con anh 250px. Rule nay dat TRUOC nen `img.imgzoom`
    # duoc uu tien; 15 trang khong co no thi tang 1 da lay og:image roi.
    "duhal.com.vn": [
        SelectorRule(field="link_anh_san_pham", selector="img.imgzoom", attr="src"),
    ],
    "vne-led.vn": [
        SelectorRule(field="ten_san_pham", selector="h1.product_title"),
        SelectorRule(field="ma_san_pham", selector=".product_meta .sku"),
        SelectorRule(
            field="link_anh_san_pham",
            selector="figure.woocommerce-product-gallery__wrapper img",
            attr="data-large_image",
        ),
    ],
}


# Selector cac LINK DANH MUC tren trang san pham, theo thu tu tu tong quat ->
# cu the. Chi khop link danh muc, khong khop "Trang chủ" va khong khop chinh
# ten san pham - ba muc do se thanh category_1..3 y nguyen.
#
# Dang ky mot domain o day dong nghia voi mot ket luan da do duoc: breadcrumb
# trong structured data cua domain do SAI hoac VANG, nen no bi thay han chu
# khong phai chi va cho o trong. Hai truong hop da gap:
#
#   - dienquang.com: microdata Product khong kem BreadcrumbList nao -> tang 1
#     tra ve rong, trong khi trang co san `<ol class="breadcrumb">` day du.
#   - denvinaled.vn: JSON-LD BreadcrumbList CO, nhung cap giua luon la trang
#     "Cửa hàng" (shop) chu khong phai danh muc that - 668/668 san pham se roi
#     vao cung mot sheet "Cửa hàng" neu tin no. Danh muc that nam o khoi
#     `.product_meta .posted_in`, va o do mot san pham thuoc nhieu danh muc thi
#     co du ca ba cap.
DOMAIN_CATEGORY_SELECTORS: dict[str, str] = {
    "dienquang.com": 'ol.breadcrumb a[href*="/collections/"]',
    "denvinaled.vn": ".product_meta .posted_in a",
    # www.denasia.vn: cung benh voi denvinaled.vn, cung la WooCommerce. JSON-LD
    # khong co BreadcrumbList nao nen tang 1 tra ve rong -> 442/442 ban ghi mat
    # danh muc. Breadcrumb hien tren trang thi co, nhung cap giua luon la
    # "Shop" (Home > Shop > DIEN GIA DUNG > Am sieu toc), tin no thi ca site
    # roi vao mot sheet "Shop". Danh muc that nam o `.product_meta .posted_in`.
    "www.denasia.vn": ".product_meta .posted_in a",
    # www.mpe.com.vn: khong co structured data san pham -> tang 1 tra ve rong,
    # 90/90 ban ghi mat danh muc. Breadcrumb tren trang thi day du. Hai cap dau
    # ("Trang Chu" -> `/`, "San Pham" -> `/danh-sach-san-pham/`) la dieu huong
    # chung, loai bang chinh href co dinh cua chung; cap con lai la danh muc
    # that. Do: 90/90 trang bat duoc, ra 3 danh muc.
    "www.mpe.com.vn": '.breadcrumb a:not([href="/"]):not([href="/danh-sach-san-pham/"])',
    # www.lighting.philips.com.vn (AEM). Trang KHONG mang BreadcrumbList nao
    # trong structured data -> 2091/2091 ban ghi mat danh muc, tuc ca site don
    # vao mot sheet. Breadcrumb DOM thi day du 4 cap. Hai cap dau la dieu huong
    # chung va tro sang signify.com chu khong phai domain nay, nen loai bang
    # chinh duoi href cua chung. Do tren 300 trang: 300/300 bat duoc.
    #
    # Buoc theo class `breadcrumbs__item-link`: trong cung khoi `.breadcrumbs`
    # con hai link KHONG phai breadcrumb - "Quay lại dòng sản phẩm"
    # (`breadcrumbs__back-link`) va "Quay lại trang Pioneers of Light"
    # (`breadcrumbs__target-link`) - do la nut dieu huong nguoc, dung o cuoi
    # chuoi. Do tren 150 trang lay mau: 150/150 trang deu dinh ca hai, va tren
    # 24 ban ghi ma breadcrumb chi con mot cap thi "Quay lại dòng sản phẩm" da
    # bi ghi thang vao cot `category 2`.
    "www.lighting.philips.com.vn":
        '.breadcrumbs a.breadcrumbs__item-link'
        ':not([href$="/vi-vn/"]):not([href$="/vi-vn/prof"])',
    # roman.vn CO breadcrumb day du - `div.breadCrumbBox`, khong phai
    # `.breadcrumb`. Chu C viet hoa: cac dot khao sat truoc do tim bang
    # `[class*=breadcrumb]` (khop chu thuong, phan biet hoa thuong) nen ket
    # luan nham la "Roman khong co breadcrumb" va de trong 139/139 ban ghi.
    #
    # Loai "Trang chu" (`/`) va cap goc "San pham" (`san-pham.html`): giu cap
    # goc thi ca site roi vao mot sheet "San pham". Con lai la 3 cap that:
    # Thiet bi chieu sang - Led > Den noi that > Bong den LED Bulb.
    #
    # Breadcrumb con la thu DUY NHAT tach duoc san pham khoi bai viet tren
    # site phang nay - do tren 139 trang da tai: 92/94 san pham nam duoi
    # "San pham", va 0/45 trang rac nam duoi do (chung nam duoi "Thong tin"
    # hoac "Giai phap chieu sang"). Moi tin hieu NOI DUNG deu that bai o day
    # (xem docs/pipeline.md, muc "Trang phang").
    "roman.vn":
        '.breadCrumbBox a:not([href="/"]):not([href$="/san-pham.html"])',
    # duhal.com.vn: site phang thu hai, cung khong co structured data. Co
    # `div.breadcrumb` hai cap that (Den Led dan dung > BONG LED TUYP) sau khi
    # loai "Trang chu" (href `/`). Cap thu hai la trang product-tag cua
    # WooCommerce - van la danh muc that do site tu xep.
    "duhal.com.vn": '.breadcrumb a:not([href="/"])',
    # panasonic.net: khong co structured data. `div.breadcrumb` co 8 cap, trong
    # do bon cap dau la dieu huong toan site (Electric Works > Lighting >
    # Tieng Viet > San pham) va cap cuoi la MA MODEL cua chinh san pham.
    #
    # Loc theo <li> chu khong theo <a>: hai trong ba cap danh muc that KHONG
    # phai link ("Den duong", "Den duong SP" khong co the <a> nao), lay theo
    # <a> thi mat chung. Bon cap dieu huong deu tro toi duong dan tuyet doi
    # `/electricworks/...`, con cap danh muc that tro toi `./plist.php?lay3=`
    # hoac khong tro dau ca - do la thu phan biet duoc chung.
    #
    # Cap cuoi (ma model) khong bi loai boi selector, no roi ra ngoai vi
    # extract_categories chi lay ba cap dau. Do: 147/147 trang bat duoc.
    "panasonic.net": '.breadcrumb li:not(:has(a[href^="/electricworks/"]))',
    # philipsvietnam.com (WooCommerce): JSON-LD co Product nhung khong co
    # BreadcrumbList -> tang 1 khong ra danh muc. Breadcrumb DOM thi day du,
    # chi phai bo "Trang chu".
    "philipsvietnam.com": '.woocommerce-breadcrumb a:not([href="https://philipsvietnam.com"])',
    "panasonicvn.com.vn": '.woocommerce-breadcrumb a:not([href="https://panasonicvn.com.vn"])',
}


def extract_categories(
    html: str, domain: str, page_url: Optional[str] = None
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """(category_1, category_2, category_3) doc tu DOM theo selector cua
    `domain`. Domain chua dang ky -> (None, None, None), ben goi giu nguyen ket
    qua tang 1.

    `page_url` dung de bo cap breadcrumb tro ve CHINH TRANG DANG DOC - cap cuoi
    cua roman.vn la ten san pham va no la mot the <a> y het cac cap danh muc,
    khong selector nao tach duoc. Truoc day no tu roi ra ngoai vi chi lay 3 cap
    dau; tu khi cac cap dieu huong dau bi cat (xem `anchor_categories`) thi no
    doi len va se bi ghi vao cot category. Doi chieu bang chinh URL la cach duy
    nhat chac chan, va dung cho moi site chu khong rieng roman.vn.
    """
    selector = DOMAIN_CATEGORY_SELECTORS.get(domain)
    if not selector:
        return None, None, None

    self_url = (page_url or "").rstrip("/")
    soup = BeautifulSoup(html, "lxml")
    names: list[str] = []
    for el in soup.select(selector):
        href = el.get("href") if el.name == "a" else None
        if self_url and href and str(href).rstrip("/") == self_url:
            continue
        name = " ".join(el.get_text(" ", strip=True).split())
        if name and name not in names:
            names.append(name)
    return anchor_categories(names, domain)


# Gia tri "gia" ma site dung lam CHO TRONG chu khong phai gia that. KingLED tra
# `<meta itemprop="price" content="0">` cho san pham khong niem yet gia, va
# trang cua chung khong render khoi gia nao ca. Ghi 0 vao cot Gia thi nguoi doc
# hieu la "mien phi" - sai han y cua nguon; con ep thanh "Liên hệ" thi la tu
# dat loi vao mieng site (trang khong he noi vay). Nen coi nhu CHUA phan giai
# duoc: tang 1.5 duoc quyen doc lai tu DOM, khong duoc thi de o trong va ban
# ghi tu roi xuong partial-missing-fields de nguoi review nhin thay.
DOMAIN_PLACEHOLDER_PRICES: dict[str, tuple[float, ...]] = {
    "kingled.com.vn": (0.0,),
    # dienquang.com khai `<meta itemprop="price" content="0">` cho MOI san
    # pham, ke ca san pham dang hien 279.000d ngay tren trang (do tren 8 trang:
    # 8/8 khai 0, trong do 3 co gia that). Day khong phai gia - no la gia tri
    # mac dinh cua template. De nguyen thi ca 741 san pham vao file voi cot Gia
    # = 0.
    "dienquang.com": (0.0,),
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
    # denvinaled.vn khong co the <table> nao tren ca trang san pham: thong so
    # nam trong mo ta ngan duoi dang `<strong>Công suất:</strong> 9W<br>`. Khoi
    # nay chi boc san pham dang xem (khoi "san pham lien quan" dung the khac),
    # nhung van phai khoanh vung vi cap "nhan: gia tri" la mot hinh dang qua
    # pho bien de quet ca trang.
    "denvinaled.vn": "div.product-short-description",
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
    # Luoi "Sản phẩm tương tự" cuoi trang denvinaled.vn: moi the la mot san
    # pham KHAC kem ten + gia rieng. Sidebar "Sản phẩm mới nhất" cung dang the
    # nhung nam trong <aside> nen da bi html_cleaner go san.
    "denvinaled.vn": ".related",
}


# Khoi MO TA san pham cua site. Khac han hai bang tren: chung khoanh vung de
# DOC mot field, con bang nay tra loi "neu trang khong co MUC uu diem thi doan
# nao la uu diem".
#
# Ly do can no, do tren trang that: nhieu site khong co muc uu diem nao - chung
# chi co MOT DOAN MO TA, va chinh doan do la uu diem:
#
#   denvinaled.vn  "...chat luong cao, tuoi tho lau nam. Phu kien ket noi
#                   driver toi thanh ray nam cham. Bao hanh 2 nam toan quoc."
#   nanoco         "Bo mang Den LED T8 co chi phi tiet kiem hon khi chung ta
#                   mua le... Phan than mang duoc cau tao tu thep..."
#
# Dang ky o day dong nghia voi mot ket luan da do duoc tren domain do. KHONG
# suy doan cho site chua khao sat: domain vang mat thi nhanh du phong nay tat
# han, y nhu truoc.
DOMAIN_DESCRIPTION_SELECTORS: dict[str, str] = {
    "denvinaled.vn": "#tab-description",
    # vne-led.vn CO `#tab-description` tren 40/40 trang, nhung trong do chi la
    # bang thong so viet doc, khong mot cau nao. Van dang ky: chinh chot chan
    # `_mo_ta_la_uu_diem` se tu choi no (do duoc 0/40 qua chot), va giu entry
    # o day ghi lai rang da khao sat roi - khong phai domain bi bo quen.
    "vne-led.vn": "#tab-description",
    # www.denasia.vn: khoi `.thongSoNhanh` la danh sach ban hang cua site,
    # gach dau dong bang dau "–": "– Thiết kế hiện đại, sang trọng. – Dễ dàng
    # sử dụng. – Thân ấm được làm bằng inox siêu bền...". Ten class noi "thong
    # so" nhung noi dung that la tron ca uu diem lan thong so.
    "www.denasia.vn": ".thongSoNhanh",
    "roman.vn": "div.nd",
    # www.nanoco.com.vn: Tailwind Typography (`.prose`) boc doan mo ta.
    "www.nanoco.com.vn": ".prose",
    "philipsvietnam.com": "#tab-description",
    "panasonicvn.com.vn": "#tab-description",
}

# KHONG dang ky duhal.com.vn: do tren 3 trang san pham that, khong trang nao co
# doan mo ta - chi co ghi chu VAT/van chuyen dung chung. De trong moi dung.


def get_description_selector(domain: str) -> Optional[str]:
    """Selector khoi mo ta cua `domain`, None neu chua dang ky."""
    return DOMAIN_DESCRIPTION_SELECTORS.get(domain)


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
        if raw_value and rule.strip_prefix:
            head, sep, tail = raw_value.partition(":")
            if sep and head.strip().casefold() == rule.strip_prefix.casefold():
                raw_value = tail.strip()
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
