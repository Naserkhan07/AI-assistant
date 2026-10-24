"""
Nixi App Launcher
Launches Windows applications, tools, and system shortcuts by voice or text.
"""
from __future__ import annotations

import os
import subprocess
import shutil

APP_MAP = {
    "notepad": "notepad.exe",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "firefox": "firefox",
    "brave": "brave",
    "terminal": "wt.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "spotify": "spotify",
    "explorer": "explorer.exe",
    "files": "explorer.exe",
    "file manager": "explorer.exe",
    "settings": "start ms-settings:",
    "task manager": "taskmgr.exe",
    "paint": "mspaint.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "discord": "discord",
    "slack": "slack",
    "steam": "steam",
}

class AppLauncher:
    @staticmethod
    def launch(app_name: str) -> tuple[bool, str]:
        """Launch an application given a common name."""
        name = app_name.strip().lower()
        # Direct lookup
        target = APP_MAP.get(name)

        if not target:
            # Fuzzy match
            for k, v in APP_MAP.items():
                if k in name or name in k:
                    target = v
                    break

        if not target:
            target = name

        try:
            if target.startswith("start "):
                os.system(target)
                return True, f"Opening {name}"
            
            # Try startfile (Windows standard URI / registered apps)
            try:
                os.startfile(target)
                return True, f"Opening {name}"
            except Exception:
                # Fallback to subprocess
                subprocess.Popen(target, shell=True)
                return True, f"Opening {name}"
        except Exception as e:
            return False, f"Could not launch '{name}': {str(e)}"
