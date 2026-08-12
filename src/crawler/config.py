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


@dataclass(frozen=True)
class ProbingConfig:
    sitemap_reliability_threshold: float = _env_float("SITEMAP_RELIABILITY_THRESHOLD", 0.8)
    sitemap_sample_size: int = _env_int("SITEMAP_SAMPLE_SIZE", 10)
    probe_cache_dir: Path = Path(os.environ.get("PROBE_CACHE_DIR", "./.cache/probe"))


@dataclass(frozen=True)
class OutputConfig:
    output_dir: Path = Path(os.environ.get("OUTPUT_DIR", "./output"))


VERTEX = VertexConfig()
DEEPSEEK = DeepSeekConfig()
FETCH = FetchConfig()
PROBING = ProbingConfig()
OUTPUT = OutputConfig()
