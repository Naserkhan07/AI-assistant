"""
Nixi Autonomous Browser & Screen Execution Agent — Turbo Speed Edition
Observes the active browser or desktop application, locates input fields, buttons,
and form controls using FreeLLMAPI Vision, and executes clicks and typing with minimal latency.
"""
from __future__ import annotations

import time
import json
import base64
import re
from nixi.compat.optional import load
from nixi.compat import fakes

pyautogui = load("pyautogui", fakes.FakePyAutoGUI())
pyperclip = load("pyperclip", fakes.FakePyperclip())
from typing import List, Dict, Any, Optional, Tuple

class BrowserExecutionAgent:
    def __init__(self, llm_client):
        self.llm = llm_client
        pyautogui.FAILSAFE = True  # Preserve PyAutoGUI's top-left emergency stop
        pyautogui.PAUSE = 0.01

    def execute_screen_goal(self, goal: str, screenshot_bytes: bytes) -> str:
        """
        Takes a screenshot of the user's screen/browser, asks Vision LLM to locate
        the target elements, and executes the mouse/keyboard actions at lightning speed.
        """
        screen_w, screen_h = pyautogui.size()
        lower_goal = goal.lower()

        # Fast path for common form-filling commands (e.g. "fill these boxes", "fill form", "fill table")
        if re.search(r"\b(fill|boxes|boxex|populate|form|table)\b", lower_goal) and not re.search(r"\b(where|what|how)\b", lower_goal):
            # Attempt rapid vision with short 3.5s timeout, otherwise immediate heuristic
            try:
                actions, summary = self._detect_actions_vision(goal, screenshot_bytes, screen_w, screen_h, timeout=3.5)
                if actions:
                    executed, errors = self._run_actions(actions)
                    if executed:
                        suffix = " Verify the visible result; I cannot confirm the page accepted every field."
                        return f"Attempted {executed} on-screen action(s). {summary}{suffix}"
                    return f"No on-screen actions succeeded: {errors}"
            except Exception as exc:
                return f"Form action failed; no blind fallback was used: {exc}"
            return "I couldn't identify safe, actionable fields; no clicks or typing were performed."

        # General vision action path (clicking buttons, links, etc.)
        try:
            actions, summary = self._detect_actions_vision(goal, screenshot_bytes, screen_w, screen_h, timeout=5.0)
            if actions:
                executed, errors = self._run_actions(actions)
                if executed:
                    return f"Attempted {executed} on-screen action(s). {summary} Verify the visible result."
                return f"No on-screen actions succeeded: {errors}"
            return "I couldn't identify a safe target; no screen actions were performed."
        except Exception as exc:
            return f"Screen action failed; no blind fallback was used: {exc}"

    def _detect_actions_vision(self, goal: str, screenshot_bytes: bytes, screen_w: int, screen_h: int, timeout: float = 4.0) -> Tuple[List[Dict[str, Any]], str]:
        """Ask Vision LLM for coordinate actions with compact prompt and aggressive timeout."""
        b64_img = base64.b64encode(screenshot_bytes).decode("utf-8")

        prompt = f"""Fast UI agent. Screen: {screen_w}x{screen_h}. Goal: "{goal}".
Return JSON ONLY:
{{
  "actions": [
    {{"type": "click", "x": 300, "y": 420}},
    {{"type": "type", "text": "custom_id"}},
    {{"type": "press", "key": "tab"}},
    {{"type": "type", "text": "Field Name"}},
    {{"type": "press", "key": "tab"}}
  ],
  "summary": "Filled fields."
}}"""

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
                    }
                ]
            }
        ]

        url = f"{self.llm.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.llm.api_key}",
        }
        payload = {
            "model": self.llm.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 180,
        }
        resp = self.llm.client.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code == 200:
            content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return data.get("actions", []), data.get("summary", "Executed browser actions.")
        return [], ""

    def _run_actions(self, actions: List[Dict[str, Any]]) -> tuple[int, list[str]]:
        """Execute validated screen actions and report attempted successes/errors."""
        screen_w, screen_h = pyautogui.size()
        executed = 0
        errors: list[str] = []
        allowed_keys = {"tab", "enter", "esc", "escape", "space", "backspace", "delete", "up", "down", "left", "right"}
        allowed_hotkeys = {("ctrl", "a"), ("ctrl", "c"), ("ctrl", "v"), ("ctrl", "z"), ("shift", "tab")}
        for act in actions[:20]:
            act_type = str(act.get("type", "")).lower()
            try:
                if act_type == "click":
                    x = max(0, min(screen_w - 5, int(act.get("x", 0))))
                    y = max(0, min(screen_h - 5, int(act.get("y", 0))))
                    pyautogui.click(x, y)
                elif act_type == "type":
                    text = str(act.get("text", ""))[:2000]
                    if not text:
                        errors.append("empty type action")
                        continue
                    pyperclip.copy(text)
                    pyautogui.hotkey("ctrl", "v")
                elif act_type == "press":
                    key = str(act.get("key", "")).lower()
                    if key not in allowed_keys:
                        errors.append(f"blocked key: {key[:20]}")
                        continue
                    pyautogui.press(key)
                elif act_type == "hotkey":
                    keys = tuple(str(k).lower() for k in act.get("keys", []))
                    if keys not in allowed_hotkeys:
                        errors.append("blocked hotkey")
                        continue
                    pyautogui.hotkey(*keys)
                elif act_type == "wait":
                    time.sleep(max(0.0, min(3.0, float(act.get("seconds", 0.05)))))
                else:
                    errors.append(f"unsupported action: {act_type[:20]}")
                    continue
                executed += 1
                time.sleep(0.01)
            except Exception as exc:
                errors.append(f"{act_type or 'action'} failed: {exc}")
        return executed, errors

    def _fallback_fill(self, goal: str) -> str:
        """Do not guess coordinates or type made-up data when screen analysis fails."""
        return "I could not identify the requested controls. No screen clicks or typing were performed."
