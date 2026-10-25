"""Text helpers shared by the agent, UI and API."""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

_FENCE = re.compile(r"^```(?:json|python|text)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def truncate(text: str, limit: int = 200, suffix: str = "...") -> str:
    text = str(text or "")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - len(suffix))].rstrip() + suffix


def word_count(text: str) -> int:
    return len(str(text or "").split())


def slugify(text: str, max_len: int = 60) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = value.encode("ascii", "ignore").decode("ascii").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return (value or "item")[:max_len]


def safe_filename(text: str, max_len: int = 80) -> str:
    value = re.sub(r"[^\w.\- ]+", "_", str(text or "")).strip()
    return (value or "file")[:max_len]


def extract_json(text: str) -> dict[str, Any] | None:
    """Find the first JSON object in an LLM reply (fenced or free-form)."""
    if not text:
        return None
    cleaned = _FENCE.sub("", text.strip()).strip()
    candidates = [cleaned]
    # Prefer a balanced top-level object if the model added commentary.
    start = cleaned.find("{")
    if start != -1:
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(cleaned)):
            ch = cleaned[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidates.insert(0, cleaned[start:i + 1])
                    break
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, TypeError):
            continue
    return None
