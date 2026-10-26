"""Bounded browser controller: real Playwright DOM actions or explicit failure."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from nixi.logging_utils import get_logger

log = get_logger("browser")


class BrowserController:
    def __init__(self, llm_client=None):
        self.llm = llm_client
        self._playwright = None
        self._browser = None
        self._page = None

    @staticmethod
    def _has_playwright() -> bool:
        try:
            import playwright.sync_api  # noqa: F401
            return True
        except Exception:
            return False

    def open_url(self, url: str) -> str:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "Only valid HTTP or HTTPS addresses can be opened."
        if self._has_playwright():
            try:
                from playwright.sync_api import sync_playwright
                if not self._browser:
                    self._playwright = sync_playwright().start()
                    self._browser = self._playwright.chromium.launch(headless=False)
                context = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
                self._page = context.new_page()
                self._page.goto(url, timeout=15000, wait_until="domcontentloaded")
                return f"Loaded {self._page.url} — {self._page.title()[:160]}"
            except Exception as exc:
                log.warning("Playwright open failed: %s", exc)
        try:
            import webbrowser
            if webbrowser.open(url):
                return f"Sent the URL to your default browser: {url}. I can't verify that its window opened."
            return f"The default browser did not accept the open request for {url}."
        except Exception as exc:
            return f"Could not open the URL: {exc}"

    def dom_snapshot(self) -> dict[str, Any]:
        """Return a compact live-page snapshot for precise targeting."""
        page = self._page
        if page:
            try:
                return {"url": page.url, "title": page.title(), "text": page.locator("body").inner_text(timeout=2500)[:8000]}
            except Exception as exc:
                return {"url": page.url, "title": "", "text": "", "error": str(exc)}
        return {"url": "", "title": "", "text": "", "mode": "no-controlled-page"}

    @staticmethod
    def _clean(value: str) -> str:
        value = value.strip().rstrip(".!?")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'", "`"}:
            value = value[1:-1]
        return value.strip()

    def _locator(self, target: str):
        page = self._page
        target = self._clean(target)
        role = None
        match = re.match(r"^(button|link|textbox|field|checkbox|tab)\s+(.+)$", target, re.I)
        if match:
            role, target = match.group(1).lower(), self._clean(match.group(2))
        if role in {"field", "textbox"}:
            candidates = [page.get_by_label(target, exact=False), page.get_by_placeholder(target, exact=False), page.get_by_role("textbox", name=target, exact=False)]
        elif role:
            candidates = [page.get_by_role(role, name=target, exact=False)]
        else:
            candidates = [page.get_by_label(target, exact=False), page.get_by_placeholder(target, exact=False), page.get_by_role("button", name=target, exact=False), page.get_by_role("link", name=target, exact=False), page.get_by_text(target, exact=True)]
        for locator in candidates:
            try:
                if locator.count() and locator.first.is_visible():
                    return locator.first
            except Exception:
                continue
        return None

    def act(self, instruction: str, screenshot_bytes: bytes | None = None) -> str:
        """Run supported DOM actions; refuse to claim success without a live target."""
        if not self._page:
            if screenshot_bytes and self.llm:
                try:
                    from nixi.core.browser_agent import BrowserExecutionAgent
                    return BrowserExecutionAgent(self.llm).execute_screen_goal(instruction, screenshot_bytes)
                except Exception as exc:
                    return f"Screen action failed: {exc}"
            return "No controlled browser page is open; no browser action was performed. Open a URL first."

        command = instruction.strip()
        if re.match(r"^(open|navigate to)\s+", command, re.I):
            url = re.sub(r"^(open|navigate to)\s+", "", command, flags=re.I)
            return self.open_url(url)
        if re.fullmatch(r"(?:read|show|get)\s+(?:the\s+)?(?:page|page text|current page)", command, re.I):
            snap = self.dom_snapshot()
            return f"{snap.get('title', '')}\n{snap.get('text', '')}"[:8200]
        key_match = re.fullmatch(r"press\s+(enter|tab|escape|esc|backspace|delete|arrowup|arrowdown|arrowleft|arrowright)", command, re.I)
        if key_match:
            try:
                key = key_match.group(1).lower().replace("esc", "escape")
                self._page.keyboard.press(key)
                return f"Sent {key} to the active page. Current URL: {self._page.url}"
            except Exception as exc:
                return f"Could not send the key: {exc}"

        fill = re.match(r"^(?:type|fill|enter)\s+(.+?)\s+(?:into|in)\s+(.+)$", command, re.I)
        if fill:
            value, target = self._clean(fill.group(1)), self._clean(fill.group(2))
        else:
            fill = re.match(r"^fill\s+(.+?)\s+with\s+(.+)$", command, re.I)
            if fill:
                target, value = self._clean(fill.group(1)), self._clean(fill.group(2))
            else:
                target = value = ""
        if fill:
            locator = self._locator(target)
            if locator is None:
                return f"Couldn't uniquely identify a visible field named '{target}'; nothing was typed."
            try:
                locator.fill(value, timeout=4000)
                actual = locator.input_value(timeout=2000)
                return f"Filled '{target}' and verified the field value." if actual == value else f"Filled '{target}', but field verification did not match."
            except Exception as exc:
                return f"Could not fill '{target}': {exc}"

        click = re.match(r"^click(?:\s+on)?\s+(?:the\s+)?(.+)$", command, re.I)
        if click:
            target = self._clean(click.group(1))
            locator = self._locator(target)
            if locator is None:
                return f"Couldn't identify a visible control named '{target}'; nothing was clicked."
            try:
                locator.click(timeout=4000)
                return f"Clicked the visible control '{target}'. Current page: {self._page.url} — {self._page.title()[:120]}"
            except Exception as exc:
                return f"Could not click '{target}': {exc}"

        return "Unsupported browser action. Try 'click [button/link]', 'fill [field] with [text]', 'type [text] into [field]', 'press Enter', or 'read page'. No action was performed."

    def close(self) -> None:
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            log.debug("Browser shutdown issue", exc_info=True)
        self._page = self._browser = self._playwright = None
