"""Cross-platform replacements for the Windows-only calls scattered in v1."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .capabilities import IS_WINDOWS, has_module
from nixi.compat.optional import load
from nixi.compat import fakes

psutil = load("psutil", fakes.FakePsutil())


def beep(frequency: int = 1000, duration: int = 250) -> bool:
    """Play a short alert tone; returns False when audio is unavailable."""
    if IS_WINDOWS:
        try:
            import winsound
            winsound.Beep(max(37, int(frequency)), max(1, int(duration)))
            return True
        except Exception:
            return False
    # POSIX: `beep` needs privileges, so prefer a terminal bell (harmless).
    try:
        sys.stdout.write("\a")
        sys.stdout.flush()
        return True
    except Exception:
        return False


def open_path(path: str | Path) -> bool:
    """Open a file/URL with the OS default handler, without shell=True."""
    target = str(path)
    try:
        if IS_WINDOWS:
            os.startfile(target)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def disk_root() -> str:
    if IS_WINDOWS:
        return os.environ.get("SystemDrive", "C:") + "\\"
    return "/"


def run_shell(command: str, timeout: int = 15) -> str:
    """Run a shell command with a hard timeout. Windows uses PowerShell."""
    if not command or not command.strip():
        return "Error: empty command."
    try:
        if IS_WINDOWS:
            # PowerShell is a hidden, captured child process: never create a console window.
            # This uses the Windows PowerShell runtime already supplied with Windows.
            executable = os.path.join(
                os.environ.get("SystemRoot", r"C:\Windows"),
                "System32", "WindowsPowerShell", "v1.0", "powershell.exe",
            )
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            proc = subprocess.run(
                [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True, text=True, timeout=timeout, check=False,
                creationflags=flags, startupinfo=startupinfo,
            )
        else:
            proc = subprocess.run(
                ["/bin/sh", "-c", command],
                capture_output=True, text=True, timeout=timeout, check=False,
            )
        out, err = (proc.stdout or "").strip(), (proc.stderr or "").strip()
        if err and not out:
            return f"Error: {err}"
        return out or "Command executed successfully with no output."
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds."
    except Exception as exc:
        return f"Execution error: {exc}"


def active_window_title() -> str:
    """Best-effort foreground window title (used by the vision blocklist)."""
    if IS_WINDOWS:
        try:
            import ctypes
            length = ctypes.windll.user32.GetWindowTextLengthW(ctypes.windll.user32.GetForegroundWindow())
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(ctypes.windll.user32.GetForegroundWindow(), buf, length + 1)
            return buf.value
        except Exception:
            return ""
    return os.environ.get("NIXI_ACTIVE_WINDOW", "")


def active_process_name() -> str:
    if has_module("psutil") and IS_WINDOWS:
        try:
            import ctypes
            from ctypes import wintypes
            pid = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(
                ctypes.windll.user32.GetForegroundWindow(), ctypes.byref(pid))
            return psutil.Process(pid.value).name()
        except Exception:
            return ""
    return ""


def trim_working_sets() -> int:
    """Windows-only RAM trim; safely returns 0 elsewhere."""
    if not IS_WINDOWS:
        return 0
    trimmed = 0
    try:
        import ctypes
        for proc in psutil.process_iter(["pid"]):
            try:
                handle = ctypes.windll.kernel32.OpenProcess(0x001F0FFF, False, proc.info["pid"])
                if handle:
                    ctypes.windll.psapi.EmptyWorkingSet(handle)
                    ctypes.windll.kernel32.CloseHandle(handle)
                    trimmed += 1
            except Exception:
                continue
    except Exception:
        pass
    return trimmed


def system_stats() -> dict[str, Any]:
    """CPU / RAM / disk / battery diagnostics with a safe fake on non-Windows."""
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage(disk_root())
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
    except Exception:
        return {"cpu_percent": 0.0, "ram_used_gb": 0.0, "ram_total_gb": 0.0,
                "ram_percent": 0.0, "disk_free_gb": 0.0,
                "battery_percent": None, "power_plugged": None}
