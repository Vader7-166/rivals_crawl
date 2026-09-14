"""Neo breadcrumb ve dung CAP LOAI SAN PHAM. Dung chung cho tang 1 va tang 1.5.

Van de do duoc tren 4 site (dot 10/09): cot `category 1` - thu quyet dinh moi
sheet cua file Excel - khong cung mot NGHIA giua cac site. TLC de loai san pham
ngay o cap dau ("Đèn LED âm trần"), con nhieu site khac danh cap dau cho mot
thung dieu huong chung, loai san pham that nam sau no mot hoac hai cap:

    tlclighting.com.vn   Đèn LED âm trần
    panasonicvn.com.vn   Đèn Led            > Đèn LED Âm Trần Panasonic
    lighting.philips     Bộ đèn trong nhà   > Đèn âm trần > GreenSpace G6
    roman.vn             Thiết bị chiếu sáng - Led > Đèn nội thất > Đèn Downlight LED
    nanoco               Danh Mục > Chiếu Sáng > Đèn chiếu sáng > Bóng LED Bulb

Hau qua: ca 441 den cua Panasonic don vao mot sheet "Đèn Led", 1.855 san pham
Philips don vao "Bộ đèn trong nhà" - dung file nhung vo dung de so sanh, vi
nguoi doc can biet den am tran cua doi thu so voi den am tran cua minh, khong
phai "den" so voi "den".

HAI CACH DOC MOT CHUOI, khai bang `CATEGORY_ANCHOR`:

    "top"  (mac dinh) - lay tu cap DAU xuong, toi da 3 cap (tong quat -> cu the).
    "leaf"             - dem NGUOC tu cap sat san pham len, toi da 3 cap
                         (cu the -> tong quat).

Khong cach nao dung cho moi site, vi cay danh muc moi site DUNG O MOT TANG
NGHIA KHAC NHAU. Do tren HTML that:

    | Site           | Cap sat san pham thuc chat la gi        |
    |----------------|-----------------------------------------|
    | nanoco         | LOAI      Bóng LED Bulb                 |
    | panasonicvn    | LOAI      Đèn LED Âm Trần Panasonic     |
    | roman          | KIEU DANG Đèn downlight nhôm tỳ         |
    | philips        | DONG HANG GreenSpace Flex Luna          |
    | panasonic.net  | MA DONG   Ex-F, Ex 2G, DN 2G IP44       |
    | kingled        | qua vun - 108 sheet cho 549 san pham    |

Nen "leaf" chi bat cho site da do; mac dinh "top" giu nguyen ket qua cua 10
site con lai (kingled 24 sheet, panasonic.net 6 sheet, TLC 36 sheet...).

Cai duoc khai o day la MOT TU CHO MOI SITE - "doc tu dau" hay "doc tu duoi" -
chu khong phai danh sach ten danh muc. Khac biet dang ke: mot danh sach ten se
chet am tham khi site doi ten danh muc, con huong doc thi khong phu thuoc vao
chu nghia nao cua site.

KHONG anh xa sang taxonomy khac va khong dat them ten moi. Moi chu trong ba cot
category deu la chu cua chinh site nguon (spec product-record-schema, muc
"Category giu nguyen theo site nguon").
"""
from __future__ import annotations

from typing import Optional

# Site doc chuoi breadcrumb TU DUOI LEN. Chi ke site da do tren trang that.
#
# Danh o day nghia la da xac nhan: cay danh muc cua site KHONG dung lai o cap
# loai, nen cap dau chi la thung dieu huong.
#
#   panasonicvn  "Đèn Led" om 441/604 san pham, cap sau no moi la loai. Doi lai,
#                nhanh cong tac cho ra ten DONG hang (DÒNG WIDE, Dòng Halumie)
#                thay vi "Công Tắc Ổ Cắm" - chap nhan duoc: sheet van gom dung
#                san pham, chi la ten rieng hon.
#   philips      Cap sat san pham la dong hang (GreenSpace Flex Luna 65 SP,
#                LuxSpace Pro 26 SP) - moi sheet van la mot nhom san pham that.
#   roman        Cap sat san pham la kieu dang (Downlight siêu mỏng, Đèn
#                downlight nhôm tỳ) - chia min hon "Đèn Downlight LED".
#   nanoco       Cap sat san pham dung la loai. Do ca hai huong: ket qua GIONG
#                HET nhau (9 sheet), nhung "leaf" thi khong phai khai ten nao.
CATEGORY_ANCHOR: dict[str, str] = {
    "panasonicvn.com.vn": "leaf",
    "www.lighting.philips.com.vn": "leaf",
    "roman.vn": "leaf",
    "www.nanoco.com.vn": "leaf",
}

_MAC_DINH = "top"


