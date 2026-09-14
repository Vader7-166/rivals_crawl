"""Validate output tho tu LLM truoc khi luu. Task 7.6."""
from __future__ import annotations

import json
import logging
import re
import unicodedata

from .schema import ExtractionOutput

logger = logging.getLogger(__name__)

_MAX_TAG_VALUE_LEN = 200
_MAX_TAG_COUNT = 60

# Tach gia tri nhieu thanh phan truoc khi doi chieu: model thuong doi dau phan
# cach ("6500K, 4000K" -> "6500K/4000K") du van chep dung tung so.
_VALUE_PIECES = re.compile(r"[/,;()]+")
_WHITESPACE = re.compile(r"[\s\u00a0]+")


def _norm(text: str) -> str:
    return _WHITESPACE.sub("", unicodedata.normalize("NFC", str(text)).lower())


def drop_ungrounded_tags(tags: dict[str, str], source_text: str) -> dict[str, str]:
    """Bo cac tag co gia tri KHONG xuat hien trong chinh noi dung nguon.

    Prompt da yeu cau "khong bia", nhung yeu cau khong phai la dam bao - day la
    luoi an toan cuoi cung truoc khi ghi vao file giao di. Do tren ca dot
    kingled.com.vn (549 san pham, 5.252 gia tri tag): loai dung 1 tag. Tuc la
    voi model + prompt hien tai, bia dat KHONG phai van de pho bien; giu ham nay
    de doi provider/model khac khong am tham lam ban du lieu.

    Doi chieu phai chiu duoc viec model dinh dang lai, neu khong se xoa nham du
    lieu that: chuan hoa 2 ben (bo dau cach, ha chu thuong) roi tach gia tri
    thanh cac manh theo dau phan cach, moi manh deu phai co mat trong nguon.
    Nho vay "IP44" van khop nguon ghi "IP 44", "6500K/4000K" khop "6500K, 4000K".

    LUU Y ve pham vi doi chieu: nguon o day la TOAN BO text da dua cho model
    (bang thong so + mo ta san pham), khong phai rieng bang thong so. Nhieu
    thuoc tinh that chi duoc noi trong phan mo ta - vd `dien_ap="12VDC"` cua
    den ban HS 10W khong co trong bang thong so (bang ghi `Nguồn Điện:
    220V/50Hz` la dien vao) nhung duoc noi ro 2 lan trong mo ta ("Điệp áp 12VDC
    an toan khi su dung"). Thu hep pham vi ve rieng bang thong so se xoa nham
    dung nhung gia tri nay.
    """
    if not source_text:
        return tags
    source = _norm(source_text)
    kept: dict[str, str] = {}
    for key, value in tags.items():
        pieces = [p for p in _VALUE_PIECES.split(_norm(value)) if p]
        if pieces and all(piece in source for piece in pieces):
            kept[key] = value
        else:
            logger.info("Bỏ tag không có căn cứ trong nguồn: %s=%r", key, value)
    return kept


class ExtractionValidationError(ValueError):
    """Output LLM khong dung JSON hoac khong dung hinh dang mong doi."""


def parse_and_validate(raw_text: str) -> ExtractionOutput:
    raw_text = (raw_text or "").strip()
    # Mot so model boc JSON trong ```json ... ``` du da yeu cau khong lam vay.
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.lower().startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ExtractionValidationError(f"LLM không trả về JSON hợp lệ: {exc}") from exc

    if not isinstance(data, dict):
        raise ExtractionValidationError("LLM trả về JSON không phải object")

    tags_raw = data.get("tags")
    if not isinstance(tags_raw, dict):
        raise ExtractionValidationError("Field 'tags' thiếu hoặc không phải object")

    clean_tags: dict[str, str] = {}
    for key, value in tags_raw.items():
        if not isinstance(key, str) or not key.strip():
            continue
        value_str = str(value).strip()
        if not value_str or len(value_str) > _MAX_TAG_VALUE_LEN:
            continue
        clean_tags[key.strip()] = value_str
        if len(clean_tags) >= _MAX_TAG_COUNT:
            break

    def _text_field(name: str) -> str | None:
        value = data.get(name)
        return value.strip() if isinstance(value, str) and value.strip() else None

    return ExtractionOutput(
        tags=clean_tags,
        ma_san_pham=_text_field("ma_san_pham"),
        muc_uu_diem=_text_field("muc_uu_diem"),
    )
