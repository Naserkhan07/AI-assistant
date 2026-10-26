"""
Nixi God-Mode Autonomous Agent
Enables Nixi to execute ANY operation anywhere:
- Full Windows system controls (Volume, Media, Windows, Hardware, Power)
- Web automation & real-time Web Search (DuckDuckGo, URL navigation)
- Shell & PowerShell execution
- Screen vision & GUI automation (PyAutoGUI, Clipboard, Bilinear screen reading)
- Intelligent routing with instant sub-50ms fast paths + Autonomous LLM Tool-Calling
"""
from __future__ import annotations

import re
import json
import time
import os
from nixi.compat.optional import load
from nixi.compat import fakes
pyautogui = load("pyautogui", fakes.FakePyAutoGUI())
pyperclip = load("pyperclip", fakes.FakePyperclip())
try:
    pyautogui.FAILSAFE = False; pyautogui.PAUSE = 0.02
except Exception: pass
from typing import Dict, Any, List, Optional, Tuple, Callable

from .system_ops import SystemOps
from .app_launcher import AppLauncher
from .screen_reader import ScreenReader
from .browser_agent import BrowserExecutionAgent


class GodModeAgent:
    def __init__(self, llm_client):
        self.llm = llm_client
        self.system = SystemOps()
        self.app_launcher = AppLauncher()
        self.browser_agent = BrowserExecutionAgent(self.llm)
        self.screen_reader = ScreenReader()

    def process_command(self, cmd: str, on_voice_feedback: Optional[Callable[[str], None]] = None) -> Tuple[bool, str]:
        """
        Processes any command with instant local fast paths or autonomous tool reasoning.
        Returns: (is_handled: bool, result_summary: str)
        """
        raw = cmd.strip()
        lower = raw.lower()

        # -------------------------------------------------------------
        # 1. AUDIO & VOLUME CONTROL (Instant < 20ms)
        # -------------------------------------------------------------
        if lower in ("mute", "mute volume", "mute audio", "silence"):
            return True, self.system.mute_volume()
        elif lower in ("unmute", "unmute volume", "unmute audio"):
            return True, self.system.unmute_volume()

        vol_set_match = re.search(r"(?:set\s+)?volume\s+(?:to\s+)?(\d{1,3})%?", lower)
        if vol_set_match:
            pct = int(vol_set_match.group(1))
            return True, self.system.set_audio_volume(pct)

        if "volume up" in lower or "increase volume" in lower:
            current = self.system.get_audio_volume()
            return True, self.system.set_audio_volume(current + 10)
        elif "volume down" in lower or "decrease volume" in lower or "lower volume" in lower:
            current = self.system.get_audio_volume()
            return True, self.system.set_audio_volume(current - 10)

        # -------------------------------------------------------------
        # 2. MEDIA PLAYBACK CONTROL (Instant < 20ms)
        # -------------------------------------------------------------
        if lower in ("play", "pause", "resume", "pause music", "play music", "toggle music"):
            return True, self.system.media_control("play_pause")
        elif lower in ("next song", "next track", "skip track", "skip song", "next"):
            return True, self.system.media_control("next")
        elif lower in ("previous song", "prev track", "previous track", "previous"):
            return True, self.system.media_control("prev")

        # -------------------------------------------------------------
        # 3. WINDOW & DESKTOP MANAGEMENT (Instant < 20ms)
        # -------------------------------------------------------------
        if lower in ("show desktop", "minimize all", "minimize all windows", "hide all"):
            return True, self.system.window_management("minimize all")
        elif lower in ("tile left", "snap left", "window left"):
            return True, self.system.window_management("snap left")
        elif lower in ("tile right", "snap right", "window right"):
            return True, self.system.window_management("snap right")
        elif lower in ("maximize", "maximize window"):
            return True, self.system.window_management("maximize")
        elif lower in ("close active window", "close window", "close this"):
            return True, self.system.window_management("close active")
        elif lower in ("switch window", "alt tab", "next window"):
            return True, self.system.window_management("switch")
        elif lower in ("lock pc", "lock computer", "lock screen", "lock workstation"):
            return True, self.system.window_management("lock")

        # -------------------------------------------------------------
        # 4. SYSTEM DIAGNOSTICS & HARDWARE STATS
        # -------------------------------------------------------------
        if re.search(r"\b(system\s+status|hardware\s+status|cpu\s+usage|ram\s+usage|battery|system\s+stats)\b", lower):
            stats = self.system.get_system_stats()
            bat_str = f", Battery: {stats['battery_percent']}%" if stats['battery_percent'] is not None else ""
            msg = f"CPU: {stats['cpu_percent']}%, RAM: {stats['ram_used_gb']}GB / {stats['ram_total_gb']}GB ({stats['ram_percent']}%), Disk Free: {stats['disk_free_gb']}GB{bat_str}."
            return True, msg

        # Instant Time and Date
        if lower in ("what time is it", "what is the time", "current time", "tell me the time", "time"):
            import datetime
            now_str = datetime.datetime.now().strftime("%I:%M %p")
            return True, f"The current time is {now_str}."
        elif "date" in lower or lower in ("what day is it", "today's day"):
            import datetime
            date_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
            return True, f"Today is {date_str}."

        # -------------------------------------------------------------
        # 5. OPEN WEBSITES / POPULAR HUBS DIRECTLY
        # -------------------------------------------------------------
        POPULAR_SITES = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "github": "https://www.github.com",
            "reddit": "https://www.reddit.com",
            "twitter": "https://www.x.com",
            "x": "https://www.x.com",
            "netflix": "https://www.netflix.com",
            "amazon": "https://www.amazon.com",
            "chatgpt": "https://chatgpt.com",
            "instagram": "https://www.instagram.com",
            "facebook": "https://www.facebook.com",
            "linkedin": "https://www.linkedin.com",
            "wikipedia": "https://www.wikipedia.org",
            "twitch": "https://www.twitch.tv",
            "gmail": "https://mail.google.com",
            "whatsapp": "https://web.whatsapp.com",
        }

        site_open_match = re.search(r"^(?:open|go\s+to|launch|visit)\s+(?:the\s+)?([a-zA-Z0-9]+)$", lower)
        if site_open_match:
            site_key = site_open_match.group(1).strip()
            if site_key in POPULAR_SITES:
                return True, self.system.open_url(POPULAR_SITES[site_key])

        web_match = re.search(r"^(?:open|go\s+to|visit)\s+(?:https?://)?([a-zA-Z0-9-]+\.(?:com|org|net|io|dev|edu|ai|gov)[^\s]*)$", lower)
        if web_match:
            target_url = web_match.group(1)
            return True, self.system.open_url(target_url)

        # -------------------------------------------------------------
        # 6. YOUTUBE MUSIC & VIDEO SEARCH & PLAY
        # -------------------------------------------------------------
        if "youtube" in lower and ("play" in lower or "search" in lower or "find" in lower):
            yt_query = re.sub(r"^(?:play|search(?:\s+for)?|find)\s+", "", lower)
            yt_query = re.sub(r"\s+(?:on|in)\s+youtube$", "", yt_query).replace("youtube", "").strip()
            if yt_query:
                import urllib.parse
                yt_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(yt_query)}"
                self.system.open_url(yt_url)
                return True, f"Searching and playing '{yt_query}' on YouTube."

        # -------------------------------------------------------------
        # 7. AGENT REACH WEB PAGE READER & YOUTUBE TRANSCRIPT
        # -------------------------------------------------------------
        read_match = re.search(r"^(?:read(?:\s+the)?\s+(?:webpage|page|link|article|url)?|fetch(?:\s+page)?)\s+(https?://[^\s]+)$", lower)
        if read_match:
            target_url = read_match.group(1).strip()
            if on_voice_feedback:
                on_voice_feedback("Reading web page.")
            content = self.system.read_webpage(target_url, max_chars=1200)
            if content:
                summary = f"Summary from {target_url}:\n{content[:350]}..."
                return True, summary
            return True, f"Could not extract clean text from {target_url}."

        yt_match = re.search(r"^(?:summarize\s+video|video\s+details|youtube\s+summary)\s+(https?://[^\s]+)$", lower)
        if yt_match:
            target_url = yt_match.group(1).strip()
            if on_voice_feedback:
                on_voice_feedback("Extracting video information.")
            yt_info = self.system.get_youtube_transcript(target_url)
            return True, yt_info

        if lower in ("agent reach doctor", "reach doctor", "check internet reach", "agent reach status"):
            out = self.system.run_powershell("app\\.venv\\Scripts\\agent-reach.exe doctor")
            return True, f"Agent Reach Status:\n{out[:400]}"

        # -------------------------------------------------------------
        # 8. EXA NEURAL & LIVE WEB SEARCH
        # -------------------------------------------------------------
        search_match = re.search(r"^(?:search(?:\s+the\s+web)?(?:\s+for)?|google|look\s+up|exa(?:\s+search)?)\s+(.+)$", lower)
        if search_match:
            query = search_match.group(1).strip()
            if on_voice_feedback:
                on_voice_feedback("Searching the web.")
            results = self.system.web_search(query, max_results=3)
            if results and results[0].get("snippet") and not results[0].get("snippet").startswith("No search"):
                top = results[0]
                summary = f"According to Exa search for '{query}': {top['snippet'][:250]}"
                return True, summary
            else:
                self.system.open_url(f"https://www.google.com/search?q={query}")
                return True, f"Searching Google for: {query}"

        # -------------------------------------------------------------
        # 9. POWERSHELL / COMMAND EXECUTION
        # -------------------------------------------------------------
        sh_match = re.search(r"^(?:run\s+powershell|powershell|cmd|terminal|exec|execute\s+command)\s+(.+)$", raw, re.IGNORECASE)
        if sh_match:
            sh_cmd = sh_match.group(1).strip()
            # Shell is powerful: require the configured confirmation policy before execution.
            permissions = getattr(self, "permissions", None)
            if permissions is not None:
                from nixi.security.permissions import RiskLevel
                decision = permissions.authorize("run_shell", RiskLevel.HIGH, {"command": sh_cmd})
                if not decision.allowed:
                    return True, f"Not run: {decision.reason}. You can allow shell commands in Settings if you choose."
            if on_voice_feedback:
                on_voice_feedback("Running the approved command.")
            out = self.system.run_powershell(sh_cmd)
            return True, f"Output:\n{out[:400]}"

        # -------------------------------------------------------------
        # 10. FILE SEARCH (Desktop, Documents, Downloads)
        # -------------------------------------------------------------
        find_match = re.search(r"^(?:find\s+file|search\s+file|where\s+is\s+file|locate)\s+(.+)$", lower)
        if find_match:
            query_file = find_match.group(1).strip()
            found = self.system.search_files(query_file)
            if found:
                first = found[0]
                return True, f"Found {len(found)} file(s). Top match: {first}"
            return True, f"No files matching '{query_file}' found in Desktop, Documents, or Downloads."

        # -------------------------------------------------------------
        # 11. DESKTOP & BROWSER FORM/TABLE AUTOMATION (Specific action intent)
        # -------------------------------------------------------------
        gui_intent = (
            re.search(r"^(?:please\s+)?(?:click(?:\s+on)?|press(?:\s+the)?\s+(?:button|key|enter|tab|esc|escape|space)|fill(?:\s+out|\s+in)?(?:\s+the)?\s+(?:form|box|boxes|field)|type\s+['\"].+['\"]\s+in|submit(?:\s+the)?\s+form)\b", lower)
            or (("click" in lower or "double click" in lower) and ("button" in lower or "link" in lower or "icon" in lower or "on " in lower))
            or ("fill" in lower and ("form" in lower or "field" in lower or "boxes" in lower or "input" in lower))
        )
        if gui_intent:
            if on_voice_feedback:
                on_voice_feedback("Executing on screen.")
            time.sleep(0.06)
            img_bytes = self.screen_reader.capture_screen()
            summary = self.browser_agent.execute_screen_goal(raw, img_bytes)
            return True, summary

        # -------------------------------------------------------------
        # 12. SCREEN VISION (Explain/Inspect active view)
        # -------------------------------------------------------------
        if lower in ("read screen", "what is on my screen", "look at this", "inspect screen", "explain this"):
            if on_voice_feedback:
                on_voice_feedback("Analyzing screen.")
            time.sleep(0.06)
            img_bytes = self.screen_reader.capture_screen()
            analysis = self.llm.analyze_screen(img_bytes)
            return True, analysis

        # Not matched by fast local paths -> Pass to general conversational LLM
        return False, ""
