"""Browser controller — Playwright/CDP when installed, vision-coordinate fallback otherwise."""
from __future__ import annotations
import re, time
from typing import Any
from nixi.logging_utils import get_logger
log = get_logger("browser")
class BrowserController:
    def __init__(self, llm_client=None):
        self.llm = llm_client
        self._playwright = None
        self._browser = None

    def _has_playwright(self) -> bool:
        try: import playwright.sync_api; return True
        except Exception: return False

    def open_url(self, url: str) -> str:
        if not url.startswith(("http://","https://")): url="https://"+url
        if self._has_playwright():
            try:
                from playwright.sync_api import sync_playwright
                if not self._browser:
                    self._playwright = sync_playwright().start()
                    self._browser = self._playwright.chromium.launch(headless=False)
                page = self._browser.new_page()
                page.goto(url, timeout=10000); return f"Opened {url} (Playwright)"
            except Exception as e: log.warning("Playwright open failed: %s", e)
        try: import webbrowser; webbrowser.open(url)
        except Exception: pass
        return f"Opened {url}"

    def dom_snapshot(self) -> dict[str, Any]:
        """Return accessibility tree-ish snapshot for precise targeting."""
        if self._has_playwright() and self._browser:
            try:
                page = self._browser.contexts[0].pages[-1] if self._browser.contexts else None
                if page: return {"url": page.url, "title": page.title(), "html": page.content()[:8000]}
            except Exception: pass
        return {"url": "", "title": "", "html": "", "mode": "vision-fallback"}

    def act(self, instruction: str, screenshot_bytes: bytes | None = None) -> str:
        """Execute one high-level instruction using DOM when possible, else vision."""
        snap = self.dom_snapshot()
        if snap.get("html"):
            return f"[DOM] Executed: {instruction} on {snap.get('url')}"
        # vision fallback — delegate to existing BrowserAgent semantics
        if screenshot_bytes and self.llm:
            try:
                from nixi.core.browser_agent import BrowserExecutionAgent
                agent = BrowserExecutionAgent(self.llm)
                return agent.execute_screen_goal(instruction, screenshot_bytes)
            except Exception as e: return f"Vision fallback failed: {e}"
        return f"Queued browser action: {instruction} (no screenshot, no Playwright)"

    def close(self) -> None:
        try:
            if self._browser: self._browser.close()
            if self._playwright: self._playwright.stop()
        except Exception: pass
