"""Controlled VS Code integration: open projects/files without a shell."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from nixi.core.file_actions import FileActionService
from nixi.platform.capabilities import IS_WINDOWS


class VSCodeIntegration:
    def __init__(self, file_actions: FileActionService):
        self.files = file_actions

    @staticmethod
    def _code_executable() -> str | None:
        candidate = shutil.which("code")
        if candidate and (not IS_WINDOWS or candidate.lower().endswith(".exe")):
            return candidate
        if IS_WINDOWS:
            candidates = [
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Microsoft VS Code/Code.exe",
                Path(os.environ.get("ProgramFiles", "")) / "Microsoft VS Code/Code.exe",
                Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft VS Code/Code.exe",
            ]
            for path in candidates:
                if path.is_file():
                    return str(path)
        return None

    def open_project(self, path: str) -> str:
        try:
            target = self.files._resolve(path)
            if not target.is_dir():
                return f"Project folder not found: {target}"
            code = self._code_executable()
            if not code:
                return "VS Code's Code.exe was not found. Install VS Code or open the folder with Explorer."
            kwargs = {"close_fds": True}
            if IS_WINDOWS:
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            process = subprocess.Popen([code, str(target)], **kwargs)
            if process.poll() is not None:
                return f"VS Code exited immediately with code {process.returncode}."
            return f"Sent project-open request to VS Code: {target}"
        except Exception as exc:
            return f"Could not open VS Code project: {exc}"

    def open_file(self, path: str) -> str:
        try:
            target = self.files._resolve(path)
            if not target.is_file():
                return f"File not found: {target}"
            code = self._code_executable()
            if not code:
                return "VS Code's Code.exe was not found."
            kwargs = {"close_fds": True}
            if IS_WINDOWS:
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            process = subprocess.Popen([code, str(target)], **kwargs)
            if process.poll() is not None:
                return f"VS Code exited immediately with code {process.returncode}."
            return f"Sent file-open request to VS Code: {target}"
        except Exception as exc:
            return f"Could not open file in VS Code: {exc}"
