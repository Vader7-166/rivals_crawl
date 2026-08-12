"""Validate output tho tu LLM truoc khi luu. Task 7.6."""
from __future__ import annotations

import json

from .schema import ExtractionOutput

_MAX_TAG_VALUE_LEN = 200
_MAX_TAG_COUNT = 60


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

    ma_san_pham = data.get("ma_san_pham")
    if not isinstance(ma_san_pham, str) or not ma_san_pham.strip():
        ma_san_pham = None
    else:
        ma_san_pham = ma_san_pham.strip()

    return ExtractionOutput(tags=clean_tags, ma_san_pham=ma_san_pham)
