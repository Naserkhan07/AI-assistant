"""Screen-vision privacy: consent, app blocklists, regions and PII redaction."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from nixi.config import NixiConfig, get_config
from nixi.platform.system import active_process_name, active_window_title
from nixi.logging_utils import get_logger

log = get_logger("privacy")

DEFAULT_BLOCKLIST: tuple[str, ...] = (
    "bank", "netbanking", "paypal", "upi", "otp", "password", "1password",
    "bitwarden", "keepass", "wallet", "sign in", "login", "checkout", "aadhaar",
    "passport", "credit card", "payment",
)

_PII_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL]"),
    (re.compile(r"(?<!\w)(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\w)"), "[PHONE]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[CARD]"),
    (re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b"), "[ID]"),
    (re.compile(r"\b(?:sk|pk|ghp|gho|xox[baprs])[-_][A-Za-z0-9_-]{12,}\b"), "[API_KEY]"),
    (re.compile(r"\b(?:password|passwd|pwd|secret|token)\s*[:=]\s*\S+", re.IGNORECASE), "password=[REDACTED]"),
)


def redact_pii(text: str) -> str:
    """Remove obvious PII/secrets before any text is logged or sent to a model."""
    result = str(text or "")
    for pattern, replacement in _PII_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


@dataclass(frozen=True)
class VisionCheck:
    allowed: bool
    reason: str
    region: tuple[int, int, int, int] | None = None

    def __bool__(self) -> bool:
        return self.allowed


class VisionGuard:
    """Gate every screenshot behind an explicit, user-controlled policy."""

    def __init__(self, config: NixiConfig | None = None,
                 indicator: Callable[[bool, str], None] | None = None):
        self.config = config or get_config()
        self.indicator = indicator
        self._consent = bool(self.config.vision_consent_granted or not self.config.vision_require_consent)
        self._blocklist = tuple(s.lower() for s in (self.config.vision_blocklist or DEFAULT_BLOCKLIST))
        self._allowlist = tuple(s.lower() for s in self.config.vision_allowlist)

    @property
    def consent_granted(self) -> bool:
        return self._consent

    def grant_consent(self, granted: bool = True) -> None:
        self._consent = bool(granted)
        log.info("Screen vision consent: %s", self._consent)

    def set_enabled(self, enabled: bool) -> None:
        self.config.vision_enabled = bool(enabled)

    def check(self, window_title: str | None = None, app_name: str | None = None,
              explicit: bool = False) -> VisionCheck:
        """Return whether a capture is permitted right now."""
        if not self.config.vision_enabled and not explicit:
            return VisionCheck(False, "Screen vision is disabled (enable it in Settings).")
        if self.config.vision_require_consent and not self._consent:
            return VisionCheck(False, "Consent for screen vision has not been granted.")
        title = (window_title if window_title is not None else active_window_title()) or ""
        app = (app_name if app_name is not None else active_process_name()) or ""
        haystack = f"{title} {app}".lower()
        if self._allowlist and any(a in haystack for a in self._allowlist):
            pass
        elif any(b in haystack for b in self._blocklist if b):
            return VisionCheck(False, f"Blocked app/window for privacy: {title or app or 'unknown'}")
        region = self.parse_region(self.config.screenshot_region)
        self._notify(True, title)
        return VisionCheck(True, "allowed", region)

    def finish(self) -> None:
        self._notify(False, "")

    def prepare_prompt(self, prompt: str) -> str:
        if self.config.vision_redact_pii:
            return redact_pii(prompt)
        return str(prompt or "")

    def prepare_output(self, text: str) -> str:
        """Redact any PII the vision model echoed back before showing/logging it."""
        return redact_pii(text) if self.config.vision_redact_pii else str(text or "")

    @staticmethod
    def parse_region(value: str) -> tuple[int, int, int, int] | None:
        """Parse 'x,y,w,h' into a positive rectangle, or None for full screen."""
        if not value or not value.strip():
            return None
        try:
            parts = [int(p.strip()) for p in value.split(",")]
            if len(parts) != 4 or parts[2] <= 0 or parts[3] <= 0:
                return None
            return (max(0, parts[0]), max(0, parts[1]), parts[2], parts[3])
        except (ValueError, TypeError):
            return None

    def _notify(self, active: bool, title: str) -> None:
        if self.indicator:
            try:
                self.indicator(active, title)
            except Exception:
                pass

    def summary(self) -> dict[str, Any]:
        return {
            "enabled": self.config.vision_enabled,
            "consent": self._consent,
            "require_consent": self.config.vision_require_consent,
            "blocklist": list(self._blocklist),
            "redact_pii": self.config.vision_redact_pii,
            "region": self.config.screenshot_region,
        }
