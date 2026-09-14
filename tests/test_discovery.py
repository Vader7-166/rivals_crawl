"""Tim site LED cua doi thu bang bo may tim kiem (`crawler/discovery`).

KHONG cham mang: dung `StaticEngine` cho tang tim kiem va truyen thang HTML cho
tang cham diem. Cac con so trong test lay tu dot do that ngay 11/09/2026 ghi o
docstring cua `scoring.py` va `queries.py`.
"""
import pytest

from crawler.discovery import (
    StaticEngine,
    UngVien,
    cham_diem,
    ly_do_loai,
    tim_doi_thu,
    tim_lai_nhan,
    tu_danh_muc,
)
from crawler.discovery.engine import go_lop_boc

TRANG_NHA_SAN_XUAT = """
<html><body><h1>Công ty CP Bóng đèn Ví Dụ</h1>
<p>Nhà máy 12.000m², dây chuyền sản xuất tự động, đạt tiêu chuẩn ISO 9001.
Sản phẩm xuất khẩu sang 20 nước. Trung tâm nghiên cứu R&D riêng.</p>
</body></html>
"""

TRANG_DAI_LY = """
<html><body><h1>Siêu thị đèn LED giá tốt</h1>
<p>Giao hàng toàn quốc, freeship đơn trên 500k. Showroom tại 3 thành phố.
Thêm vào giỏ hàng ngay, khuyến mãi tháng 9. Đại lý chính hãng giá rẻ.</p>
</body></html>
"""

TRANG_SAN_PHAM = """
<html><body>
<div itemscope itemtype="https://schema.org/Product">
  <span itemprop="name">Đèn LED âm trần 9W</span>
  <span itemprop="price">199000</span>
</div>
<p>Giá: 199.000 đ</p></body></html>
"""


# -- go lop boc cua Bing -----------------------------------------------------


def test_bing_redirect_is_decoded():
    """Khong go lop boc thi MOI ket qua deu co domain `www.bing.com`, tuc ca
    tang chon loc ben tren khong con gi de lam viec."""
    boc = ("https://www.bing.com/ck/a?!&&p=abc&u=a1aHR0cHM6Ly9wYXJhZ29uLmNvbS52bi8"
           "&ntb=1")

    assert go_lop_boc(boc) == "https://paragon.com.vn/"


def test_a_plain_link_is_left_alone():
    assert go_lop_boc("https://duhal.com.vn/x") == "https://duhal.com.vn/x"


def test_an_undecodable_link_falls_back_to_the_original():
    """Bing doi cach ma hoa thi phai tra ve chinh no, khong duoc nem loi - mot
    ket qua hong khong duoc lam hong ca dot do."""
    hong = "https://www.bing.com/ck/a?u=a1###khong-phai-base64###"

    assert go_lop_boc(hong) == hong


# -- loai thang tap dong -----------------------------------------------------


@pytest.mark.parametrize("domain", ["shopee.vn", "www.lazada.vn", "vi.wikipedia.org"])
def test_marketplaces_and_dictionaries_are_dropped(domain):
    assert ly_do_loai(domain) is not None


def test_our_own_site_is_dropped(): 
    """rangdong.com.vn dung hang 2 cho "đèn led âm trần" (do that). Khong loai
    la mat mot suat trong top 3 o gan nhu moi truy van."""
    assert ly_do_loai("rangdong.com.vn", cua_minh=["rangdong.com.vn"]) is not None
    assert ly_do_loai("duhal.com.vn", cua_minh=["rangdong.com.vn"]) is None


def test_a_real_competitor_is_not_dropped():
    assert ly_do_loai("paragon.com.vn") is None


# -- tin hieu tu vung --------------------------------------------------------


def test_manufacturer_vocabulary_scores_positive():
    uv = cham_diem(UngVien(domain="x.vn"), html_trang_chu=TRANG_NHA_SAN_XUAT)

    tu_vung = [t for t in uv.tin_hieu if t.ten == "tu_vung"]
    assert len(tu_vung) == 1 and tu_vung[0].diem > 0


