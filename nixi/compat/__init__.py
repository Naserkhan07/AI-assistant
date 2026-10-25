"""Optional-dependency compatibility layer (keeps Nixi importable everywhere)."""
from .optional import load, NullModule, is_available

__all__ = ["load", "NullModule", "is_available"]
