"""Privacy controls for screen vision and personal data."""
from .vision_guard import VisionGuard, redact_pii, DEFAULT_BLOCKLIST

__all__ = ["VisionGuard", "redact_pii", "DEFAULT_BLOCKLIST"]