def test_reseller_vocabulary_scores_negative():
    uv = cham_diem(UngVien(domain="x.vn"), html_trang_chu=TRANG_DAI_LY)

    tu_vung = [t for t in uv.tin_hieu if t.ten == "tu_vung"]
    assert len(tu_vung) == 1 and tu_vung[0].diem < 0


def test_the_grey_zone_scores_nothing_instead_of_guessing():
    """kingled.com.vn (nha san xuat) va ledxanh.vn (dai ly) cung cho chenh
    lech 0. Doan bua o vung do thi te hon la im lang."""
    mo = "<html><body>Nhà máy sản xuất. Giao hàng nhanh, showroom rộng.</body></html>"

    uv = cham_diem(UngVien(domain="x.vn"), html_trang_chu=mo)

    assert [t for t in uv.tin_hieu if t.ten == "tu_vung"] == []


def test_a_selling_page_alone_does_not_prove_a_manufacturer():
    """Tin hieu "co trang san pham that" chi loai duoc blog/wiki. Dai ly nao
    cung dat no (ledxanh: 506 lan nhac so tien), nen no khong duoc du manh de
    mot minh dua mot dai ly len dau."""
    dai_ly = cham_diem(UngVien(domain="x.vn"),
                       html_trang_chu=TRANG_DAI_LY, html_trang_mau=TRANG_SAN_PHAM)
    nsx = cham_diem(UngVien(domain="y.vn"),
                    html_trang_chu=TRANG_NHA_SAN_XUAT, html_trang_mau=TRANG_SAN_PHAM)

    assert nsx.diem > dai_ly.diem


def test_every_signal_carries_a_reason_a_person_can_read():
    """Diem tran khong kiem chung duoc. Nguoi duyet phai doc duoc VI SAO."""
    uv = cham_diem(UngVien(domain="x.vn", hang_tot_nhat=1),
                   html_trang_chu=TRANG_NHA_SAN_XUAT)

    assert uv.tin_hieu and all(t.ly_do.strip() for t in uv.tin_hieu)


# -- truy van ----------------------------------------------------------------


def test_queries_come_from_category_names_in_the_store():
    """Tu vung KHONG bia ra: ten danh muc trong kho la tu vung that cua nganh,
    do chinh doi thu viet."""
    ra = tu_danh_muc(["Đèn LED âm trần", "Đèn LED panel", "Quạt trần", "SP Khác"])

    assert "Đèn LED âm trần" in ra
    assert "Quạt trần" not in ra   # khong mang tu neo -> tim ra nganh khac
    assert "SP Khác" not in ra     # qua ngan/chung de lam truy van


def test_an_empty_store_still_has_usable_queries():
    """Lan chay dau kho rong - do la trang thai binh thuong, khong phai loi."""
    assert len(tu_danh_muc([])) >= 3


def test_refinding_a_brand_always_keeps_an_anchor_word():
    """"Roman" mot minh ra lich su La Ma, "Asia" ra chau A."""
    for q in tim_lai_nhan("Roman"):
        assert "Roman" in q and ("led" in q.lower() or "đèn" in q.lower())


# -- ghep --------------------------------------------------------------------


def test_the_same_domain_across_queries_counts_as_one_candidate():
    engine = StaticEngine({
        "q1": ["paragon.com.vn", "shopee.vn"],
        "q2": ["paragon.com.vn", "ledhome.vn"],
    })

    kq = tim_doi_thu(truy_van=["q1", "q2"], engine=engine, tai_trang=False, top=5)

    paragon = [u for u in kq.ung_vien if u.domain == "paragon.com.vn"]
    assert len(paragon) == 1
    assert paragon[0].truy_van == ["q1", "q2"]
    assert "shopee.vn" in [d for d, _ in kq.da_loai]


def test_an_already_registered_domain_is_flagged_not_hidden():
    """Voi muc dich "tim lai site da doi", chinh viec domain cu con song la cau
    tra loi can biet - an no di la giau mat cau tra loi."""
    engine = StaticEngine({"q": ["duhal.com.vn"]})

    kq = tim_doi_thu(truy_van=["q"], engine=engine, tai_trang=False, top=3)

    assert kq.ung_vien[0].domain == "duhal.com.vn"
    assert kq.ung_vien[0].da_dang_ky is True


