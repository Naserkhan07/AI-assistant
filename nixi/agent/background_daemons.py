"""Proactive daemons — battery, clipboard, and configurable daily briefing."""
from __future__ import annotations

import datetime
import re
import threading
import time
from typing import Any, Callable

from nixi.config import NixiConfig, get_config
from nixi.platform.capabilities import has_module
from nixi.platform.system import system_stats
from nixi.logging_utils import get_logger

log = get_logger("daemons")


class BatteryGuardianDaemon:
    def __init__(self, on_warning: Callable[[str], None] | None = None,
                 check_interval: float = 60.0, config: NixiConfig | None = None):
        self.on_warning = on_warning
        self.check_interval = check_interval
        self.config = config or get_config()
        self._running = False
        self._thread: threading.Thread | None = None
        self._has_warned_20 = False
        self._has_warned_10 = False

    def start(self) -> None:
        if self._running or not self.config.battery_enabled:
            return
        if not has_module("psutil"):
            log.info("Battery daemon: psutil unavailable, disabled")
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="BatteryGuardian")
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        import psutil
        while self._running:
            try:
                battery = psutil.sensors_battery()
                if battery is not None:
                    pct, plugged = battery.percent, battery.power_plugged
                    if plugged:
                        self._has_warned_20 = self._has_warned_10 = False
                    elif pct <= 10 and not self._has_warned_10:
                        self._has_warned_10 = True
                        if self.on_warning:
                            self.on_warning(f"Critical Battery: {pct}% remaining — please plug in!")
                    elif pct <= 20 and not self._has_warned_20:
                        self._has_warned_20 = True
                        if self.on_warning:
                            self.on_warning(f"Battery low: {pct}%. Consider enabling battery saver.")
            except Exception:
                pass
            time.sleep(self.check_interval)


class ClipboardWatcherDaemon:
    def __init__(self, on_chip_detected: Callable[[dict], None] | None = None,
                 poll_interval: float = 1.0, config: NixiConfig | None = None):
        self.on_chip_detected = on_chip_detected
        self.poll_interval = poll_interval
        self.config = config or get_config()
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_content = ""

    def start(self) -> None:
        if self._running or not self.config.clipboard_enabled:
            return
        try:
            import pyperclip
            self._last_content = pyperclip.paste()
        except Exception:
            self._last_content = ""
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ClipboardWatcher")
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        while self._running:
            try:
                import pyperclip
                curr = pyperclip.paste()
                if curr and curr != self._last_content:
                    self._last_content = curr
                    self._analyze(curr)
            except Exception:
                pass
            time.sleep(self.poll_interval)

    def _analyze(self, text: str) -> None:
        text = text.strip()
        if not text or len(text) < 4:
            return
        url_m = re.search(r"https?://\S+", text)
        if url_m and len(text) < 300:
            url = url_m.group(0)
            chip = {"type": "url", "label": "Summarize Link",
                    "preview": url[:40] + ("..." if len(url) > 40 else ""),
                    "action": f"Summarize this webpage: {url}", "data": url}
            if self.on_chip_detected:
                self.on_chip_detected(chip)
            return
        if any(k in text for k in ("Traceback (most recent call last)", "SyntaxError:", "TypeError:", "Exception:")):
            first = next((l for l in text.splitlines() if "Error" in l or "Exception" in l), "Code Error")
            chip = {"type": "error", "label": "Auto-Fix Error", "preview": first[:40],
                    "action": f"Fix this code error: {text[:600]}", "data": text}
            if self.on_chip_detected:
                self.on_chip_detected(chip)
            return
        code_markers = ("def ", "class ", "import ", "const ", "let ", "function ", "return ")
        if any(m in text for m in code_markers) and len(text.splitlines()) >= 2:
            chip = {"type": "code", "label": "Run / Explain Code",
                    "preview": text.splitlines()[0][:35],
                    "action": f"Explain or execute this code:\n{text[:500]}", "data": text}
            if self.on_chip_detected:
                self.on_chip_detected(chip)


class DailyBriefingDaemon:
    def __init__(self, on_briefing: Callable[[str], None] | None = None,
                 config: NixiConfig | None = None):
        self.on_briefing = on_briefing
        self.config = config or get_config()
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_brief_date: str | None = None

    def start(self) -> None:
        if self._running or not self.config.briefing_enabled:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="DailyBriefing")
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        while self._running:
            try:
                now = datetime.datetime.now()
                today = now.strftime("%Y-%m-%d")
                if (now.hour == self.config.briefing_hour
                        and self.config.briefing_minute <= now.minute <= self.config.briefing_minute + 5
                        and self._last_brief_date != today):
                    self._last_brief_date = today
                    brief = self.generate_briefing()
                    if self.on_briefing:
                        self.on_briefing(brief)
            except Exception:
                pass
            time.sleep(30.0)

    def generate_briefing(self) -> str:
        now = datetime.datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        stats = system_stats()
        battery_str = "Plugged in"
        if stats.get("battery_percent") is not None:
            battery_str = f"{stats['battery_percent']}% ({'Charging' if stats.get('power_plugged') else 'Battery'})"

        lines = [
            f"Good morning, {self.config.user_name}! Here is your briefing for {date_str}:",
            f"System: CPU {stats.get('cpu_percent',0)}%, RAM {stats.get('ram_percent',0)}% "
            f"({stats.get('ram_used_gb',0)}GB/{stats.get('ram_total_gb',0)}GB), Battery {battery_str}.",
        ]
        # calendar
        try:
            from nixi.integrations.calendar import CalendarReader
            cal = CalendarReader(self.config)
            lines.append(cal.format_briefing())
        except Exception:
            pass
        # weather
        try:
            from nixi.integrations.info import WeatherClient
            lines.append(WeatherClient(self.config).format_briefing())
        except Exception:
            pass
        # news
        try:
            from nixi.integrations.info import NewsClient
            lines.append(NewsClient(self.config).format_briefing())
        except Exception:
            pass
        lines.append("Ready for your commands.")
        return "\n".join(f"• {l}" if i else l for i, l in enumerate(lines))
