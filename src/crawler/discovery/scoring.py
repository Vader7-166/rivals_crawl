"""Cham diem mot domain ung vien: day co phai web LED cua NHA SAN XUAT khong.

NGUYEN TAC, rut ra tu chinh bai hoc da ghi trong crawl_list.md ("7 luat loc
tren 80 trang Roman, khong luat nao sach"): KHONG luat nao o day duoc tu dong
vut mot ung vien vi mot phan doan ve noi dung. Cai duy nhat duoc loai thang la
nhung tap DONG, kiem chung duoc bang mat: san TMDT, mang xa hoi, tu dien.

Phan con lai la DIEM kem LY DO, va nguoi dung bam duyet. Do la cung hinh voi
man xac nhan pham vi da co: khop truot thi bo tick, gia sua bang mot cu bam.

Vi sao khong dam tu dong: da do that ngay 11/09/2026, luat "nhieu nhan tren
trang chu = dai ly" sai ca hai chieu:

    kingled.com.vn        5 nhan  -> NHA SAN XUAT that (trang chu co muc so
                                     sanh nhac ten doi thu)
    ledhome.vn            0 nhan  -> DAI LY that (trang chu render bang JS,
                                     httpx thuan khong thay chu nao)

Mot luat sai ca hai chieu ma van duoc de tu dong quyet thi no vua bo sot doi
thu that, vua keo dai ly vao kho - va ca hai deu im lang.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Optional

from ..probing.detection import analyze_page
from ..search import normalise

logger = logging.getLogger(__name__)

# Tap DONG, loai thang. Ba nhom, moi nhom mot ly do khac nhau:
#
#   san TMDT   ban hang cua NHIEU nhan, gia da qua tay dai ly - so lieu khong
#              tin duoc (nguyen tac dau tien cua crawl_list.md)
#   mang xa hoi / video   khong co catalogue san pham
#   tu dien / bach khoa / dich vu cong   rac ma chinh Bing keo vao khi truy van
#              mang tu truu tuong (xem queries.py)
TEN_MIEN_LOAI_THANG: frozenset[str] = frozenset({
    "shopee.vn", "lazada.vn", "tiki.vn", "sendo.vn", "chotot.com", "vatgia.com",
    "facebook.com", "youtube.com", "music.youtube.com", "tiktok.com",
    "instagram.com", "twitter.com", "x.com", "linkedin.com", "pinterest.com",
    "wikipedia.org", "wiktionary.org", "vietjack.com", "dichvucong.gov.vn",
    "tratu.soha.vn", "vtudien.com", "hvdic.thivien.net", "tudientiengviet.org",
    "lyricvn.com", "nhac.vn", "akinator.com", "amazon.com", "alibaba.com",
    "google.com", "bing.com",
    # Bao va trang tai chinh. Them vao sau khi do that: tim lai nhan "VNE" cho
    # ra finance.vietstock.vn, cafef.vn, vnetrust.vn - vi "VNE" con la ma co
    # phieu. Bai bao ve mot doanh nghiep san xuat thi dat het tin hieu tu vung
    # nha san xuat ("sản xuất", "xuất khẩu", "nghiên cứu") ma khong phai site
    # cua ho, nen day la tap PHAI loai thang chu khong the cham diem.
    "cafef.vn", "vietstock.vn", "finance.vietstock.vn", "vneconomy.vn",
    "vnexpress.net", "tuoitre.vn", "thanhnien.vn", "dantri.com.vn",
    "24h.com.vn", "baodautu.vn", "nguoiquansat.vn", "vietnamnet.vn",
    "tienphong.vn", "laodong.vn", "kinhtedothi.vn", "markettimes.vn",
})

# TU VUNG cua hai loai site. Day la tin hieu DUY NHAT o day nham dung cau hoi
# "nha san xuat hay dai ly" - hai tin hieu de nghi truoc do deu da bi do va
# loai:
#
#   "co trang san pham that"     -> dai ly nao cung dat (ledxanh: 506 lan nhac
#                                   so tien). No tach duoc "site ban hang" voi
#                                   "blog/wiki", khong tach duoc NSX voi dai ly.
#   "ten mien mang tu rieng"     -> `ledxanh`, `thegioidentrangtri` duoc diem y
#                                   het `kingled`, vi ca ba deu la mot tu ghep
#                                   lien khong tach duoc. Tin hieu vo dung.
#
# Do that ngay 11/09/2026 tren trang chu, dem so tu khoa moi nhom xuat hien:
#
#   site                        that la   NSX  dai ly  chenh
#   rangdong.com.vn             NSX         5       3     +2
#   paragon.com.vn              NSX         6       4     +2
#   www.mpe.com.vn              NSX         2       0     +2
#   duhal.com.vn                NSX         5       4     +1
#   kingled.com.vn              NSX         6       6      0   <- mo
#   ledxanh.vn                  dai ly      2       2      0   <- mo
#   hoangphatlighting.vn        dai ly      0       2     -2
#   thegioidentrangtri.com      dai ly      1       4     -3
#   ledhome.vn                  dai ly      0       5     -5
#
# Tach dung 7/9, hai ca con lai roi vao vung 0 - tuc khong ai bi day sai huong,
# chi la khong duoc giup. Do la ly do diem o day CHIA MUC chu khong ty le
# thuan voi chenh lech: vung mo phai tra ve 0 diem, khong phai mot phan doan.
TU_VUNG_NHA_SAN_XUAT: frozenset[str] = frozenset({
    "nhà máy", "dây chuyền", "sản xuất", "nghiên cứu", "công nghệ sản xuất",
    "iso 9001", "chứng nhận", "nhà sản xuất", "r&d", "xuất khẩu", "tiêu chuẩn",
})
TU_VUNG_DAI_LY: frozenset[str] = frozenset({
    "giao hàng", "freeship", "miễn phí vận chuyển", "showroom", "đại lý",
    "phân phối", "giỏ hàng", "thêm vào giỏ", "đặt hàng", "khuyến mãi",
    "giá tốt", "chính hãng giá",
})


@dataclass
class TinHieu:
    """Mot tin hieu da do, kem diem va cau giai thich cho nguoi doc."""

    ten: str
    diem: int
    ly_do: str


@dataclass
class UngVien:
    domain: str
    title: str = ""
    url: str = ""
    # Cac truy van da keo domain nay ra, kem thu hang tot nhat.
    truy_van: list[str] = field(default_factory=list)
    hang_tot_nhat: int = 99
    tin_hieu: list[TinHieu] = field(default_factory=list)
    # Domain da co trong registry. KHONG loai: voi muc dich "tim lai site da
    # doi", chinh viec no con song la cau tra loi can biet.
    da_dang_ky: bool = False
    bi_loai: Optional[str] = None

    @property
    def diem(self) -> int:
        return sum(t.diem for t in self.tin_hieu)

    @property
    def giai_thich(self) -> str:
        return " · ".join(f"{t.ly_do} ({t.diem:+d})" for t in self.tin_hieu)


def _goc_ten_mien(domain: str) -> str:
    return domain.lower().removeprefix("www.")


def ly_do_loai(domain: str, *, cua_minh: Iterable[str] = ()) -> Optional[str]:
    """Ly do loai thang ung vien, hoac None.

    Chi dua tren tap DONG - khong phan doan noi dung.
    """
    goc = _goc_ten_mien(domain)
    if any(goc == normalise(m) or goc.endswith("." + normalise(m)) for m in cua_minh if m):
        # Trang cua CHINH MINH. Khong loai thi no chiem mot suat trong top 3 o
        # gan nhu moi truy van (do that: rangdong.com.vn dung hang 2 cho "đèn
        # led âm trần") va day mot doi thu that ra ngoai.
        return "Trang của chính mình, không phải đối thủ"
    for xau in TEN_MIEN_LOAI_THANG:
        if goc == xau or goc.endswith("." + xau):
            return f"Sàn TMĐT / mạng xã hội / từ điển ({xau})"
    return None


def cham_diem(
    ung_vien: UngVien,
    *,
    html_trang_chu: Optional[str] = None,
    html_trang_mau: Optional[str] = None,
    ten_nhan_da_biet: Iterable[str] = (),
    ten_nhan_can_tim: Optional[str] = None,
) -> UngVien:
    """Do cac tin hieu va gan diem. Khong tin hieu nao tu loai ung vien.

    `html_trang_mau` la mot trang BAT KY cua site (thuong la ket qua tim kiem
    tro thang vao trang san pham). Do la tin hieu MANH nhat va dung lai dung bo
    phat hien da co o tang 0 - khong dung mot thuoc do thu hai co the lech voi
    no.
    """
    # 1. Thu hang tren trang ket qua - diem NHO CO CHU DICH.
    #
    #    Thu hang do SEO, va do that: dai ly dau tu SEO manh hon nha san xuat.
    #    De tin hieu nay nang ngang tin hieu loai hinh thi no THUONG dung cai ta
    #    dang muon loai - da thay that: ledxanh.vn (dai ly) dung dau chi nho
    #    hang 1 cong "ra o 6 tu khoa", trong khi haledco.com (co xuong san
    #    xuat) tut xuong.
    if ung_vien.hang_tot_nhat <= 3:
        ung_vien.tin_hieu.append(TinHieu(
            "hang", 1, f"Hạng {ung_vien.hang_tot_nhat} trên trang kết quả"))
    if len(ung_vien.truy_van) > 2:
        ung_vien.tin_hieu.append(TinHieu(
            "phu", 1, f"Ra ở {len(ung_vien.truy_van)} từ khoá khác nhau"))

    # 2. Co trang san pham THAT. Tin hieu manh nhat, va la thu duy nhat o day
    #    kiem chung bang chinh noi dung trang chu khong phai bang ten mien.
    if html_trang_mau:
        tin = analyze_page(html_trang_mau)
        if tin.product_structured_data_count > 0:
            # STRUCTURED DATA la tin hieu manh nhat o day, va manh vi mot ly do
            # RAT THUC DUNG voi chinh du an nay: tang 1 doc structured data:
            # site co no la site crawl duoc ngay, khong phai hieu chinh
            # selector. Do cung la thu ma trang ban le dung nen tang thuong
            # khong co - chung to gia bang HTML de hien thi, khong de may doc.
            ung_vien.tin_hieu.append(TinHieu(
                "structured_data", 3,
                f"Trang sản phẩm có {tin.product_structured_data_count} block "
                "structured data — crawl được ngay bằng tầng 1"))
        elif tin.looks_like_single_product_page:
            # Chi co so tien: chung minh "site co ban hang", tuc loai duoc
            # blog/wiki - nhung dai ly nao cung dat (ledxanh: 506 lan nhac so
            # tien), nen no khong duoc du manh de mot minh lat ket qua.
            ung_vien.tin_hieu.append(TinHieu(
                "san_pham", 1,
                f"Trang có giá ({tin.price_amount_mentions} lần nhắc số tiền) "
                "nhưng không có structured data"))
        elif tin.spec_field_count >= 3:
            ung_vien.tin_hieu.append(TinHieu(
                "thong_so", 1,
                f"Trang có {tin.spec_field_count} trường thông số kỹ thuật"))
        else:
            ung_vien.tin_hieu.append(TinHieu(
                "san_pham", -2,
                "Trang lấy mẫu không có dấu hiệu trang sản phẩm"))

    # 3. TU VUNG tren trang chu - tin hieu duy nhat nham dung cau hoi "nha san
    #    xuat hay dai ly". Xem bang do o dau file.
    if html_trang_chu:
        chuan_hoa = normalise(html_trang_chu)
        so_nsx = sum(1 for k in TU_VUNG_NHA_SAN_XUAT if normalise(k) in chuan_hoa)
        so_dl = sum(1 for k in TU_VUNG_DAI_LY if normalise(k) in chuan_hoa)
        chenh = so_nsx - so_dl
        # Doi IT NHAT 3 dau hieu san xuat chu khong chi doi chenh lech duong.
        # Do that: mot bai bao tai chinh dat chenh +2 voi dung hai chu "sản
        # xuất" va "nghiên cứu" - tuc nguong chi-can-chenh-lech thuong ca nhung
        # trang khong phai site doanh nghiep.
        if chenh >= 1 and so_nsx >= 3:
            ung_vien.tin_hieu.append(TinHieu(
                "tu_vung", 4,
                f"Nói ngôn ngữ nhà sản xuất ({so_nsx} dấu hiệu sản xuất / "
                f"{so_dl} dấu hiệu bán lẻ)"))
        elif chenh <= -2:
            ung_vien.tin_hieu.append(TinHieu(
                "tu_vung", -4,
                f"Nói ngôn ngữ bán lẻ ({so_dl} dấu hiệu bán lẻ / "
                f"{so_nsx} dấu hiệu sản xuất)"))
        # chenh trong khoang (-2, 1): KHONG cham diem. Do la vung ma phep do
        # nay da duoc chung minh la khong phan biet duoc (kingled va ledxanh
        # cung roi vao day), va doan bua o vung mo thi te hon la im lang.

    # 4. So nhan hieu tren trang chu. DIEM NHE co chu dich: da do la luat nay
    #    sai ca hai chieu (kingled 5 nhan van la nha san xuat; ledhome 0 nhan
    #    van la dai ly). Giu lai vi no van dung o phan lon ca, nhung khong bao
    #    gio duoc du mot minh de lat ket qua.
    if html_trang_chu:
        chuan = normalise(html_trang_chu)
        thay = {n for n in ten_nhan_da_biet if n and normalise(n) in chuan}
        if len(thay) >= 4:
            ung_vien.tin_hieu.append(TinHieu(
                "da_nhan", -2,
                f"Trang chủ nhắc {len(thay)} nhãn khác nhau — nghiêng về đại lý"))
        elif len(thay) == 1:
            ung_vien.tin_hieu.append(TinHieu(
                "mot_nhan", 1, f"Trang chủ chỉ nhắc một nhãn ({next(iter(thay))})"))

    # 5. Ten mien mang chinh ten nhan DANG DI TIM. Chi co nghia o duong "tim
    #    lai site cua mot nhan", va o do no la tin hieu manh nhat - ta da biet
    #    phai tim chu gi.
    #
    #    PHAI cham o day chu khong phai sau khi xep hang. Loi da gap: cong +4
    #    nay sau buoc cat top thi `roman.vn` (hang 2, dung la site can tim) bi
    #    loai TRUOC khi kip nhan diem, con `roman.co.uk` lot vao nho thu hang
    #    roi moi duoc cong - ket qua la tra ve site tham o Anh thay vi site cua
    #    chinh doi thu.
    if ten_nhan_can_tim:
        khoa = normalise(ten_nhan_can_tim).replace(" ", "")
        goc = normalise(_goc_ten_mien(ung_vien.domain)).replace(".", "").replace(" ", "")
        if khoa and khoa in goc:
            ung_vien.tin_hieu.append(TinHieu(
                "ten_nhan", 4, f"Tên miền mang chính tên nhãn “{ten_nhan_can_tim}”"))

    if ung_vien.da_dang_ky:
        # O duong TIM LAI, day la cau tra loi chu khong phai mot ghi chu: cau
        # hoi la "site cu con song khong", va viec no van duoc bo may tim kiem
        # xep hang chinh la cau tra loi "con". Nen no phai DUNG DAU de nguoi
        # doc thay ngay khong co gi phai doi - de +0 thi mot site trung ten o
        # nuoc ngoai (roman.co.uk) vuot len tren roman.vn, va nguoi doc phai tu
        # doi chieu moi biet.
        #
        # O duong tim doi thu MOI thi nguoc lai: domain da co khong phai thu
        # dang tim, nen chi ghi chu, khong cong diem.
        ung_vien.tin_hieu.append(TinHieu(
            "da_co", 3 if ten_nhan_can_tim else 0,
            "Đã có trong registry — site cũ vẫn sống"))
    return ung_vien


__all__ = [
    "TEN_MIEN_LOAI_THANG",
    "TU_VUNG_DAI_LY",
    "TU_VUNG_NHA_SAN_XUAT",
    "TinHieu",
    "UngVien",
    "cham_diem",
    "ly_do_loai",
]