def test_a_search_engine_returning_nothing_is_not_a_crash():
    kq = tim_doi_thu(truy_van=["q"], engine=StaticEngine({}), tai_trang=False)

    assert kq.ung_vien == []


# -- hai lo hong lo ra khi chay that (11/09/2026) -----------------------------


@pytest.mark.parametrize("domain", ["cafef.vn", "finance.vietstock.vn", "vnexpress.net"])
def test_news_and_finance_sites_are_dropped(domain):
    """Tim lai nhan "VNE" cho ra vietstock/cafef vi "VNE" con la ma co phieu.
    Mot bai bao VE mot doanh nghiep san xuat dat het tin hieu tu vung nha san
    xuat ma khong phai site cua ho - nen day phai la tap loai THANG."""
    assert ly_do_loai(domain) is not None


def test_two_stray_words_are_not_enough_to_claim_a_factory():
    """Nguong chi-can-chenh-lech-duong thuong ca mot bai bao co dung hai chu
    "sản xuất" va "nghiên cứu"."""
    bai_bao = "<html><body>Doanh nghiệp đẩy mạnh sản xuất và nghiên cứu.</body></html>"

    uv = cham_diem(UngVien(domain="x.vn"), html_trang_chu=bai_bao)

    assert [t for t in uv.tin_hieu if t.ten == "tu_vung"] == []


def test_refinding_a_known_brand_also_uses_its_aliases():
    """"VNE" mot minh la ma co phieu (VNECO) va cho ra vietstock/cafef. Bi danh
    "VNE Led" da khai san trong registry thi tro dung nganh - bo qua no la vut
    di cong khai bao."""
    from crawler.discovery import tim_lai_site
    from crawler.discovery.engine import StaticEngine

    kq = tim_lai_site("VNE", engine=StaticEngine({}), tai_trang=False)

    assert any("VNE Led" in q for q in kq.truy_van)


def test_the_brand_name_signal_is_scored_before_the_cut_not_after():
    """Loi da gap khi chay that: cong diem "tên miền mang tên nhãn" SAU buoc
    cat top thi `roman.vn` (hang 2, dung la site can tim) bi loai truoc khi kip
    nhan diem, con `roman.co.uk` lot vao nho thu hang roi moi duoc cong."""
    uv = cham_diem(UngVien(domain="roman.vn"), ten_nhan_can_tim="Roman")

    assert any(t.ten == "ten_nhan" and t.diem > 0 for t in uv.tin_hieu)


def test_the_brand_name_signal_is_absent_when_not_refinding():
    """Duong tim doi thu MOI khong co nhan nao de doi chieu - tin hieu nay chi
    co nghia khi ta da biet phai tim chu gi."""
    uv = cham_diem(UngVien(domain="roman.vn"))

    assert not any(t.ten == "ten_nhan" for t in uv.tin_hieu)


def test_refinding_puts_the_still_living_old_site_first():
    """Cau hoi cua duong tim lai la "site cu con song khong". No van duoc bo
    may tim kiem xep hang chinh la cau tra loi "còn" - nen no phai dung dau,
    khong de mot site trung ten o nuoc ngoai (roman.co.uk) vuot len."""
    cu = cham_diem(UngVien(domain="roman.vn", da_dang_ky=True), ten_nhan_can_tim="Roman")
    ngoai = cham_diem(UngVien(domain="www.roman.co.uk"), ten_nhan_can_tim="Roman")

    assert cu.diem > ngoai.diem


def test_an_already_registered_domain_scores_nothing_when_hunting_for_new_rivals():
    """Duong tim doi thu MOI: domain da co khong phai thu dang tim."""
    uv = cham_diem(UngVien(domain="roman.vn", da_dang_ky=True))

    assert [t.diem for t in uv.tin_hieu if t.ten == "da_co"] == [0]
