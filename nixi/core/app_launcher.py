"""
Nixi App Launcher
Launches Windows applications, tools, and system shortcuts by voice or text.
"""
from __future__ import annotations

import os
import subprocess
import shutil

from nixi.platform.capabilities import IS_WINDOWS

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
        # The user's preference is to execute commands inside Nixi, never launch a shell UI.
        shell_names = ("powershell", "pwsh", "cmd", "command prompt", "terminal")
        if any(term in name for term in shell_names):
            return False, "Shell windows and shell commands are disabled. Ask for a supported built-in action instead."
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
            if target == "start ms-settings:":
                if not IS_WINDOWS:
                    return False, "Windows Settings is only available on Windows."
                os.startfile("ms-settings:")  # type: ignore[attr-defined]
                return True, "Windows accepted the Settings launch request."

            if target == "code":
                from nixi.integrations.vscode import VSCodeIntegration
                executable = VSCodeIntegration._code_executable()
                if not executable:
                    return False, "VS Code's executable was not found."
                kwargs = {"close_fds": True}
                if IS_WINDOWS:
                    kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                subprocess.Popen([executable], **kwargs)
                return True, "Sent an app-launch request to VS Code."

            # Use the OS association first; never invoke a command shell.
            try:
                os.startfile(target)  # type: ignore[attr-defined]
                return True, f"Opening {name}"
            except (AttributeError, OSError):
                executable = shutil.which(target)
                if not executable:
                    return False, f"Could not find an installed app named '{name}'."
                kwargs = {"close_fds": True}
                if IS_WINDOWS:
                    kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                subprocess.Popen([executable], **kwargs)
                return True, f"Opening {name}"
        except Exception as e:
            return False, f"Could not launch '{name}': {str(e)}"
