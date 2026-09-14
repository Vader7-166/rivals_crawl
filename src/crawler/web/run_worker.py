"""Điểm vào tiến trình worker: `python -m crawler.web.run_worker`.

Tách khỏi `worker.py` để phần logic (nhận job, chạy, chốt trạng thái) vẫn nhập
được vào test mà không kéo theo việc dựng log và kiểm tra cấu hình.
"""
from __future__ import annotations

import logging
import os
import sys

from ..config import STORE, VERTEX
from .worker import serve

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("run_worker")


def kiem_tra_cau_hinh() -> list[str]:
    """Các thiếu sót khiến job chắc chắn hỏng, kiểm TRƯỚC khi nhận việc.

    Hỏng sớm thay vì hỏng giữa lượt crawl (task 9.5). Thiếu khoá LLM mà vẫn
    nhận job thì mỗi trang đều fetch thành công rồi mới chết ở tầng 2 — mất
    hàng chục phút và một mớ quota mạng để phát hiện một biến môi trường trống.
    """
    thieu = []
    co_vertex = VERTEX.is_configured
    co_deepseek = bool(os.environ.get("DEEPSEEK_API_KEY"))
    if not (co_vertex or co_deepseek):
        thieu.append(
            "Không có provider LLM nào: cần VERTEX_PROJECT_ID (hoặc "
            "GOOGLE_APPLICATION_CREDENTIALS trỏ tới file service-account có "
            "project_id), hoặc DEEPSEEK_API_KEY — xem .env.example"
        )
    thu_muc = STORE.db_path.parent
    if not os.access(thu_muc, os.W_OK):
        thieu.append(f"Không ghi được vào {thu_muc} — kho dữ liệu nằm ở đó")
    return thieu


def main() -> int:
    loi = kiem_tra_cau_hinh()
    if loi:
        for dong in loi:
            logger.error("Cấu hình thiếu: %s", dong)
        return 1
    serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
