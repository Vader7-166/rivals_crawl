"""Lop fetch/render dung chung qua cloakBrowser (tuong thich Playwright API).

Tasks 3.1-3.4 (capability stealth-fetch):
- 3.1: interface fetch(url) dung chung cho moi tang trich xuat.
- 3.2: fingerprint/header thuc te mac dinh.
- 3.3: doi/kich hoat noi dung render bang JS (vd tab thong so ky thuat).
- 3.4: retry khi gap loi chan bot co ban (406/403).

cloakBrowser la 1 ban Chromium build rieng noi len API Playwright chuan, nen
chi can tro `executable_path` toi binary cloakBrowser da cai (bien moi truong
CLOAKBROWSER_EXECUTABLE_PATH) la dung duoc qua sync_playwright() nhu Chromium
thuong. Neu chua cau hinh, fallback ve Chromium mac dinh cua Playwright kem
canh bao (khong co kha nang chong fingerprint nhu thiet ke yeu cau).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional, Sequence

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from ..config import FETCH, FetchConfig

logger = logging.getLogger(__name__)

_BOT_BLOCK_STATUSES = {403, 406, 429}


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: Optional[int]
    html: str
    ok: bool
    error: Optional[str] = None


class StealthFetcher:
    """Context manager boc cloakBrowser/Playwright thanh 1 interface fetch() don gian."""

    def __init__(self, config: FetchConfig = FETCH):
        self._config = config
        self._playwright = None
        self._browser = None

    def __enter__(self) -> "StealthFetcher":
        self._playwright = sync_playwright().start()
        launch_kwargs: dict = {"headless": True}
        if self._config.cloakbrowser_executable_path:
            launch_kwargs["executable_path"] = self._config.cloakbrowser_executable_path
        else:
            logger.warning(
                "CLOAKBROWSER_EXECUTABLE_PATH chua duoc cau hinh - dang fallback ve "
                "Chromium mac dinh cua Playwright (khong co stealth fingerprinting)."
            )
        self._browser = self._playwright.chromium.launch(**launch_kwargs)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    def _new_page(self):
        context = self._browser.new_context(
            user_agent=self._config.default_user_agent,
            locale="vi-VN",
            extra_http_headers={"Accept-Language": self._config.default_accept_language},
            viewport={"width": 1366, "height": 900},
        )
        page = context.new_page()
        page.set_default_navigation_timeout(self._config.navigation_timeout_ms)
        return context, page

    def fetch(
        self,
        url: str,
        *,
        click_selectors: Sequence[str] = (),
        wait_selector: Optional[str] = None,
        max_retries: int = 2,
    ) -> FetchResult:
        """Lay HTML da render cua 1 URL.

        click_selectors: cac selector duoc click theo thu tu truoc khi doc HTML
        (vd tab "Thong so ky thuat" chi render sau khi bam - case KingLED).
        wait_selector: cho selector nay xuat hien/co noi dung truoc khi tra ve.
        """
        last_error: Optional[str] = None
        for attempt in range(max_retries + 1):
            context = None
            try:
                context, page = self._new_page()
                response = page.goto(url, wait_until="domcontentloaded")
                status = response.status if response else None

                if status in _BOT_BLOCK_STATUSES and attempt < max_retries:
                    last_error = f"HTTP {status} (nghi bi chan bot), thu lai..."
                    logger.info("%s -> %s, retry lan %s", url, status, attempt + 1)
                    context.close()
                    time.sleep(1.5 * (attempt + 1))
                    continue

                for selector in click_selectors:
                    try:
                        page.click(selector, timeout=5_000)
                        page.wait_for_timeout(500)
                    except PlaywrightError:
                        logger.debug("Khong click duoc selector %s tren %s", selector, url)

                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=5_000)
                    except PlaywrightError:
                        logger.debug("wait_selector %s khong xuat hien tren %s", wait_selector, url)

                html = page.content()
                final_url = page.url
                context.close()

                ok = status is None or status < 400
                return FetchResult(url=url, final_url=final_url, status=status, html=html, ok=ok)

            except PlaywrightError as exc:
                last_error = str(exc)
                if context is not None:
                    context.close()
                if attempt < max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue

        return FetchResult(url=url, final_url=url, status=None, html="", ok=False, error=last_error)
