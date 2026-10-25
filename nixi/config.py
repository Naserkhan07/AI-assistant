"""Single source of truth for every Nixi setting.

Pure standard library so it works in the GUI, the headless CLI and CI.
All previous dead keys from ``.env.example`` are now genuinely consumed.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_ENV_FILE = ROOT / ".env"

TRUE_VALUES = {"1", "true", "yes", "on", "y"}
SECRET_KEYS = frozenset({"api_key", "exa_api_key", "api_token"})


def as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in TRUE_VALUES


def as_int(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def as_csv(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        items: Iterable[Any] = value
    else:
        items = str(value).split(",")
    return tuple(str(i).strip() for i in items if str(i).strip())


_ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")


def read_env_file(path: str | Path | None = None) -> dict[str, str]:
    """Parse a .env file without depending on python-dotenv."""
    p = Path(path) if path else DEFAULT_ENV_FILE
    result: dict[str, str] = {}
    if not p.exists():
        return result
    try:
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            match = _ENV_LINE.match(line)
            if not match:
                continue
            key, value = match.group(1), match.group(2).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            else:
                value = value.split(" #", 1)[0].strip()
            result[key] = value
    except OSError:
        pass
    return result


def merged_env(env: Mapping[str, str] | None = None, env_file: str | Path | None = None) -> dict[str, str]:
    """Overlay: defaults < .env < real process env < explicit ``env`` mapping."""
    merged = read_env_file(env_file)
    merged.update({k: v for k, v in os.environ.items() if k.startswith(("NIXI_", "FREELLMAPI_", "EXA_", "TTS_", "STT_", "WAKE_", "ASSISTANT_", "USER_", "REQUIRE_", "LOG_", "API_", "HOTKEY_", "VISION_"))})
    if env:
        merged.update({str(k): str(v) for k, v in env.items()})
    return merged


def save_env(updates: Mapping[str, Any], path: str | Path | None = None) -> Path:
    """Write settings back to .env while preserving comments and unknown keys."""
    p = Path(path) if path else DEFAULT_ENV_FILE
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    remaining = {str(k): str(v) for k, v in updates.items()}
    out: list[str] = []
    for line in lines:
        match = _ENV_LINE.match(line)
        if match and match.group(1) in remaining:
            key = match.group(1)
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)
    for key, value in remaining.items():
        out.append(f"{key}={value}")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    return p


@dataclass(frozen=True)
class ProviderSpec:
    """One OpenAI-compatible (or offline) LLM endpoint."""
    name: str
    kind: str = "openai"            # "openai" | "offline"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    vision_model: str = ""
    timeout: float = 20.0

    @property
    def is_offline(self) -> bool:
        return self.kind == "offline"


@dataclass
class NixiConfig:
    # ── Identity ────────────────────────────────────────────────────────────
    assistant_name: str = "Nixi"
    user_name: str = "Sir"
    system_prompt: str = ""

    # ── LLM / providers ─────────────────────────────────────────────────────
    provider: str = "freellmapi"
    base_url: str = "http://127.0.0.1:3001/v1"
    api_key: str = ""
    model: str = "auto:fast"
    vision_model: str = "auto"
    fallback_models: tuple[str, ...] = ("mistral-nemo", "free-router", "kilo-auto", "auto")
    vision_models: tuple[str, ...] = ("auto", "claude-haiku-4-5", "claude-sonnet-4-5", "free-router")
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    ollama_model: str = "llama3.2"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-latest"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    temperature: float = 0.25
    max_tokens: int = 1200
    vision_max_tokens: int = 800
    request_timeout: float = 20.0
    local_only: bool = False
    exa_api_key: str = ""

    # ── Voice ───────────────────────────────────────────────────────────────
    tts_engine: str = "edge-tts"    # edge-tts | pyttsx3 | sapi | piper | silent
    tts_voice: str = "en-US-AvaNeural"
    tts_rate: str = "+10%"
    tts_pitch: str = "+0Hz"
    tts_language: str = "en"
    stt_engine: str = "auto"        # auto | faster-whisper | google | silent
    whisper_model: str = "tiny.en"
    stt_language: str = ""          # empty = auto-detect (supports hi, en, ...)
    sample_rate: int = 16000
    silence_duration_sec: float = 0.7
    energy_threshold: float = 0.005
    push_to_talk: bool = False
    push_to_talk_hotkey: str = "ctrl+alt+space"
    wake_word_enabled: bool = False
    wake_word_phrases: tuple[str, ...] = ("hey nixi", "nixi")
    speaker_verification: bool = False
    voice_gate_mode: str = "open"   # open | wake | push_to_talk | muted

    # ── Hotkeys ─────────────────────────────────────────────────────────────
    hotkey_dictation: str = "F8"
    hotkey_expand: str = "F9"
    hotkey_vision: str = "F10"
    hotkey_palette: str = "ctrl+k"

    # ── Privacy / vision ────────────────────────────────────────────────────
    vision_enabled: bool = False     # OPT-IN: no screenshot leaves the machine by default
    vision_require_consent: bool = True
    vision_consent_granted: bool = False
    vision_blocklist: tuple[str, ...] = (
        "bank", "netbanking", "paypal", "upi", "otp", "password", "1password",
        "bitwarden", "keepass", "wallet", "sign in", "login", "checkout", "aadhaar",
    )
    vision_redact_pii: bool = True
    vision_keep_screenshots: bool = False
    vision_allowlist: tuple[str, ...] = ()
    screenshot_region: str = ""      # "x,y,w,h" – empty means full screen

    # ── Security / permissions ──────────────────────────────────────────────
    require_confirmation: bool = True
    allowed_tools: tuple[str, ...] = ()
    denied_tools: tuple[str, ...] = ("wipe_disk", "format_drive")
    dry_run: bool = False
    shell_enabled: bool = True
    shell_timeout: int = 15
    code_timeout: int = 20
    sandbox_code: bool = True
    code_network: bool = False
    audit_enabled: bool = True

    # ── UI ──────────────────────────────────────────────────────────────────
    theme: str = "dark"              # dark | light | high-contrast
    font_scale: float = 1.0
    opacity: float = 0.96
    screen_index: int = -1           # -1 = follow cursor
    island_y: int = 10
    start_minimized: bool = False
    launch_at_startup: bool = False
    notifications_enabled: bool = True
    notification_history: int = 50

    # ── Daemons / briefing ──────────────────────────────────────────────────
    battery_enabled: bool = True
    clipboard_enabled: bool = True
    briefing_enabled: bool = True
    briefing_hour: int = 9
    briefing_minute: int = 0
    briefing_latitude: float = 28.6139
    briefing_longitude: float = 77.2090
    briefing_news_feeds: tuple[str, ...] = ()
    calendar_ics_paths: tuple[str, ...] = ()

    # ── Storage / plugins / server ──────────────────────────────────────────
    data_dir: str = str(DEFAULT_DATA_DIR)
    knowledge_dirs: tuple[str, ...] = ()
    knowledge_extensions: tuple[str, ...] = (".md", ".txt", ".py", ".json", ".csv", ".rst")
    timers_persist: bool = True
    plugins_enabled: bool = True
    plugins_dir: str = ""
    api_enabled: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    api_token: str = ""
    log_level: str = "INFO"
    log_file: str = ""
    crash_reports: bool = False
    auto_update: bool = False

    # ────────────────────────────────────────────────────────────────────────
    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, env_file: str | Path | None = None) -> "NixiConfig":
        e = merged_env(env, env_file)
        g = lambda key, default=None: e.get(key, default)  # noqa: E731
        data_dir = g("NIXI_DATA_DIR", str(DEFAULT_DATA_DIR))
        cfg = cls(
            assistant_name=g("ASSISTANT_NAME", "Nixi"),
            user_name=g("USER_NAME", "Sir"),
            system_prompt=g("NIXI_SYSTEM_PROMPT", ""),
            provider=str(g("NIXI_PROVIDER", g("LLM_PROVIDER", "freellmapi"))).lower(),
            base_url=g("FREELLMAPI_URL", "http://127.0.0.1:3001/v1").rstrip("/"),
            api_key=g("FREELLMAPI_KEY", ""),
            model=g("FREELLMAPI_MODEL", "auto:fast"),
            vision_model=g("NIXI_VISION_MODEL", "auto"),
            fallback_models=as_csv(g("NIXI_FALLBACK_MODELS", "mistral-nemo,free-router,kilo-auto,auto")),
            vision_models=as_csv(g("NIXI_VISION_MODELS", "auto,claude-haiku-4-5,claude-sonnet-4-5,free-router")),
            openai_base_url=g("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            openai_api_key=g("OPENAI_API_KEY", ""),
            openai_model=g("OPENAI_MODEL", "gpt-4o-mini"),
            ollama_base_url=g("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"),
            ollama_model=g("OLLAMA_MODEL", "llama3.2"),
            anthropic_api_key=g("ANTHROPIC_API_KEY", ""),
            anthropic_model=g("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
            gemini_api_key=g("GEMINI_API_KEY", ""),
            gemini_model=g("GEMINI_MODEL", "gemini-2.0-flash"),
            temperature=as_float(g("NIXI_TEMPERATURE", 0.25), 0.25),
            max_tokens=as_int(g("NIXI_MAX_TOKENS", 1200), 1200),
            vision_max_tokens=as_int(g("NIXI_VISION_MAX_TOKENS", 800), 800),
            request_timeout=as_float(g("NIXI_REQUEST_TIMEOUT", 20.0), 20.0),
            local_only=as_bool(g("NIXI_LOCAL_ONLY", False)),
            exa_api_key=g("EXA_API_KEY", ""),
            tts_engine=g("TTS_ENGINE", "edge-tts"),
            tts_voice=g("TTS_VOICE", "en-US-AvaNeural"),
            tts_rate=g("TTS_RATE", "+10%"),
            tts_pitch=g("TTS_PITCH", "+0Hz"),
            tts_language=g("TTS_LANGUAGE", "en"),
            stt_engine=g("STT_ENGINE", "auto"),
            whisper_model=g("WHISPER_MODEL", "tiny.en"),
            stt_language=g("STT_LANGUAGE", ""),
            sample_rate=as_int(g("NIXI_SAMPLE_RATE", 16000), 16000),
            silence_duration_sec=as_float(g("NIXI_SILENCE_SEC", 0.7), 0.7),
            energy_threshold=as_float(g("NIXI_ENERGY_THRESHOLD", 0.005), 0.005),
            push_to_talk=as_bool(g("NIXI_PUSH_TO_TALK", False)),
            push_to_talk_hotkey=g("NIXI_PTT_HOTKEY", "ctrl+alt+space"),
            wake_word_enabled=as_bool(g("WAKE_WORD_ENABLED", False)),
            wake_word_phrases=as_csv(g("WAKE_WORD_PHRASES", "hey nixi,nixi")) or ("hey nixi", "nixi"),
            speaker_verification=as_bool(g("NIXI_SPEAKER_VERIFICATION", False)),
            voice_gate_mode=g("NIXI_VOICE_GATE", "open"),
            hotkey_dictation=g("HOTKEY_DICTATION", "F8"),
            hotkey_expand=g("HOTKEY_EXPAND", "F9"),
            hotkey_vision=g("HOTKEY_VISION", "F10"),
            hotkey_palette=g("HOTKEY_PALETTE", "ctrl+k"),
            vision_enabled=as_bool(g("VISION_ENABLED", False)),
            vision_require_consent=as_bool(g("VISION_REQUIRE_CONSENT", True)),
            vision_consent_granted=as_bool(g("VISION_CONSENT_GRANTED", False)),
            vision_blocklist=as_csv(g("VISION_BLOCKLIST", "")) or cls.vision_blocklist,
            vision_redact_pii=as_bool(g("VISION_REDACT_PII", True)),
            vision_keep_screenshots=as_bool(g("VISION_KEEP_SCREENSHOTS", False)),
            vision_allowlist=as_csv(g("VISION_ALLOWLIST", "")),
            screenshot_region=g("NIXI_SCREENSHOT_REGION", ""),
            require_confirmation=as_bool(g("REQUIRE_CONFIRMATION", True)),
            allowed_tools=as_csv(g("NIXI_ALLOWED_TOOLS", "")),
            denied_tools=as_csv(g("NIXI_DENIED_TOOLS", "wipe_disk,format_drive")),
            dry_run=as_bool(g("NIXI_DRY_RUN", False)),
            shell_enabled=as_bool(g("NIXI_SHELL_ENABLED", True)),
            shell_timeout=as_int(g("NIXI_SHELL_TIMEOUT", 15), 15),
            code_timeout=as_int(g("NIXI_CODE_TIMEOUT", 20), 20),
            sandbox_code=as_bool(g("NIXI_SANDBOX_CODE", True)),
            code_network=as_bool(g("NIXI_CODE_NETWORK", False)),
            audit_enabled=as_bool(g("NIXI_AUDIT_ENABLED", True)),
            theme=g("NIXI_THEME", "dark"),
            font_scale=as_float(g("NIXI_FONT_SCALE", 1.0), 1.0),
            opacity=as_float(g("NIXI_OPACITY", 0.96), 0.96),
            screen_index=as_int(g("NIXI_SCREEN_INDEX", -1), -1),
            island_y=as_int(g("NIXI_ISLAND_Y", 10), 10),
            start_minimized=as_bool(g("NIXI_START_MINIMIZED", False)),
            launch_at_startup=as_bool(g("NIXI_LAUNCH_AT_STARTUP", False)),
            notifications_enabled=as_bool(g("NIXI_NOTIFICATIONS", True)),
            notification_history=as_int(g("NIXI_NOTIFICATION_HISTORY", 50), 50),
            battery_enabled=as_bool(g("NIXI_BATTERY_DAEMON", True)),
            clipboard_enabled=as_bool(g("NIXI_CLIPBOARD_DAEMON", True)),
            briefing_enabled=as_bool(g("NIXI_BRIEFING_DAEMON", True)),
            briefing_hour=as_int(g("NIXI_BRIEFING_HOUR", 9), 9),
            briefing_minute=as_int(g("NIXI_BRIEFING_MINUTE", 0), 0),
            briefing_latitude=as_float(g("NIXI_LATITUDE", 28.6139), 28.6139),
            briefing_longitude=as_float(g("NIXI_LONGITUDE", 77.2090), 77.2090),
            briefing_news_feeds=as_csv(g("NIXI_NEWS_FEEDS", "")),
            calendar_ics_paths=as_csv(g("NIXI_CALENDAR_ICS", "")),
            data_dir=data_dir,
            knowledge_dirs=as_csv(g("NIXI_KNOWLEDGE_DIRS", "")),
            knowledge_extensions=as_csv(g("NIXI_KNOWLEDGE_EXT", ".md,.txt,.py,.json,.csv,.rst")),
            timers_persist=as_bool(g("NIXI_TIMERS_PERSIST", True)),
            plugins_enabled=as_bool(g("NIXI_PLUGINS_ENABLED", True)),
            plugins_dir=g("NIXI_PLUGINS_DIR", str(Path(data_dir) / "plugins")),
            api_enabled=as_bool(g("NIXI_API_ENABLED", False)),
            api_host=g("NIXI_API_HOST", "127.0.0.1"),
            api_port=as_int(g("NIXI_API_PORT", 8765), 8765),
            api_token=g("NIXI_API_TOKEN", ""),
            log_level=g("LOG_LEVEL", "INFO"),
            log_file=g("NIXI_LOG_FILE", str(Path(data_dir) / "nixi.log")),
            crash_reports=as_bool(g("NIXI_CRASH_REPORTS", False)),
            auto_update=as_bool(g("NIXI_AUTO_UPDATE", False)),
        )
        if cfg.local_only:
            cfg.vision_enabled = False
        return cfg

    def provider_specs(self) -> list[ProviderSpec]:
        """Ordered failover chain. Local-only/offline mode never emits network calls."""
        if self.local_only or self.provider == "offline":
            return [ProviderSpec("offline", kind="offline", model="local")]
        specs: list[ProviderSpec] = []
        p = self.provider
        if p == "freellmapi":
            specs.append(ProviderSpec("freellmapi", base_url=self.base_url, api_key=self.api_key,
                                      model=self.model, vision_model=self.vision_model, timeout=self.request_timeout))
        elif p == "openai":
            specs.append(ProviderSpec("openai", base_url=self.openai_base_url, api_key=self.openai_api_key,
                                      model=self.openai_model, vision_model=self.openai_model, timeout=self.request_timeout))
        elif p == "anthropic":
            specs.append(ProviderSpec("anthropic", base_url="https://api.anthropic.com/v1", api_key=self.anthropic_api_key,
                                      model=self.anthropic_model, vision_model=self.anthropic_model, timeout=self.request_timeout))
        elif p == "gemini":
            specs.append(ProviderSpec("gemini", base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                                      api_key=self.gemini_api_key, model=self.gemini_model,
                                      vision_model=self.gemini_model, timeout=self.request_timeout))
        elif p in ("ollama", "lmstudio"):
            base = self.ollama_base_url if p == "ollama" else "http://127.0.0.1:1234/v1"
            specs.append(ProviderSpec(p, base_url=base, model=self.ollama_model,
                                      vision_model=self.ollama_model, timeout=self.request_timeout))
        # Always append local fallbacks: they keep the assistant useful offline.
        specs.append(ProviderSpec("ollama-local", base_url=self.ollama_base_url, model=self.ollama_model,
                                  vision_model=self.ollama_model, timeout=min(self.request_timeout, 8.0)))
        specs.append(ProviderSpec("offline", kind="offline", model="local"))
        return specs

    def validate(self) -> list[str]:
        """Non-fatal problems the user should know about."""
        issues: list[str] = []
        if self.theme not in ("dark", "light", "high-contrast"):
            issues.append(f"Unknown theme '{self.theme}'; falling back to dark.")
        if not 0.5 <= self.font_scale <= 2.0:
            issues.append("font_scale should be between 0.5 and 2.0.")
        if not 0.2 <= self.opacity <= 1.0:
            issues.append("opacity should be between 0.2 and 1.0.")
        if not 1 <= self.api_port <= 65535:
            issues.append("api_port must be 1..65535.")
        if not 0 <= self.briefing_hour <= 23 or not 0 <= self.briefing_minute <= 59:
            issues.append("briefing time is invalid.")
        if self.voice_gate_mode not in ("open", "wake", "push_to_talk", "muted"):
            issues.append("voice_gate_mode is invalid; using 'open'.")
        if self.provider in ("openai", "anthropic", "gemini") and not self._has_provider_key():
            issues.append(f"Provider '{self.provider}' has no API key configured.")
        if self.exa_api_key and len(self.exa_api_key) < 8:
            issues.append("EXA_API_KEY looks malformed.")
        if self.local_only and self.vision_enabled:
            issues.append("local_only forces vision_enabled=False.")
        return issues

    def _has_provider_key(self) -> bool:
        return bool({"openai": self.openai_api_key, "anthropic": self.anthropic_api_key,
                     "gemini": self.gemini_api_key}.get(self.provider))

    def as_dict(self, mask_secrets: bool = True) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, tuple):
                value = list(value)
            if mask_secrets and (f.name in SECRET_KEYS or "api_key" in f.name or "token" in f.name) and value:
                value = "***"
            out[f.name] = value
        return out

    def data_path(self, *parts: str) -> Path:
        p = Path(self.data_dir).expanduser().joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


_config: NixiConfig | None = None


def get_config(refresh: bool = False, env: Mapping[str, str] | None = None) -> NixiConfig:
    global _config
    if _config is None or refresh or env is not None:
        _config = NixiConfig.from_env(env)
    return _config


def set_config(config: NixiConfig) -> None:
    global _config
    _config = config
