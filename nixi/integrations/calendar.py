"""Local ICS calendar reader — stdlib only."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from nixi.config import NixiConfig, get_config


def _parse_ics_datetime(value: str) -> datetime | None:
    value = value.strip()
    # strip trailing Z and timezone suffixes simply
    value = value.split(";")[0] if ";" in value else value
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


class CalendarReader:
    def __init__(self, config: NixiConfig | None = None):
        self.config = config or get_config()

    def _load_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for p in self.config.calendar_ics_paths:
            path = Path(p).expanduser()
            if not path.exists():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # very small ICS parser
            for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.DOTALL):
                summary = re.search(r"SUMMARY:(.+)", block)
                dtstart = re.search(r"DTSTART[^:]*:(.+)", block)
                dtend = re.search(r"DTEND[^:]*:(.+)", block)
                location = re.search(r"LOCATION:(.+)", block)
                if not summary or not dtstart:
                    continue
                start = _parse_ics_datetime(dtstart.group(1).strip())
                end = _parse_ics_datetime(dtend.group(1).strip()) if dtend else None
                events.append({
                    "summary": summary.group(1).strip(),
                    "start": start,
                    "end": end,
                    "location": location.group(1).strip() if location else "",
                    "source": str(path),
                })
        return events

    def upcoming(self, days: int = 7, limit: int = 10) -> list[dict[str, Any]]:
        now = datetime.now()
        horizon = now + timedelta(days=days)
        events = [e for e in self._load_events() if e["start"] and now <= e["start"] <= horizon]
        events.sort(key=lambda e: e["start"])
        return events[:limit]

    def today(self) -> list[dict[str, Any]]:
        return self.upcoming(days=1, limit=20)

    def format_briefing(self) -> str:
        events = self.upcoming(days=2, limit=8)
        if not events:
            return "No upcoming calendar events found."
        lines = ["📅 Upcoming events:"]
        for e in events:
            when = e["start"].strftime("%a %b %d, %H:%M") if e["start"] else "?"
            loc = f" @ {e['location']}" if e["location"] else ""
            lines.append(f"• {when} — {e['summary']}{loc}")
        return "\n".join(lines)
