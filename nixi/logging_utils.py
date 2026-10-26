"""Structured logging, latency measurement and first-run diagnostics."""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from nixi.config import NixiConfig, get_config
from nixi.platform.capabilities import capability_report, has_module

_CONFIGURED = False


def setup_logging(config: NixiConfig | None = None, force: bool = False) -> logging.Logger:
    global _CONFIGURED
    cfg = config or get_config()
    root = logging.getLogger("nixi")
    if _CONFIGURED and not force:
        return root
    level = getattr(logging, str(cfg.log_level).upper(), logging.INFO)
    root.setLevel(level)
    root.handlers.clear()
    root.propagate = False
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)-22s | %(message)s", "%H:%M:%S")
    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(fmt)
    root.addHandler(stream)
    if cfg.log_file:
        try:
            path = Path(cfg.log_file).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.handlers.RotatingFileHandler(
                path, maxBytes=1024 * 1024, backupCount=3, encoding="utf-8")
            handler.setFormatter(fmt)
            root.addHandler(handler)
        except OSError:
            root.warning("Could not open log file %s", cfg.log_file)
    _CONFIGURED = True
    return root


def get_logger(name: str) -> logging.Logger:
    """Return a child of the configured 'nixi' logger."""
    if not _CONFIGURED:
        setup_logging()
    return logging.getLogger("nixi").getChild(name)


@contextmanager
def log_timing(logger: logging.Logger, label: str) -> Iterator[dict[str, float]]:
    stats: dict[str, float] = {}
    start = time.perf_counter()
    try:
        yield stats
    finally:
        stats["elapsed_ms"] = round((time.perf_counter() - start) * 1000, 2)
        logger.debug("%s took %.2f ms", label, stats["elapsed_ms"])


class Diagnostics:
    """Health checks surfaced in the settings dialog, CLI and /health endpoint."""

    def __init__(self, config: NixiConfig | None = None, llm: Any = None):
        self.config = config or get_config()
        self.llm = llm

    def run(self) -> dict[str, Any]:
        checks: list[dict[str, str]] = []

        def add(name: str, ok: bool | None, detail: str) -> None:
            checks.append({"name": name, "status": "ok" if ok else ("warn" if ok is None else "fail"), "detail": detail})

        caps = capability_report()
        add("platform", True, f"python {sys.version.split()[0]} / {sys.platform}")
        add("config", not self.config.validate(), "; ".join(self.config.validate()) or "valid")
        add("data dir", self._data_writable(), str(Path(self.config.data_dir).resolve()))
        # Optional subsystems are warnings, never hard failures.
        optional = None
        add("PyQt6 UI", True if caps["qt"] else optional, "available" if caps["qt"] else "headless mode only")
        add("screen capture", True if caps["pillow"] else optional, "Pillow available" if caps["pillow"] else "no Pillow")
        add("microphone STT dependencies", True if (caps["sounddevice"] and caps["faster_whisper"]) else optional,
            "sounddevice + faster-whisper installed" if caps["sounddevice"] and caps["faster_whisper"] else "install audio extras with the Windows setup script")
        mic_ok, mic_detail = self._microphone_status(caps["sounddevice"])
        add("microphone device", mic_ok, mic_detail)
        model = str(getattr(self.config, "whisper_model", "") or "").strip()
        add("Whisper model setting", bool(model), model or "no transcription model selected")
        add("neural TTS", True if caps["edge_tts"] else optional,
            "edge-tts available" if caps["edge_tts"] else "silent/local fallback")
        add("system metrics", True if caps["psutil"] else optional,
            "psutil available" if caps["psutil"] else "using safe fallback")
        add("browser DOM", True if caps["playwright"] else optional,
            "Playwright package installed; Chromium browser must also be installed" if caps["playwright"] else "default-browser launch available; install Playwright + Chromium for DOM actions")
        office_ready = has_module("docx") and has_module("openpyxl")
        add("Office document skills", True if office_ready else optional,
            "Word and Excel libraries available" if office_ready else "install python-docx and openpyxl")
        add("RAG index", True if caps["sqlite_fts5"] else optional,
            "FTS5" if caps["sqlite_fts5"] else "LIKE fallback")
        llm_ok: bool | None = optional
        detail = "not checked (no client supplied)"
        if self.llm is not None:
            try:
                llm_ok = bool(self.llm.is_online())
                detail = "reachable" if llm_ok else "unreachable"
            except Exception as exc:
                llm_ok, detail = False, f"error: {exc}"
        add("LLM provider", llm_ok, f"{self.config.provider}: {detail}")
        add("local-only mode", None if self.config.local_only else True,
            "on (no network)" if self.config.local_only else "off")
        add("vision privacy", None if self.config.vision_enabled else True,
            "screenshots ON" if self.config.vision_enabled else "screenshots OFF (opt-in)")
        add("destructive confirmation", None if not self.config.require_confirmation else True,
            "required" if self.config.require_confirmation else "disabled")
        return {
            "ok": all(c["status"] != "fail" for c in checks),
            "checks": checks,
            "capabilities": caps,
            "warnings": self.config.validate(),
        }

    @staticmethod
    def _microphone_status(sounddevice_available: bool) -> tuple[bool | None, str]:
        if not sounddevice_available:
            return None, "audio input package is not installed"
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            inputs = [d for d in devices if int(d.get("max_input_channels", 0)) > 0]
            if inputs:
                return True, f"{len(inputs)} input device(s) detected; recording permission is checked when capture starts"
            return None, "no microphone input device found; check Windows microphone privacy and sound settings"
        except Exception as exc:
            return None, f"could not enumerate microphone devices: {exc}"

    def _data_writable(self) -> bool:
        try:
            p = Path(self.config.data_dir)
            p.mkdir(parents=True, exist_ok=True)
            test = p / ".write_test"
            test.write_text("ok", encoding="utf-8")
            test.unlink()
            return True
        except OSError:
            return False

    def format_text(self) -> str:
        result = self.run()
        lines = ["Nixi diagnostics", "=" * 40]
        for c in result["checks"]:
            mark = {"ok": "[OK]", "warn": "[!!]", "fail": "[XX]"}[c["status"]]
            lines.append(f"{mark:5} {c['name']:<26} {c['detail']}")
        for w in result["warnings"]:
            lines.append(f"  ! {w}")
        return "\n".join(lines)
