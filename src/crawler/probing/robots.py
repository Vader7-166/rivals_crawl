"""Doc robots.txt tim chi thi Sitemap:. Task 4.1."""
from __future__ import annotations

import re

import requests

from ..config import FETCH

_SITEMAP_DIRECTIVE_RE = re.compile(r"(?im)^\s*sitemap\s*:\s*(\S+)\s*$")


def get_sitemap_urls_from_robots(base_url: str, timeout: float = 10.0) -> list[str]:
    """Tra ve danh sach URL sitemap khai bao trong robots.txt cua domain.
    Tra ve [] neu robots.txt khong ton tai hoac khong co chi thi Sitemap:.
    """
    robots_url = base_url.rstrip("/") + "/robots.txt"
    try:
        resp = requests.get(
            robots_url,
            timeout=timeout,
            headers={
                "User-Agent": FETCH.default_user_agent,
                "Accept-Language": FETCH.default_accept_language,
            },
        )
    except requests.RequestException:
        return []
    if resp.status_code != 200:
        return []
    return _SITEMAP_DIRECTIVE_RE.findall(resp.text)
