"""Interface LLM provider dung chung. Task 7.2 (phan interface)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProviderError(Exception):
    """Loi khi goi 1 LLM provider (quota/auth/network/response rong...).

    Duoc dung lam tin hieu de FallbackLLMProvider chuyen sang provider tiep
    theo (xem fallback.py) - KHONG lam crawl that bai toan bo.
    """


class LLMProvider(ABC):
    name: str = "unknown"

    @abstractmethod
    def generate_json(self, prompt: str, json_schema: dict | None = None) -> str:
        """Goi LLM va tra ve chuoi JSON tho (chua parse/validate).

        Prompt da bao gom mo ta hinh dang JSON mong doi (xem llm/schema.py)
        nen json_schema la optional/best-effort: provider nao ho tro structured
        output truc tiep (vd Vertex AI) thi dung de tang do tin cay, provider
        nao khong ho tro (vd DeepSeek JSON mode khong nhan schema) thi bo qua
        tham so nay va chi dua vao huong dan trong prompt + validate.py o tang
        goi phia tren.
        """
        raise NotImplementedError
