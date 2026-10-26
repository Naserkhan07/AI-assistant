"""Bounded browser controller: real Playwright DOM actions or explicit failure."""
from __future__ import annotations

import os
import queue
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlsplit

from nixi.logging_utils import get_logger

log = get_logger("browser")


class BrowserController:
    def __init__(self, llm_client=None, obscura_bin: str | None = None, data_dir: str | Path | None = None):
        self.llm = llm_client
        self._playwright = None
        self._browser = None
        self._page = None
        self._obscura_process = None
        self._command_queue: queue.Queue = queue.Queue()
        self._worker: threading.Thread | None = None
        self._worker_ident: int | None = None
        self._worker_lock = threading.Lock()
        self._closed = False
        self._obscura_bin = self._resolve_obscura_bin(obscura_bin, data_dir)
        try:
            self._obscura_port = max(1024, min(65535, int(os.getenv("NIXI_OBSCURA_PORT", "9222"))))
        except ValueError:
            self._obscura_port = 9222

    def _submit(self, method: str, *args):
        if threading.get_ident() == self._worker_ident:
            return getattr(self, method)(*args)
        with self._worker_lock:
            if self._closed and method != "_shutdown":
                return "Browser controller is closed; restart Nixi to reconnect."
            if not self._worker or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._worker_loop, name="nixi-browser", daemon=True)
                self._worker.start()
        completed = threading.Event()
        result: dict[str, Any] = {}
        self._command_queue.put((method, args, completed, result))
        if not completed.wait(75.0):
            return "Browser operation timed out. No additional action was attempted."
        if "error" in result:
            return f"Browser operation failed: {result['error']}"
        return result.get("value", "")

    def _worker_loop(self):
        self._worker_ident = threading.get_ident()
        while True:
            item = self._command_queue.get()
            if item is None:
                break
            method, args, completed, result = item
            try:
                result["value"] = getattr(self, method)(*args)
            except Exception as exc:
                result["error"] = str(exc)
            finally:
                completed.set()
        self._worker_ident = None

    @staticmethod
    def _resolve_obscura_bin(explicit: str | None, data_dir: str | Path | None) -> str | None:
        candidates = [explicit, os.getenv("NIXI_OBSCURA_BIN")]
        if data_dir:
            candidates.append(str(Path(data_dir) / "integrations" / "bin" / ("obscura.exe" if os.name == "nt" else "obscura")))
        candidates.append(shutil.which("obscura"))
        for raw in candidates:
            if raw and Path(raw).expanduser().is_file():
                return str(Path(raw).expanduser().resolve())
        return None

    def _ensure_browser(self):
        if self._browser:
            return self._browser
        if not self._has_playwright():
            return None
        from playwright.sync_api import sync_playwright
        if not self._playwright:
            self._playwright = sync_playwright().start()
        chromium = self._playwright.chromium
        endpoint = f"http://127.0.0.1:{self._obscura_port}"
        if self._obscura_bin:
            try:
                self._browser = chromium.connect_over_cdp(endpoint, timeout=1500)
            except Exception:
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
                try:
                    self._obscura_process = subprocess.Popen(
                        [self._obscura_bin, "serve", "--port", str(self._obscura_port)],
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        close_fds=True, shell=False, creationflags=flags,
                    )
                    for _ in range(40):
                        if self._obscura_process.poll() is not None:
                            break
                        try:
                            self._browser = chromium.connect_over_cdp(endpoint, timeout=1000)
                            break
                        except Exception:
                            time.sleep(0.25)
                except Exception as exc:
                    log.warning("Obscura could not start: %s", exc)
        if not self._browser:
            try:
                self._browser = chromium.launch(headless=False)
            except Exception as exc:
                log.warning("No controlled browser backend is available: %s", exc)
        return self._browser

    @staticmethod
    def _has_playwright() -> bool:
        try:
            import playwright.sync_api  # noqa: F401
            return True
        except Exception:
            return False

    def open_url(self, url: str) -> str:
        return self._submit("_open_url", url)

    def _open_url(self, url: str) -> str:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "Only valid HTTP or HTTPS addresses can be opened."
        if self._has_playwright():
            try:
                browser = self._ensure_browser()
                if browser:
                    context = browser.contexts[0] if browser.contexts else browser.new_context()
                    self._page = context.new_page()
                    self._page.goto(url, timeout=20000, wait_until="domcontentloaded")
                    return f"Loaded {self._page.url} — {self._page.title()[:160]}"
            except Exception as exc:
                log.warning("Controlled browser open failed: %s", exc)
        try:
            import webbrowser
            if webbrowser.open(url):
                return f"Sent the URL to your default browser: {url}. I can't verify that its window opened."
            return f"The default browser did not accept the open request for {url}."
        except Exception as exc:
            return f"Could not open the URL: {exc}"

    def search_web(self, query: str, engine: str = "duckduckgo") -> str:
        return self._submit("_search_web", query, engine)

    def _search_web(self, query: str, engine: str = "duckduckgo") -> str:
        query = str(query or "").strip()
        if not query or len(query) > 500:
            return "Provide a web search query of 1-500 characters."
        engines = {
            "duckduckgo": "https://html.duckduckgo.com/html/?q=",
            "bing": "https://www.bing.com/search?q=",
            "google": "https://www.google.com/search?q=",
        }
        base = engines.get(str(engine).lower())
        if not base:
            return "Supported search engines: DuckDuckGo, Bing, or Google."
        result = self._open_url(base + quote_plus(query))
        if self._page:
            snapshot = self._dom_snapshot()
            text = str(snapshot.get("text", ""))[:4500]
            return f"{result}\nSearch page text (untrusted):\n{text}" if text else result
        return result

    def dom_snapshot(self) -> dict[str, Any]:
        """Return a compact live-page snapshot for precise targeting."""
        return self._submit("_dom_snapshot")

    def _dom_snapshot(self) -> dict[str, Any]:
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
        return self._submit("_act", instruction, screenshot_bytes)

    def _act(self, instruction: str, screenshot_bytes: bytes | None = None) -> str:
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
            return self._open_url(url)
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
        if self._closed:
            return
        self._closed = True
        if self._worker and self._worker.is_alive():
            self._submit("_shutdown")
            self._command_queue.put(None)
            if threading.get_ident() != self._worker_ident:
                self._worker.join(timeout=3.0)
        else:
            self._shutdown()

    def _shutdown(self) -> None:
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            log.debug("Browser shutdown issue", exc_info=True)
        process, self._obscura_process = self._obscura_process, None
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()
        self._page = self._browser = self._playwright = None
