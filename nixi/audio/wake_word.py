"""
Nixi Wake Word & Trigger Detector
Recognizes phrases like 'Hey Nixi', 'Nixi', 'Hey Jarvis' or custom triggers.
"""
from __future__ import annotations

import re
from typing import Tuple

DEFAULT_TRIGGERS = ["hey nixi", "nixi", "hey nixie", "nixie", "hey jarvis", "jarvis"]

class VoiceGate:
    """Gating for voice input: open / wake / push_to_talk / muted."""
    def __init__(self, mode: str = "open", hotkey: str = "ctrl+alt+space"):
        self.mode=mode; self.hotkey=hotkey; self._held=False
    def is_allowed(self, has_wake: bool, ptt_held: bool) -> bool:
        if self.mode=="muted": return False
        if self.mode=="open": return True
        if self.mode=="push_to_talk": return bool(ptt_held)
        if self.mode=="wake": return bool(has_wake)
        return True

class WakeWordDetector:
    def __init__(self, triggers: list[str] = DEFAULT_TRIGGERS):
        self.triggers = [t.lower() for t in triggers]

    def check(self, text: str) -> Tuple[bool, str]:
        """
        Check if speech contains a wake phrase.
        Returns: (is_wake_word_triggered, cleaned_command)
        """
        cleaned = text.strip()
        lower = cleaned.lower()

        # Remove leading punctuation
        lower = re.sub(r"^[,\.\?!;:\s]+", "", lower)

        for trigger in self.triggers:
            if lower.startswith(trigger):
                # Cut the trigger prefix
                remainder = cleaned[len(trigger):].strip()
                # Remove leading commas or punctuation after wake word
                remainder = re.sub(r"^[,\.\?!;:\s]+", "", remainder).strip()
                return True, remainder
            elif f" {trigger} " in f" {lower} ":
                # Trigger in middle of sentence
                idx = lower.find(trigger)
                remainder = cleaned[idx + len(trigger):].strip()
                remainder = re.sub(r"^[,\.\?!;:\s]+", "", remainder).strip()
                return True, remainder

        return False, cleaned
