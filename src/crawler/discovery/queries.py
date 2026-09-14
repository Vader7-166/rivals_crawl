"""Tu khoa nao thi tim ra web LED - phan CUSTOM duoc cua bo tim kiem.

DO THAT tren Bing ngay 11/09/2026, 10 ket qua dau moi truy van:

    tu khoa                                 ra gi
    ---------------------------------------------------------------------
    "đèn led âm trần"                       10/10 domain dung nganh
    "công ty sản xuất đèn led"              vietjack, dichvucong.gov.vn,
                                            wiktionary - 0 site LED
    "thương hiệu đèn led việt nam"          youtube, wikipedia, nhac.vn
                                            - 0 site LED
    "thiết bị chiếu sáng led nhà sản xuất"  tu dien, tratu.soha.vn - 0 site

KET LUAN, va day la ly do file nay ton tai: truy van phai la TEN LOAI HANG cu
the, khong phai mo ta loai hinh doanh nghiep. Bing tach tu tieng Viet kem nen
"công ty", "thương hiệu", "nhà sản xuất" keo no ve tu dien va dich vu cong.
Truc giac "muon tim nha san xuat thi go chu nha san xuat" la SAI o day, va sai
theo kieu im lang - van tra ve 10 ket qua, chi la khong co cai nao dung.

Tu vung dung de go thi KHONG PHAI BIA RA: 254 ten `category_1` trong kho la tu
vung that cua nganh, do chinh doi thu viet. Dung lai chung vua dung hon mot
danh sach tu nghi ra, vua tu lon len moi lan crawl them mot site.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from ..search import normalise

# Tu khoa neo: moi truy van deu phai mang mot trong so nay, neu khong Bing
# truot khoi nganh (do that: "âm trần" mot minh ra tran thach cao, "panel" ra
# tam panel xay dung).
TU_NEO: tuple[str, ...] = ("đèn led", "led")

# Truy van mac dinh khi chua co du lieu danh muc nao trong kho - vd lan chay
# dau tien. Deu la TEN LOAI HANG, theo dung ket luan o tren.
TRUY_VAN_MAC_DINH: tuple[str, ...] = (
    "đèn led âm trần",
    "đèn led panel",
    "đèn led downlight",
    "đèn led nhà xưởng",
    "đèn đường led",
    "bóng đèn led bulb",
)


def tu_danh_muc(
    ten_danh_muc: Iterable[str],
    *,
    so_luong: int = 6,
    it_nhat: int = 8,
) -> list[str]:
    """Ten danh muc trong kho -> danh sach truy van.

    Ba buoc, moi buoc sua mot loi da do duoc khi chay that:

    1. BO TEN NHAN ra khoi truy van. Kho day nhung ten kieu "Đèn LED Âm Trần
       VinaLED", "Đèn led âm trần Philips" - go nguyen ca cum thi chi ra dung
       site cua chinh nhan do, tuc khong tim duoc ai moi, dung muc dich cua ca
       cong cu. Do that: lan chay dau tien cho ra ledxanh/kingled.vn/flexhouse
       thay vi paragon/haledco.
    2. XEP THEO DO PHO BIEN. Mot ten danh muc xuat hien o NHIEU doi thu la mot
       loai hang ca nganh cung ban - go no thi keo ra nhieu nha san xuat. Lay 6
       cai dau danh sach thi phu thuoc vao thu tu alphabet cua domain.
    3. LOAI ten qua ngan / khong mang tu neo: "Đèn Led", "SP Khác" qua chung;
       "Thiết Bị Điện Thông Minh", "Quạt trần" thi tim ra nganh khac.

    Dau vao thuong co LAP (moi domain mot dong cho cung mot loai hang) - chinh
    so lan lap la thuoc do do pho bien o buoc 2, nen dung bo trung truoc khi
    goi ham nay.
    """
    from ..sites.registry import SITE_PROFILES

    # Ten nhan da biet, dai truoc ngan sau: cat "Panasonic Lighting" truoc khi
    # cat "Panasonic", neu khong con lai chu "Lighting" lung lung.
    nhan = sorted(
        {t for p in SITE_PROFILES.values()
         for t in [p.brand_name, *p.brand_aliases] if t},
        key=len, reverse=True,
    )

    dem: dict[str, int] = {}
    goc: dict[str, str] = {}
    for ten in ten_danh_muc:
        if not ten:
            continue
        sach = ten
        for n in nhan:
            sach = re.sub(re.escape(n), " ", sach, flags=re.IGNORECASE)
        sach = " ".join(sach.split())
        if len(sach) < it_nhat:
            continue
        chuan = normalise(sach)
        if not any(normalise(neo) in chuan for neo in TU_NEO):
            continue
        dem[chuan] = dem.get(chuan, 0) + 1
        goc.setdefault(chuan, sach)

    xep = sorted(dem, key=lambda k: (-dem[k], k))
    ra = [goc[k] for k in xep[:so_luong]]
    return ra or list(TRUY_VAN_MAC_DINH[:so_luong])


def tim_lai_nhan(
    ten_nhan: str, *, loai_hang: Optional[str] = None
) -> list[str]:
    """Truy van de TIM LAI site cua mot nhan da biet (domain cu chet/doi).

    Khac han truy van tim doi thu moi: o day ta biet ten nhan va can dia chi
    moi cua chinh no, nen ten nhan phai nam trong truy van. Van kem tu neo -
    "Roman" mot minh ra lich su La Ma, "Asia" ra chau A.
    """
    hang = loai_hang or TU_NEO[0]
    return [
        f"{ten_nhan} {hang}",
        f"{ten_nhan} {hang} chính hãng",
        f'"{ten_nhan}" website chính thức {hang}',
    ]


__all__ = ["TRUY_VAN_MAC_DINH", "TU_NEO", "tim_lai_nhan", "tu_danh_muc"]
