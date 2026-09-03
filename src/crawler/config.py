"""Cau hinh doc tu bien moi truong (.env). Task 1.1."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _resolve_vertex_project_id() -> str | None:
    """VERTEX_PROJECT_ID neu co khai bao truc tiep; neu khong, thu doc field
    "project_id" trong file service-account JSON tro boi
    GOOGLE_APPLICATION_CREDENTIALS (tien loi khi nguoi dung chi cung cap file
    key ma khong tu dien project id rieng)."""
    explicit = os.environ.get("VERTEX_PROJECT_ID")
    if explicit:
        return explicit

    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path and Path(creds_path).is_file():
        try:
            with open(creds_path, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("project_id")
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return None
    return None


@dataclass(frozen=True)
class VertexConfig:
    project_id: str | None = _resolve_vertex_project_id()
    location: str = os.environ.get("VERTEX_LOCATION", "us-central1")
    model: str = os.environ.get("VERTEX_MODEL", "gemini-2.5-flash")
    credentials_file: str | None = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or None

    @property
    def is_configured(self) -> bool:
        return bool(self.project_id)


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str | None = os.environ.get("DEEPSEEK_API_KEY") or None
    base_url: str = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model: str = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass(frozen=True)
class FetchConfig:
    cloakbrowser_executable_path: str | None = (
        os.environ.get("CLOAKBROWSER_EXECUTABLE_PATH") or None
    )
    default_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    default_accept_language: str = "vi-VN,vi;q=0.9,en;q=0.8"
    navigation_timeout_ms: int = 30_000

    # Giai cach toi thieu giua 2 lan fetch (giay). Mac dinh 0 - do thuc te cho
    # thay fetch tuan tu khong delay da la nhanh nhat ma van an toan. Dat > 0
    # neu site doi thu nhay cam hon.
    min_interval_seconds: float = _env_float("FETCH_MIN_INTERVAL", 0.0)
    # Tran cua co che tu lui (adaptive cooldown) khi server bat dau tu choi.
    max_cooldown_seconds: float = _env_float("FETCH_MAX_COOLDOWN", 15.0)


@dataclass(frozen=True)
class ProbingConfig:
    sitemap_reliability_threshold: float = _env_float("SITEMAP_RELIABILITY_THRESHOLD", 0.8)
    sitemap_sample_size: int = _env_int("SITEMAP_SAMPLE_SIZE", 10)
    probe_cache_dir: Path = Path(os.environ.get("PROBE_CACHE_DIR", "./.cache/probe"))


@dataclass(frozen=True)
class CrawlConfig:
    """So luong san pham crawl song song.

    Mac dinh 4 - chon dua tren do thuc te, khong phai uoc luong:
      4 luong -> 32.9 SP/phut   (1.00x)
      8 luong -> 54.2 SP/phut   (1.65x)
     16 luong -> 62.8 SP/phut   (1.91x)
    Lai giam dan rat nhanh vi tran that la QUOTA Vertex chu khong phai CPU/RAM
    (goi LLM la cho mang, gan nhu khong ton CPU). Day worker len cao chi bien
    "cham" thanh "mat du lieu" khi quota can. 4 luong cung la muc lich su voi
    server doi thu - moi luong giu 1 browser rieng (~450MB RAM).
    """

    workers: int = _env_int("CRAWL_WORKERS", 4)


@dataclass(frozen=True)
class OutputConfig:
    output_dir: Path = Path(os.environ.get("OUTPUT_DIR", "./output"))


@dataclass(frozen=True)
class StoreConfig:
    """Kho du lieu crawl (SQLite, 1 file).

    Uoc luong dung luong tu do that: 549 SP KingLED ~9,3MB + 485 SP TLC ~22,8MB
    -> ~32MB cho 2 site da co, ~100MB neu tinh ca Roman. File nay KHONG nam
    trong git (xem .gitignore) - dung lai duoc tu output/*.xlsx.
    """

    db_path: Path = Path(os.environ.get("CRAWL_DB_PATH", "./crawl.db"))
    # Cho bao lau khi file dang bi khoa boi mot lan ghi khac truoc khi bao loi.
    busy_timeout_seconds: float = _env_float("CRAWL_DB_BUSY_TIMEOUT", 30.0)


VERTEX = VertexConfig()
DEEPSEEK = DeepSeekConfig()
FETCH = FetchConfig()
PROBING = ProbingConfig()
CRAWL = CrawlConfig()
OUTPUT = OutputConfig()
STORE = StoreConfig()