def anchor_categories(
    labels: list[str], domain: str
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """(category_1, category_2, category_3) tu chuoi breadcrumb DA bo "Trang
    chu", cap goc "San pham" va chinh ten san pham.

    Site "leaf" DEM NGUOC de CHON ba cap gan san pham nhat, nhung DIEN LAI theo
    dung thu tu goc cua site - tong quat -> cu the, y nhu breadcrumb hien tren
    trang ("Trang chủ / Đèn Led / Đèn LED Búp Panasonic"):

        Bộ đèn trong nhà > Đèn Highbay và Lowbay > Trần cao > ...Rectangular
          category 1 = Đèn Highbay và Lowbay
          category 2 = Trần cao
          category 3 = ...Rectangular      (cap sat san pham)

    Chi cap DAU bi bo, va chi khi chuoi sau hon ba cap. Dao nguoc ca thu tu thi
    ba cot doc thanh cu the -> tong quat, nguoc han quy uoc cua khuon tham chieu
    va nguoc han cach chinh site trinh bay.

    Site "top" lay ba cap dau, cung thu tu goc.

    Luu y: ten sheet KHONG con lay tu `category 1` cho site "leaf" - xem
    `sheet_category`.
    """
    if not labels:
        return None, None, None

    lay = labels[-3:] if CATEGORY_ANCHOR.get(domain, _MAC_DINH) == "leaf" else labels[:3]
    padded = (lay + [None, None, None])[:3]
    return padded[0], padded[1], padded[2]


def sheet_category(
    cat_1: Optional[str],
    cat_2: Optional[str],
    cat_3: Optional[str],
    domain: str,
) -> Optional[str]:
    """Cap danh muc dung lam TEN SHEET - tuc "loai san pham" cua site do.

    Khong the luon lay `category 1`: sau khi ba cot duoc dien theo thu tu goc
    (tong quat -> cu the), cot 1 cua site "leaf" quay ve chinh thung dieu huong
    - "Đèn Led" om lai 441/604 san pham Panasonic. Loai san pham cua nhung site
    do nam o cap SAU CUNG co du lieu.

    Nguoc lai, site "top" phai giu `category 1`: cay cua chung da dat loai san
    pham ngay o cap dau, lay cap cuoi thi TLC ra sheet "COB" thay vi "Đèn LED
    âm trần", KingLED no tu 24 thanh 108 sheet cho 549 san pham.
    """
    if CATEGORY_ANCHOR.get(domain, _MAC_DINH) == "leaf":
        return cat_3 or cat_2 or cat_1
    return cat_1


# Nhanh breadcrumb ma chinh site khai la KHONG PHAI san pham. Ten lay NGUYEN VAN
# tu breadcrumb cua site, khong phai tu khoa doan mo.
#
# Van de do duoc tren kho (dot 11/09): 68 ban ghi cua Roman va Duhal la BAI VIET
# chu khong phai san pham - "10 thông số đèn led quan trọng cần nắm được khi
# mua", "Cách Chọn Đèn LED Trang Trí Phòng Ngủ...". Ca hai site de moi trang o
# `/<slug>.html` nen hinh URL khong tach duoc, va ca hai deu nhac du cong suat /
# quang thong / dien ap / nhiet do mau / CRI nen vuot moi nguong thong so.
#
# Bay cua bai toan nay, da do va ghi lai o crawl_list.md: 7 luat loc tren 80
# trang Roman, KHONG luat nao sach. Luat nghe hop ly nhat - "khong ma va khong
# gia thi khong phai san pham" - vut ca den duong TLC that va 422 URL Philips
# that. Tuc moi luat SUY DOAN tu noi dung deu tra gia bang san pham that.
#
# Cai khong phai suy doan: chinh doi thu da xep bai viet vao mot nhanh rieng va
# noi ra dieu do trong breadcrumb. Doc lai lop khai bao cua ho re hon va dung
# hon moi thuoc do noi dung - va khi ho doi ten nhanh, hau qua la mot dong du
# lieu o day phai sua, khong phai mot nguong phai hieu chinh lai.
#
# Dieu kien de them mot dong vao day: da MO trang do ra xem va xac nhan no la
# bai viet. Khong duoc suy tu ten nhanh nghe giong tin tuc.
DOMAIN_NON_PRODUCT_BRANCHES: dict[str, tuple[str, ...]] = {
    # 48 bai viet + 5 trang gioi thieu giai phap, da doi chieu tung ten.
    "roman.vn": ("Thông tin", "Giải pháp chiếu sáng"),
    # 15 bai viet.
    "duhal.com.vn": ("Tin tức",),
}


def non_product_branch(
    cat_1: Optional[str],
    cat_2: Optional[str],
    cat_3: Optional[str],
    domain: str,
) -> Optional[str]:
    """Ten nhanh khien trang nay KHONG phai san pham, hoac None.

    So khop tren ca ba cot chu khong rieng cot 1: site "leaf" dem nguoc tu cap
    sat san pham len, nen nhanh goc cua no roi vao cot nao la tuy do dai chuoi
    breadcrumb cua tung trang.

    So khop CHINH XAC tung ky tu, khong phai chuoi con: `Tin tức` phai khong
    duoc cham vao mot danh muc that ten `Đèn tin tức`(*), va quan trong hon la
    khong duoc cham vao danh muc cua site KHAC - moi domain chi doc danh sach
    cua chinh no.

    (*) chua site nao co danh muc nhu vay; rang buoc nay la de phong, vi gia
    phai tra cho mot lan khop nham la mot san pham that bien mat khoi file ket
    qua ma khong ai thay.
    """
    branches = DOMAIN_NON_PRODUCT_BRANCHES.get(domain)
    if not branches:
        return None
    for value in (cat_1, cat_2, cat_3):
        if value and value in branches:
            return value
    return None


__all__ = [
    "CATEGORY_ANCHOR",
    "DOMAIN_NON_PRODUCT_BRANCHES",
    "anchor_categories",
    "non_product_branch",
    "sheet_category",
]
