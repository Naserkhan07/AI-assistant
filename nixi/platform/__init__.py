"""OS abstraction: one API, graceful degradation everywhere."""
from .capabilities import IS_WINDOWS, IS_MACOS, IS_LINUX, HAS_GUI, capability_report, has_module
from .system import (
    beep, open_path, run_shell, disk_root, active_window_title,
    trim_working_sets, system_stats,
)

__all__ = [
    "IS_WINDOWS", "IS_MACOS", "IS_LINUX", "HAS_GUI", "capability_report", "has_module",
    "beep", "open_path", "run_shell", "disk_root", "active_window_title",
    "trim_working_sets", "system_stats",
]
