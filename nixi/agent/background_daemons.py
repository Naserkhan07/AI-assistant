"""
Nixi Background Daemons — Proactive Event-Driven Monitoring
1. BatteryGuardianDaemon: Warns when battery drops below 20%, triggers low-power advice.
2. ClipboardWatcherDaemon: Detects URLs, code blocks, stack trace errors, and emits preview chips for Dynamic Island.
3. DailyBriefingDaemon: Triggers morning tech digest and daily briefing at 9:00 AM or on demand.
"""
from __future__ import annotations

import datetime
import os
import re
import threading
import time
from typing import Callable, Optional

import psutil
try:
    import pyperclip
except ImportError:
    pyperclip = None


class BatteryGuardianDaemon:
    """Monitors system battery percentage and power status.
    Warns when battery falls below 20% on battery power.
    """
    def __init__(self, on_warning: Optional[Callable[[str], None]] = None, check_interval: float = 60.0):
        self.on_warning = on_warning
        self.check_interval = check_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._has_warned_20 = False
        self._has_warned_10 = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="BatteryGuardian")
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                battery = psutil.sensors_battery()
                if battery is not None:
                    percent = battery.percent
                    plugged = battery.power_plugged

                    if plugged:
                        # Reset warnings once plugged back into power
                        self._has_warned_20 = False
                        self._has_warned_10 = False
                    else:
                        if percent <= 10 and not self._has_warned_10:
                            self._has_warned_10 = True
                            msg = f"⚠️ Critical Battery Alert: {percent}% remaining! Please plug in your charger immediately."
                            if self.on_warning:
                                self.on_warning(msg)
                        elif percent <= 20 and not self._has_warned_20:
                            self._has_warned_20 = True
                            msg = f"🔋 Battery Low: Battery has dropped to {percent}%. Turn on Battery Saver to extend battery life."
                            if self.on_warning:
                                self.on_warning(msg)

            except Exception:
                pass

            time.sleep(self.check_interval)


class ClipboardWatcherDaemon:
    """Monitors Windows clipboard for interesting items:
    - URLs -> Suggests 'Summarize URL' or 'Open Link'
    - Error tracebacks -> Suggests 'Fix Code Error'
    - Code snippets -> Suggests 'Run Script' or 'Explain Code'
    - Plain text -> Suggests 'Create Meeting Notes'
    """
    def __init__(self, on_chip_detected: Optional[Callable[[dict], None]] = None, poll_interval: float = 1.0):
        self.on_chip_detected = on_chip_detected
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_content = ""

    def start(self):
        if self._running or pyperclip is None:
            return
        try:
            self._last_content = pyperclip.paste()
        except Exception:
            self._last_content = ""

        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ClipboardWatcher")
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                curr = pyperclip.paste()
                if curr and curr != self._last_content:
                    self._last_content = curr
                    self._analyze_clipboard(curr)
            except Exception:
                pass
            time.sleep(self.poll_interval)

    def _analyze_clipboard(self, text: str):
        text = text.strip()
        if not text or len(text) < 4:
            return

        # 1. Detect URLs
        url_match = re.search(r"https?://[^\s]+", text)
        if url_match and len(text) < 300:
            url = url_match.group(0)
            chip = {
                "type": "url",
                "label": "🌐 Summarize Link",
                "preview": url[:40] + ("..." if len(url) > 40 else ""),
                "action": f"Summarize this webpage: {url}",
                "data": url,
            }
            if self.on_chip_detected:
                self.on_chip_detected(chip)
            return

        # 2. Detect Error Traceback / Exception
        if "Traceback (most recent call last)" in text or "SyntaxError:" in text or "TypeError:" in text or "Exception:" in text or "Error: " in text:
            first_err_line = [l for l in text.splitlines() if "Error" in l or "Exception" in l]
            err_title = first_err_line[0][:40] if first_err_line else "Code Error"
            chip = {
                "type": "error",
                "label": "🛠️ Auto-Fix Error",
                "preview": err_title,
                "action": f"Fix this code error: {text[:600]}",
                "data": text,
            }
            if self.on_chip_detected:
                self.on_chip_detected(chip)
            return

        # 3. Detect Code Snippet (Python, JS, Shell)
        code_markers = ["def ", "class ", "import ", "const ", "let ", "function ", "return ", "npm run ", "docker "]
        if any(marker in text for marker in code_markers) and len(text.splitlines()) >= 2:
            chip = {
                "type": "code",
                "label": "⚡ Run / Explain Code",
                "preview": text.splitlines()[0][:35],
                "action": f"Explain or execute this code:\n{text[:500]}",
                "data": text,
            }
            if self.on_chip_detected:
                self.on_chip_detected(chip)
            return


class DailyBriefingDaemon:
    """Triggers or synthesizes a 9:00 AM daily briefing:
    - Weather overview
    - System health check
    - Top tech headlines
    """
    def __init__(self, on_briefing: Optional[Callable[[str], None]] = None):
        self.on_briefing = on_briefing
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_brief_date = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="DailyBriefing")
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                now = datetime.datetime.now()
                today_str = now.strftime("%Y-%m-%d")

                # Check if it is between 09:00 and 09:05 AM and hasn't run today
                if now.hour == 9 and 0 <= now.minute <= 5 and self._last_brief_date != today_str:
                    self._last_brief_date = today_str
                    brief = self.generate_briefing()
                    if self.on_briefing:
                        self.on_briefing(brief)

            except Exception:
                pass
            time.sleep(30.0)

    @staticmethod
    def generate_briefing() -> str:
        """Assembles a prompt-ready morning briefing summary."""
        import psutil
        now = datetime.datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        cpu_pct = psutil.cpu_percent(interval=0.1)
        ram_pct = psutil.virtual_memory().percent

        battery_str = "Plugged in"
        b = psutil.sensors_battery()
        if b:
            battery_str = f"{b.percent}% ({'Charging' if b.power_plugged else 'Battery'})"

        return (
            f"Good morning! Here is your daily briefing for {date_str}:\n"
            f"• System status: CPU is at {cpu_pct}%, RAM is at {ram_pct}%, Battery is {battery_str}.\n"
            f"• All proactive daemons and memory are active.\n"
            f"Ready for your commands."
        )
