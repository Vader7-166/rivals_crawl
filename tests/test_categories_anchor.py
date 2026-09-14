"""Neo breadcrumb ve dung cap loai san pham - `extraction/categories.py`.

Moi truong hop duoi day la mot hinh chuoi DO DUOC tren HTML that trong
`crawl.db`, khong phai vi du bia ra.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawler.extraction.categories import (  # noqa: E402
    anchor_categories,
    non_product_branch,
    sheet_category,
)
from crawler.record.schema import CrawlStatus, ProductRecord  # noqa: E402


def _ba_cot_va_sheet(labels, domain):
    cats = anchor_categories(labels, domain)
    return cats, sheet_category(*cats, domain)


def test_mac_dinh_doc_tu_cap_dau():
    """Site chua khai thi KHONG dong gi - crawl duoc ngay voi 0 dong cau hinh,
    va 10/14 site dang chay dung o hanh vi nay."""
    cats, sheet = _ba_cot_va_sheet(
        ["Đèn LED âm trần", "Đèn LED âm trần COB"], "tlclighting.com.vn"
    )

    assert cats == ("Đèn LED âm trần", "Đèn LED âm trần COB", None)
    assert sheet == "Đèn LED âm trần"


def test_site_leaf_dien_ba_cot_theo_dung_thu_tu_goc():
    """Ba cot doc y nhu breadcrumb hien tren trang: "Trang chủ / Đèn Led / Đèn
    LED Búp Panasonic". Cot 1 la thung dieu huong, nen TEN SHEET lay o cap sau
    cung chu khong phai cot 1."""
    cats, sheet = _ba_cot_va_sheet(
        ["Đèn Led", "Đèn LED Búp Panasonic"], "panasonicvn.com.vn"
    )

    assert cats == ("Đèn Led", "Đèn LED Búp Panasonic", None)
    assert sheet == "Đèn LED Búp Panasonic"


def test_chuoi_mot_cap_thi_chinh_no_la_loai():
    """"Quạt Hút" khong co cap con - ca ba cot lan ten sheet deu la chinh no."""
    cats, sheet = _ba_cot_va_sheet(["Quạt Hút"], "panasonicvn.com.vn")

    assert cats == ("Quạt Hút", None, None)
    assert sheet == "Quạt Hút"


def test_chuoi_sau_hon_ba_cap_thi_bo_CAP_DAU():
    """Khuon tham chieu chi co ba cot. Chuoi sau hon thi phai bo bot, va bo cap
    DAU - cap tong quat nhat - chu khong bo cap cuoi: Nanoco co bon cap, bo cap
    cuoi thi mat "Bóng LED Bulb", dung loi da lam ca 48 san pham don vao mot
    sheet "Danh Mục"."""
    cats, sheet = _ba_cot_va_sheet(
        ["Danh Mục", "Chiếu Sáng", "Đèn chiếu sáng", "Bóng LED Bulb"],
        "www.nanoco.com.vn",
    )

    assert cats == ("Chiếu Sáng", "Đèn chiếu sáng", "Bóng LED Bulb")
    assert sheet == "Bóng LED Bulb"


def test_nhanh_nong_hon_van_dung_o_dung_loai():
    """Cay danh muc KHONG deu nen dem SO CAP tu dau nao cung sai. Nhanh nay chi
    sau ba cap - khong cap nao bi bo, va ten sheet van dung."""
    cats, sheet = _ba_cot_va_sheet(
        ["Danh Mục", "Chiếu Sáng", "Phụ kiện đèn"], "www.nanoco.com.vn"
    )

    assert cats == ("Danh Mục", "Chiếu Sáng", "Phụ kiện đèn")
    assert sheet == "Phụ kiện đèn"


def test_roman_hai_nhanh_lech_sau_deu_ra_dung_ten_sheet():
    sau_ba_cap = ["Thiết bị chiếu sáng - Led", "Đèn nội thất", "Đèn Downlight LED"]
    sau_hai_cap = ["Thiết bị gia dụng", "Đèn học chống cận"]

    assert _ba_cot_va_sheet(sau_ba_cap, "roman.vn")[1] == "Đèn Downlight LED"
    assert _ba_cot_va_sheet(sau_hai_cap, "roman.vn")[1] == "Đèn học chống cận"


def test_philips_bo_cap_dau_va_giu_ba_cap_sat_san_pham():
    cats, sheet = _ba_cot_va_sheet(
        [
            "Bộ đèn trong nhà",
            "Đèn Highbay và Lowbay",
            "Trần cao",
            "Đèn GreenPerform Highbay Rectangular",
        ],
        "www.lighting.philips.com.vn",
    )

    assert cats == (
        "Đèn Highbay và Lowbay",
        "Trần cao",
        "Đèn GreenPerform Highbay Rectangular",
    )
    assert sheet == "Đèn GreenPerform Highbay Rectangular"


def test_site_top_giu_cap_dau_lam_ten_sheet():
    """Lay cap cuoi cho site "top" thi TLC ra sheet "COB" thay vi "Đèn LED âm
    trần", va KingLED no tu 24 thanh 108 sheet cho 549 san pham."""
    assert sheet_category("Đèn LED âm trần", "COB", None, "tlclighting.com.vn") == (
        "Đèn LED âm trần"
    )


