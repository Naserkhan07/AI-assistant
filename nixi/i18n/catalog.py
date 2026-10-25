from __future__ import annotations
import json
from pathlib import Path

_LOCALES = {
    "en": {
        "app.name": "Nixi",
        "status.idle": "Idle",
        "status.listening": "Listening...",
        "status.thinking": "Thinking...",
        "status.speaking": "Speaking...",
        "voice.hold_to_talk": "Hold {hotkey} to talk",
        "voice.wake_hint": "Say “hey nixi”",
        "settings.title": "Nixi Settings",
        "settings.voice": "Voice & Language",
        "settings.privacy": "Privacy & Safety",
        "settings.theme": "Appearance",
        "settings.language": "Language",
        "vault.title": "Vault",
        "vault.locked": "Vault locked",
        "timeline.title": "Activity Timeline",
        "notifications.title": "Notifications",
        "notif.timer_done": "Timer finished — {label}",
        "notif.briefing": "Daily briefing ready",
        "error.generic": "Something went wrong: {detail}",
        "offline.notice": "You’re offline — local actions still work",
    },
    "hi": {
        "app.name": "निक्सी",
        "status.idle": "तैयार",
        "status.listening": "सुन रही हूँ...",
        "status.thinking": "सोच रही हूँ...",
        "status.speaking": "बोल रही हूँ...",
        "voice.hold_to_talk": "{hotkey} दबाकर बोलें",
        "voice.wake_hint": "“हे निक्सी” कहें",
        "settings.title": "निक्सी सेटिंग्स",
        "settings.voice": "आवाज़ और भाषा",
        "settings.privacy": "गोपनीयता और सुरक्षा",
        "settings.theme": "दिखावट",
        "settings.language": "भाषा",
        "vault.title": "वॉल्ट",
        "vault.locked": "वॉल्ट बंद है",
        "timeline.title": "गतिविधि",
        "notifications.title": "सूचनाएँ",
        "notif.timer_done": "टाइमर पूरा — {label}",
        "notif.briefing": "रोज़ की ब्रीफिंग तैयार है",
        "error.generic": "कुछ गड़बड़ हो गई: {detail}",
        "offline.notice": "आप ऑफ़लाइन हैं — स्थानीय काम जारी हैं",
    },
    "hinglish": {
        "app.name": "Nixi",
        "status.idle": "Ready",
        "status.listening": "Sun rahi hoon...",
        "status.thinking": "Soch rahi hoon...",
        "status.speaking": "Bol rahi hoon...",
        "voice.hold_to_talk": "{hotkey} hold karke bolo",
        "voice.wake_hint": "“hey nixi” bolo",
        "settings.title": "Nixi Settings",
        "settings.voice": "Voice & Bhasha",
        "settings.privacy": "Privacy & Safety",
        "settings.theme": "Appearance",
        "settings.language": "Bhasha",
        "vault.title": "Vault",
        "vault.locked": "Vault locked",
        "timeline.title": "Timeline",
        "notifications.title": "Notifications",
        "notif.timer_done": "Timer done — {label}",
        "notif.briefing": "Briefing ready",
        "error.generic": "Error: {detail}",
        "offline.notice": "Offline ho — local kaam chal rahe hain",
    },
}

class I18N:
    def __init__(self, locale: str = "en"):
        self.locale = locale if locale in _LOCALES else "en"
    def t(self, key: str, **kwargs) -> str:
        table = _LOCALES.get(self.locale, _LOCALES["en"])
        template = table.get(key) or _LOCALES["en"].get(key, key)
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    def set_locale(self, locale: str) -> None:
        if locale in _LOCALES: self.locale = locale
    def available(self) -> list[str]: return list(_LOCALES.keys())
    def all_strings(self) -> dict[str, str]:
        base = dict(_LOCALES["en"])
        base.update(_LOCALES.get(self.locale, {}))
        return base

_active = I18N("en")
def get_text(key: str, **kwargs) -> str: return _active.t(key, **kwargs)
