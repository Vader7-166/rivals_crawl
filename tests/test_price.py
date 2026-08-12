"""Task 9.3: logic Gia tri-state (so / "Lien he" / null)."""
import pytest

from crawler.record.price import LIEN_HE, InvalidPriceError, normalize_price


@pytest.mark.parametrize(
    "raw,expected",
    [
        (166000, 166000.0),
        (166000.0, 166000.0),
        ("166000", 166000.0),
        ("339.900 đ", 339900.0),
        ("339.900", 339900.0),
        ("1.234.567 ₫", 1234567.0),
    ],
)
def test_numeric_price_is_normalized_to_float(raw, expected):
    assert normalize_price(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["Liên hệ", "liên hệ", "LIÊN HỆ", "Giá: Liên hệ", "Vui lòng liên hệ để biết giá"],
)
def test_contact_price_variants_become_the_literal_sentinel(raw):
    assert normalize_price(raw) == LIEN_HE


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_missing_price_stays_none(raw):
    assert normalize_price(raw) is None


def test_none_and_lien_he_are_distinguishable():
    """Day la yeu cau cot loi cua spec: None (loi crawl) khac voi "Lien he"
    (site xac nhan khong cong khai gia) - khong duoc gop lam 1."""
    assert normalize_price(None) is not LIEN_HE
    assert normalize_price(None) != LIEN_HE
    assert normalize_price("Liên hệ") == LIEN_HE
    assert normalize_price("Liên hệ") is not None


def test_unparseable_price_raises_instead_of_silently_guessing():
    with pytest.raises(InvalidPriceError):
        normalize_price("abc xyz not a price")