def test_chuoi_rong_thi_khong_co_danh_muc():
    assert anchor_categories([], "panasonicvn.com.vn") == (None, None, None)
    assert anchor_categories([], "tlclighting.com.vn") == (None, None, None)


def test_hai_category_chi_khac_hoa_thuong_van_ra_hai_sheet_hop_le():
    """Excel coi ten sheet la KHONG phan biet hoa thuong. Do tren Philips: hai
    danh muc cat giua ra hai ten chi khac chu "T"/"t" - so khop phan biet hoa
    thuong thi ta khong thay trung, nhung openpyxl thay: no lang le noi them
    "1" va KHONG kiem lai gioi han 31 ky tu, de ra ten 32 ky tu."""
    from crawler.record.excel_writer import _sheet_name

    taken: set[str] = set()
    dau = _sheet_name("LuxSpace Accent Nhỏ Gọn Có Thể Điều Chỉnh", taken)
    taken.add(dau.casefold())
    sau = _sheet_name("LuxSpace Accent phiên bản Performance có thể điều chỉnh", taken)

    assert dau.casefold() != sau.casefold()
    assert len(dau) <= 31 and len(sau) <= 31


# -- Nhanh breadcrumb khong phai san pham ------------------------------------
#
# Bai toan: Roman va Duhal de MOI trang o `/<slug>.html` - san pham, danh muc,
# bai viet cung mot hinh URL - va bai viet ky thuat nhac du cong suat/quang
# thong/dien ap/nhiet do mau/CRI nen vuot moi nguong thong so.
#
# 7 luat loc da do tren 80 trang Roman, khong luat nao sach (crawl_list.md).
# Cai KHONG phai suy doan: chinh doi thu da xep bai viet vao mot nhanh rieng
# va noi ra dieu do trong breadcrumb.


def test_site_declared_branch_marks_a_page_as_not_a_product():
    assert non_product_branch("Thông tin", None, None, "roman.vn") == "Thông tin"
    assert non_product_branch("Tin tức", None, None, "duhal.com.vn") == "Tin tức"


def test_a_real_category_is_left_alone():
    assert non_product_branch("Đèn nội thất", "Đèn Downlight LED", None, "roman.vn") is None


def test_branches_do_not_leak_across_domains():
    """Moi domain chi doc danh sach cua chinh no. Gia phai tra cho mot lan khop
    nham la mot san pham that bien mat khoi file ket qua ma khong ai thay."""
    assert non_product_branch("Tin tức", None, None, "roman.vn") is None
    assert non_product_branch("Thông tin", None, None, "tlclighting.com.vn") is None


def test_branch_is_matched_on_every_level_not_just_the_first():
    """Site "leaf" (roman) dem nguoc tu cap sat san pham len, nen nhanh goc roi
    vao cot nao la tuy do dai chuoi breadcrumb cua tung trang."""
    assert non_product_branch("Đèn nội thất", "Thông tin", None, "roman.vn") == "Thông tin"


def test_partial_name_does_not_match():
    """So khop chinh xac tung ky tu, khong phai chuoi con."""
    assert non_product_branch("Đèn tin tức", None, None, "duhal.com.vn") is None


def test_a_non_product_keeps_its_verdict_through_recompute():
    """Bai viet THIEU gan het field bat buoc, nen neu de tinh lai binh thuong
    no thanh "san pham thieu o" va quay lai hang doi crawl lai mai mai."""
    record = ProductRecord(product_id="1", link_san_pham="https://roman.vn/x.html")
    record.mark_not_a_product("Thông tin")

    record.recompute_status()

    assert record.crawl_status is CrawlStatus.NOT_A_PRODUCT
    assert "Thông tin" in record.crawl_error
