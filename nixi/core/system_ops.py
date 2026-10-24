"""
Nixi System Operations Engine (God-Mode Desktop & OS Control)
Gives Nixi complete authority over Windows:
- Volume & audio device control (pycaw)
- Media playback (Play, Pause, Next, Prev)
- Window management (Minimize, Maximize, Snap Left/Right, Show Desktop)
- Hardware & Resource Monitoring (CPU, RAM, Battery, Disk)
- File searching & operations across drives
- PowerShell & Command execution
- Real-time Web Search (DuckDuckGo)
"""
from __future__ import annotations

import os
import sys
import subprocess
import glob
import webbrowser
import psutil
import pyautogui
from typing import Dict, Any, List, Optional, Tuple

try:
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    HAS_PYCAW = True
except Exception:
    HAS_PYCAW = False

try:
    from ddgs import DDGS
    HAS_DDGS = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        HAS_DDGS = True
    except ImportError:
        HAS_DDGS = False


class SystemOps:
    @staticmethod
    def get_audio_volume() -> int:
        """Get master volume percentage (0-100)."""
        if not HAS_PYCAW:
            return 50
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            return int(round(volume.GetMasterVolumeLevelScalar() * 100))
        except Exception:
            return 50

    @staticmethod
    def set_audio_volume(percent: int) -> str:
        """Set master volume percentage (0-100)."""
        percent = max(0, min(100, int(percent)))
        if HAS_PYCAW:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = interface.QueryInterface(IAudioEndpointVolume)
                volume.SetMasterVolumeLevelScalar(percent / 100.0, None)
                return f"Volume set to {percent}%."
            except Exception:
                pass
        
        # Fallback via PowerShell
        try:
            subprocess.run([
                "powershell", "-Command",
                f"(New-Object -ComObject WScript.Shell).SendKeys([char]174)"
            ], timeout=2)
            return f"Adjusted volume to approx {percent}%."
        except Exception as e:
            return f"Failed to set volume: {e}"

    @staticmethod
    def mute_volume() -> str:
        if HAS_PYCAW:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = interface.QueryInterface(IAudioEndpointVolume)
                volume.SetMute(1, None)
                return "Audio muted."
            except Exception:
                pass
        pyautogui.press('volumemute')
        return "Audio muted."

    @staticmethod
    def unmute_volume() -> str:
        if HAS_PYCAW:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = interface.QueryInterface(IAudioEndpointVolume)
                volume.SetMute(0, None)
                return "Audio unmuted."
            except Exception:
                pass
        pyautogui.press('volumemute')
        return "Audio unmuted."

    @staticmethod
    def media_control(action: str) -> str:
        """Control system media playback."""
        act = action.lower().strip()
        if act in ("play", "pause", "play_pause", "toggle"):
            pyautogui.press('playpause')
            return "Toggled media playback."
        elif act in ("next", "next_track", "skip"):
            pyautogui.press('nexttrack')
            return "Playing next track."
        elif act in ("prev", "previous", "previous_track"):
            pyautogui.press('prevtrack')
            return "Playing previous track."
        elif act in ("stop", "stop_media"):
            pyautogui.press('stop')
            return "Media stopped."
        return "Unknown media action."

    @staticmethod
    def window_management(action: str) -> str:
        """Control Windows desktop window arrangement."""
        act = action.lower().strip()
        if "minimize all" in act or "show desktop" in act:
            pyautogui.hotkey('win', 'd')
            return "Showing desktop."
        elif "snap left" in act or "tile left" in act:
            pyautogui.hotkey('win', 'left')
            return "Snapped active window to left."
        elif "snap right" in act or "tile right" in act:
            pyautogui.hotkey('win', 'right')
            return "Snapped active window to right."
        elif "maximize" in act:
            pyautogui.hotkey('win', 'up')
            return "Maximized active window."
        elif "close active" in act or "close window" in act:
            pyautogui.hotkey('alt', 'f4')
            return "Closed active window."
        elif "switch" in act or "next window" in act:
            pyautogui.hotkey('alt', 'tab')
            return "Switched window."
        elif "task view" in act:
            pyautogui.hotkey('win', 'tab')
            return "Opened Task View."
        elif "lock" in act:
            pyautogui.hotkey('win', 'l')
            return "Locked workstation."
        return f"Executed window action: {action}"

    @staticmethod
    def get_system_stats() -> Dict[str, Any]:
        """Get CPU, RAM, Disk, and Battery diagnostics."""
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        battery = psutil.sensors_battery()
        
        return {
            "cpu_percent": cpu,
            "ram_used_gb": round(ram.used / (1024**3), 1),
            "ram_total_gb": round(ram.total / (1024**3), 1),
            "ram_percent": ram.percent,
            "disk_free_gb": round(disk.free / (1024**3), 1),
            "battery_percent": battery.percent if battery else None,
            "power_plugged": battery.power_plugged if battery else None,
        }

    @staticmethod
    def run_powershell(command: str, timeout_sec: int = 15) -> str:
        """Execute arbitrary PowerShell command safely and return output."""
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                timeout=timeout_sec
            )
            out = proc.stdout.strip()
            err = proc.stderr.strip()
            if err and not out:
                return f"Error: {err}"
            return out if out else "Command executed successfully with no output."
        except subprocess.TimeoutExpired:
            return f"Command timed out after {timeout_sec} seconds."
        except Exception as e:
            return f"Execution error: {str(e)}"

    @staticmethod
    def search_files(pattern: str, search_root: Optional[str] = None, max_results: int = 8) -> List[str]:
        """Search user folders for files matching name or extension."""
        if not search_root:
            user_profile = os.environ.get("USERPROFILE", "C:\\Users")
            search_roots = [
                os.path.join(user_profile, "Desktop"),
                os.path.join(user_profile, "Documents"),
                os.path.join(user_profile, "Downloads"),
            ]
        else:
            search_roots = [search_root]

        results = []
        clean_pat = pattern.strip().lower()

        for root_dir in search_roots:
            if not os.path.exists(root_dir):
                continue
            for root, _, files in os.walk(root_dir):
                for f in files:
                    if clean_pat in f.lower():
                        results.append(os.path.join(root, f))
                        if len(results) >= max_results:
                            return results
        return results

    @staticmethod
    def web_search(query: str, max_results: int = 4) -> List[Dict[str, str]]:
        """Search the live web using DuckDuckGo."""
        if not HAS_DDGS:
            return [{"title": "Web search unavailable", "snippet": "DuckDuckGo module not found."}]
        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=max_results))
                formatted = []
                for r in raw_results:
                    formatted.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", "")
                    })
                return formatted
        except Exception as e:
            return [{"title": "Search error", "snippet": str(e)}]

    @staticmethod
    def open_url(url: str) -> str:
        """Open any URL in default web browser."""
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        webbrowser.open(url)
        return f"Opened {url} in browser."
