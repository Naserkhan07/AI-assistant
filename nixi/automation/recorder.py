"""Workflow recorder — captures pyautogui/pyperclip actions and replays them."""
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any
from nixi.config import NixiConfig, get_config
from nixi.logging_utils import get_logger
log = get_logger("recorder")

class MacroRecorder:
    def __init__(self, config: NixiConfig | None = None):
        self.config = config or get_config()
        self.dir = Path(self.config.data_dir) / "macros"
        self.recording: list[dict[str, Any]] = []
        self.is_recording = False
        self._start_ts = 0.0

    def start(self, name: str = "macro") -> None:
        self.recording = []; self.is_recording=True; self._start_ts=time.time(); log.info("Recording macro %s", name)
    def record_action(self, action: dict[str, Any]) -> None:
        if not self.is_recording: return
        action = dict(action); action["t"] = round(time.time()-self._start_ts,3)
        self.recording.append(action)
    def stop(self, name: str | None = None) -> str:
        self.is_recording=False
        if not self.recording: return "No actions recorded."
        fname = f"{name or 'macro'}_{int(time.time())}.json"
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / fname
        path.write_text(json.dumps(self.recording, indent=2), encoding="utf-8")
        log.info("Macro saved %s (%d actions)", path, len(self.recording))
        return f"Saved macro {fname} with {len(self.recording)} actions to {path}"
    def list_macros(self) -> list[str]:
        if not self.dir.exists(): return []
        return sorted(p.name for p in self.dir.glob("*.json"))
    def load(self, name: str) -> list[dict[str, Any]]:
        path = self.dir / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    def replay(self, name: str, dry_run: bool = False) -> str:
        steps = self.load(name)
        if not steps: return f"No macro {name}"
        if dry_run: return f"[dry-run] Would replay {len(steps)} steps from {name}"
        from nixi.compat.optional import load as _load
        from nixi.compat import fakes
        pyautogui = _load("pyautogui", fakes.FakePyAutoGUI())
        pyperclip = _load("pyperclip", fakes.FakePyperclip())
        for step in steps:
            t = step.get("type")
            try:
                if t=="click": pyautogui.click(step.get("x",0), step.get("y",0))
                elif t=="type": pyperclip.copy(step.get("text","")); pyautogui.hotkey("ctrl","v")
                elif t=="press": pyautogui.press(step.get("key","enter"))
                elif t=="hotkey": pyautogui.hotkey(*step.get("keys",[]))
                elif t=="wait": time.sleep(min(5.0, float(step.get("seconds",0.2))))
            except Exception as e: log.warning("Replay step failed %s: %s", step, e)
            delay = step.get("delay", 0.05)
            if delay:  time.sleep(min(1.0, delay))
        return f"Replayed {len(steps)} steps from {name}"
