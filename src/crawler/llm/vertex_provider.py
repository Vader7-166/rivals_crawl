"""Adapter Vertex AI (Gemini 2.5 Flash) - provider LLM chinh. Task 7.2."""
from __future__ import annotations

import logging
import random
import time

from google import genai
from google.genai import types

from ..config import VERTEX, VertexConfig
from .provider import LLMProvider, LLMProviderError

logger = logging.getLogger(__name__)

# Loi TAM THOI - dang thu lai duoc. Quan trong nhat la RESOURCE_EXHAUSTED (429):
# khi chay that tren TLC, 3/129 san pham mat Tags chi vi 1 lan 429 thoang qua,
# trong khi cac request truoc va sau do deu binh thuong (tuc la KHONG phai het
# quota han, chi la vuot gioi han moi phut trong 1 khoanh khac).
_RETRYABLE_MARKERS = (
    "RESOURCE_EXHAUSTED", "429",
    "UNAVAILABLE", "503",
    "INTERNAL", "500",
    "DEADLINE_EXCEEDED", "504",
)

# Loi CAU HINH/QUYEN - thu lai chi ton thoi gian, phai fail nhanh de con
# chuyen sang provider ke tiep (xem fallback.py).
_FATAL_MARKERS = (
    "PERMISSION_DENIED", "403",
    "UNAUTHENTICATED", "401",
    "NOT_FOUND", "404",
    "INVALID_ARGUMENT", "400",
)


def _is_retryable(exc: Exception) -> bool:
    text = str(exc)
    if any(m in text for m in _FATAL_MARKERS):
        return False
    return any(m in text for m in _RETRYABLE_MARKERS)


class VertexAIProvider(LLMProvider):
    name = "vertex-ai"

    # 6 lan thu, backoff 2 -> 4 -> 8 -> 16 -> 32s (+ jitter) = doi toi da ~62s.
    #
    # Ban dau de 4 lan (~14s) nhung do thuc te cho thay khong du: khi quota bi
    # bao mon (chay nhieu dot lien tiep), 4 luong x 24 san pham van mat 6 san
    # pham du da retry, va NGHI 100s cung khong cuu duoc - tuc gioi han la theo
    # gio/ngay chu khong phai theo phut. Voi loi dang quota thi CHO kien nhan
    # hieu qua hon la chay song song nhieu hon.
    MAX_ATTEMPTS = 6
    BASE_DELAY_SECONDS = 2.0

    def __init__(self, config: VertexConfig = VERTEX):
        if not config.is_configured:
            raise LLMProviderError("Vertex AI chưa được cấu hình (thiếu VERTEX_PROJECT_ID)")
        self._config = config
        self._client = genai.Client(
            vertexai=True, project=config.project_id, location=config.location
        )

    def generate_json(self, prompt: str, json_schema: dict | None = None) -> str:
        # thinking_budget=0: TAT HAN che do "thinking" cua Gemini 2.5 Flash.
        #
        # Tac vu nay la doc bang thong so co san roi do ra JSON - khong can suy
        # luan nhieu buoc. Da do A/B tren 4 san pham that (cung prompt, chi doi
        # muc thinking):
        #
        #   muc thinking     thoi gian   output token   so tag TB
        #   tat (budget=0)        2.2s            230        12.2
        #   han che (512)         6.4s            726        12.5
        #   mac dinh (dynamic)    8.2s          1_556        12.5
        #
        # Tren 49 key chung giua "tat" va "mac dinh" chi khac 4 key (8%), deu la
        # khac ve hinh thuc (vd "Trắng, vàng" vs "Trắng/vàng"), KHONG co truong
        # hop nao thinking tim ra thong so ma tat thinking bo sot. Mac dinh chi
        # them 1 key thua (`ten_san_pham` - da co cot rieng).
        #
        # Thinking token bi tinh theo gia OUTPUT ($2.50/1M) nen no chiem ~85%
        # hoa don. Tat di: nhanh hon 3.7x, re hon 3.3x, va giam ap luc quota
        # (moi request tu ~6k token xuong ~3.2k token - lien quan truc tiep den
        # loi 429 RESOURCE_EXHAUSTED da gap khi chay that).
        gen_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            **({"response_json_schema": json_schema} if json_schema else {}),
        )
        last_exc: Exception | None = None
        for attempt in range(self.MAX_ATTEMPTS):
            try:
                response = self._client.models.generate_content(
                    model=self._config.model,
                    contents=prompt,
                    config=gen_config,
                )
            except Exception as exc:  # SDK nem nhieu loai loi (quota, auth, network...)
                last_exc = exc
                if attempt < self.MAX_ATTEMPTS - 1 and _is_retryable(exc):
                    # Backoff mu + jitter. Jitter tranh viec nhieu request cung
                    # bi 429 roi thu lai DONG THOI, gay ra dot 429 tiep theo.
                    delay = self.BASE_DELAY_SECONDS * (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        "Vertex AI lỗi tạm thời (lần %d/%d), đợi %.1fs rồi thử lại: %s",
                        attempt + 1, self.MAX_ATTEMPTS, delay, str(exc)[:120],
                    )
                    time.sleep(delay)
                    continue
                raise LLMProviderError(f"Vertex AI lỗi: {exc}") from exc

            text = getattr(response, "text", None)
            if not text:
                # Nội dung rỗng cũng là lỗi thoáng qua (vd bị safety filter chặn
                # 1 lần) - thử lại thay vì bỏ luôn sản phẩm.
                last_exc = LLMProviderError("Vertex AI trả về nội dung rỗng")
                if attempt < self.MAX_ATTEMPTS - 1:
                    delay = self.BASE_DELAY_SECONDS * (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        "Vertex AI trả về rỗng (lần %d/%d), đợi %.1fs rồi thử lại",
                        attempt + 1, self.MAX_ATTEMPTS, delay,
                    )
                    time.sleep(delay)
                    continue
                raise last_exc
            return text

        raise LLMProviderError(f"Vertex AI lỗi: {last_exc}")
