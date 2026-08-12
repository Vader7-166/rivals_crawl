"""Logic tri-state cho field Gia: so cu the / literal "Lien he" / None.

Task 2.2 (product-record-schema spec, requirement "Gia co 3 trang thai"):
- so cu the: trang nguon hien thi gia bang so.
- chuoi literal LIEN_HE: trang nguon xac nhan khong cong khai gia (vd "Lien he").
- None: chua xac dinh duoc gia do loi crawl - KHAC voi truong hop LIEN_HE.
"""
from __future__ import annotations

from typing import Union

LIEN_HE = "Liên hệ"

PriceValue = Union[float, str, None]

_CONTACT_MARKERS = (
    "liên hệ",
    "lien he",
    "lienhe",
    "gọi để biết giá",
    "call for price",
    "contact for price",
)

_CURRENCY_NOISE = ("đ", "₫", "vnd", "vnđ")


class InvalidPriceError(ValueError):
    """Gia tri Gia tho khong the phan giai duoc ve 1 trong 3 trang thai hop le."""


def is_contact_price(value: PriceValue) -> bool:
    return value == LIEN_HE


def is_missing_price(value: PriceValue) -> bool:
    return value is None


def normalize_price(raw: PriceValue) -> PriceValue:
    """Chuan hoa 1 gia tri Gia tho (lay tu structured data / CSS fallback / LLM)
    ve dung 1 trong 3 trang thai: float, LIEN_HE, hoac None.
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        raise InvalidPriceError(f"Gia tri Gia khong hop le (bool): {raw!r}")
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        lowered = text.lower()
        if any(marker in lowered for marker in _CONTACT_MARKERS):
            return LIEN_HE
        cleaned = lowered
        for noise in _CURRENCY_NOISE:
            cleaned = cleaned.replace(noise, "")
        cleaned = cleaned.replace(" ", "")
        # "339.900" (dau cham la phan cach nghin trong so VN) -> "339900"
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(".", "").replace(",", "")
        try:
            return float(cleaned)
        except ValueError as exc:
            raise InvalidPriceError(f"Khong the phan giai gia tri Gia: {raw!r}") from exc
    raise InvalidPriceError(f"Kieu du lieu Gia khong hop le: {type(raw)!r}")
