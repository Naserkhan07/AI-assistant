"""System operations — volume, media, windows, diagnostics, files, web."""
from __future__ import annotations

import glob
import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Any

from nixi.config import NixiConfig, get_config
from nixi.platform.capabilities import IS_WINDOWS, has_module
from nixi.platform.system import disk_root, run_shell, system_stats
from nixi.compat.optional import load
from nixi.compat import fakes

pyautogui = load("pyautogui", fakes.FakePyAutoGUI())

try:
    from comtypes import CLSCTX_ALL  # type: ignore
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
    HAS_PYCAW = True
except Exception:
    HAS_PYCAW = False

try:
    from ddgs import DDGS  # type: ignore
    HAS_DDGS = True
except ImportError:
    try:
        from duckduckgo_search import DDGS  # type: ignore
        HAS_DDGS = True
    except ImportError:
        HAS_DDGS = False


class SystemOps:
    @staticmethod
    def get_audio_volume() -> int:
        if not HAS_PYCAW:
            return 50
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(AudioUtilities._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            return int(round(volume.GetMasterVolumeLevelScalar() * 100))
        except Exception:
            return 50

    @staticmethod
    def set_audio_volume(percent: int) -> str:
        percent = max(0, min(100, int(percent)))
        if HAS_PYCAW:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(AudioUtilities._iid_, CLSCTX_ALL, None)
                volume = interface.QueryInterface(IAudioEndpointVolume)
                volume.SetMasterVolumeLevelScalar(percent / 100.0, None)
                return f"Volume set to {percent}%."
            except Exception:
                pass
        try:
            pyautogui.press("volumemute")
            return f"Adjusted volume to approx {percent}%."
        except Exception as exc:
            return f"Failed to set volume: {exc}"

    @staticmethod
    def mute_volume() -> str:
        if HAS_PYCAW:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(AudioUtilities._iid_, CLSCTX_ALL, None)
                volume = interface.QueryInterface(IAudioEndpointVolume)
                volume.SetMute(1, None)
                return "Audio muted."
            except Exception:
                pass
        try:
            pyautogui.press("volumemute")
        except Exception:
            pass
        return "Audio muted."

    @staticmethod
    def unmute_volume() -> str:
        if HAS_PYCAW:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(AudioUtilities._iid_, CLSCTX_ALL, None)
                volume = interface.QueryInterface(IAudioEndpointVolume)
                volume.SetMute(0, None)
                return "Audio unmuted."
            except Exception:
                pass
        try:
            pyautogui.press("volumemute")
        except Exception:
            pass
        return "Audio unmuted."

    @staticmethod
    def media_control(action: str) -> str:
        act = action.lower().strip()
        mapping = {
            "play": "playpause", "pause": "playpause", "play_pause": "playpause", "toggle": "playpause",
            "next": "nexttrack", "next_track": "nexttrack", "skip": "nexttrack",
            "prev": "prevtrack", "previous": "prevtrack", "previous_track": "prevtrack",
            "stop": "stop",
        }
        key = mapping.get(act)
        if not key:
            return "Unknown media action."
        try:
            pyautogui.press(key)
        except Exception:
            pass
        return f"Media: {act}."

    @staticmethod
    def window_management(action: str) -> str:
        if not IS_WINDOWS:
            return "Window management is only available on Windows."
        act = action.lower().strip()
        try:
            if "minimize all" in act or "show desktop" in act:
                pyautogui.hotkey("win", "d")
                return "Showing desktop."
            if "snap left" in act or "tile left" in act:
                pyautogui.hotkey("win", "left")
                return "Snapped window to left."
            if "snap right" in act or "tile right" in act:
                pyautogui.hotkey("win", "right")
                return "Snapped window to right."
            if "maximize" in act:
                pyautogui.hotkey("win", "up")
                return "Maximized active window."
            if "close active" in act or "close window" in act:
                pyautogui.hotkey("alt", "f4")
                return "Closed active window."
            if "switch" in act or "next window" in act:
                pyautogui.hotkey("alt", "tab")
                return "Switched window."
            if "task view" in act:
                pyautogui.hotkey("win", "tab")
                return "Opened Task View."
            if "lock" in act:
                pyautogui.hotkey("win", "l")
                return "Locked workstation."
        except Exception as exc:
            return f"Window action failed: {exc}"
        return f"Executed window action: {action}"

    @staticmethod
    def get_system_stats() -> dict[str, Any]:
        return system_stats()

    @staticmethod
    def run_powershell(command: str, timeout_sec: int = 15) -> str:
        return run_shell(command, timeout=timeout_sec)

    @staticmethod
    def search_files(pattern: str, search_root: str | None = None, max_results: int = 8) -> list[str]:
        if search_root:
            search_roots = [search_root]
        else:
            home = Path.home()
            user_profile = os.environ.get("USERPROFILE", str(home))
            search_roots = [str(Path(user_profile) / d) for d in ("Desktop", "Documents", "Downloads")]
            # fallback for non-Windows
            if not any(Path(r).exists() for r in search_roots):
                search_roots = [str(home / d) for d in ("Desktop", "Documents", "Downloads", "")]

        results: list[str] = []
        clean = pattern.strip().lower()
        for root_dir in search_roots:
            if not os.path.exists(root_dir):
                continue
            for root, _, files in os.walk(root_dir):
                for f in files:
                    if clean in f.lower():
                        results.append(os.path.join(root, f))
                        if len(results) >= max_results:
                            return results
        return results

    @staticmethod
    def exa_search(query: str, num_results: int = 3) -> list[dict[str, str]]:
        api_key = os.getenv("EXA_API_KEY", "")
        if not api_key:
            return []
        try:
            from exa_py import Exa
            exa = Exa(api_key=api_key)
            res = exa.search(query, num_results=num_results)
            out: list[dict[str, str]] = []
            for r in res.results:
                snippet = (r.text[:300].replace("\n", " ").strip() if hasattr(r, "text") and r.text else "")
                out.append({"title": r.title or "", "url": r.url or "", "snippet": snippet})
            return out
        except Exception as exc:
            print(f"[Exa Search Error] {exc}")
            return []

    @staticmethod
    def read_webpage(url: str, max_chars: int = 1500) -> str:
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        try:
            import httpx
            jina_url = f"https://r.jina.ai/{url}"
            resp = httpx.get(jina_url, timeout=10.0, headers={"User-Agent": "Nixi-Assistant/1.0"})
            if resp.status_code == 200:
                return resp.text.strip()[:max_chars]
        except Exception as exc:
            print(f"[Jina Reader Error] {exc}")
        return ""

    @staticmethod
    def get_youtube_transcript(url: str) -> str:
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL({"skip_download": True, "quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                return f"Title: {info.get('title','Video')}\nDescription: {info.get('description','')[:400]}"
        except Exception as exc:
            return f"Video details unavailable: {exc}"

    @staticmethod
    def web_search(query: str, max_results: int = 3) -> list[dict[str, str]]:
        exa_res = SystemOps.exa_search(query, num_results=max_results)
        if exa_res:
            return exa_res
        if HAS_DDGS:
            try:
                with DDGS() as ddgs:
                    raw = list(ddgs.text(query, max_results=max_results))
                    formatted = [{"title": r.get("title",""), "url": r.get("href",""), "snippet": r.get("body","")} for r in raw]
                    if formatted:
                        return formatted
            except Exception:
                pass
        return [{"title": "Web search unavailable", "url": "", "snippet": "No results found."}]

    @staticmethod
    def open_url(url: str) -> str:
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        webbrowser.open(url)
        return f"Opened {url} in browser."
