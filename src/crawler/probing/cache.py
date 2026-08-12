"""Cache ket qua site-probing theo domain. Task 4.6."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional

from ..config import PROBING

Strategy = Literal["sitemap", "menu_crawl"]


@dataclass
class ProbeResult:
    domain: str
    strategy: Strategy
    probed_at: str
    sitemap_url: Optional[str] = None
    reliability_score: Optional[float] = None
    # strategy == "sitemap": URL san pham lay truc tiep tu sitemap.
    product_urls: list[str] = field(default_factory=list)
    # strategy == "menu_crawl": URL trang danh muc da xac nhan la luoi san pham that.
    listing_urls: list[str] = field(default_factory=list)
    flagged_landing_urls: list[str] = field(default_factory=list)


def _domain_key(domain: str) -> str:
    return re.sub(r"[^a-z0-9.-]+", "_", domain.lower())


class ProbeCache:
    def __init__(self, cache_dir: Path = PROBING.probe_cache_dir, ttl_days: int = 30):
        self._cache_dir = Path(cache_dir)
        self._ttl = timedelta(days=ttl_days)

    def _path_for(self, domain: str) -> Path:
        return self._cache_dir / f"{_domain_key(domain)}.json"

    def get(self, domain: str) -> Optional[ProbeResult]:
        path = self._path_for(domain)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        result = ProbeResult(**data)
        probed_at = datetime.fromisoformat(result.probed_at)
        if datetime.now(timezone.utc) - probed_at > self._ttl:
            return None
        return result

    def save(self, result: ProbeResult) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(result.domain)
        path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
