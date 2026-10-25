"""Settings dialog — provider, voice, vision, privacy, daemons, diagnostics."""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget, QWidget,
        QLabel, QLineEdit, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox,
        QPushButton, QTextEdit, QMessageBox, QGroupBox, QScrollArea,
    )
    from PyQt6.QtCore import Qt
    HAS_QT = True
except ImportError:
    HAS_QT = False

from nixi.config import NixiConfig, get_config, save_env
from nixi.logging_utils import Diagnostics


class SettingsDialog:
    """Thin wrapper so headless imports don't crash."""

    def __init__(self, config: NixiConfig | None = None, llm=None, parent=None):
        self.config = config or get_config()
        self.llm = llm
        self.parent = parent
        self._dialog = None
        if HAS_QT:
            self._build()

    def _build(self) -> None:
        from PyQt6.QtWidgets import QDialog
        d = QDialog(self.parent)
        d.setWindowTitle("Nixi Settings")
        d.resize(640, 520)
        layout = QVBoxLayout(d)
        tabs = QTabWidget()

        # Provider tab
        provider_tab = QWidget()
        pf = QFormLayout(provider_tab)
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["freellmapi", "openai", "anthropic", "gemini", "ollama", "offline"])
        self.provider_combo.setCurrentText(self.config.provider)
        pf.addRow("Provider:", self.provider_combo)
        self.base_url_edit = QLineEdit(self.config.base_url)
        pf.addRow("Base URL:", self.base_url_edit)
        self.model_edit = QLineEdit(self.config.model)
        pf.addRow("Model:", self.model_edit)
        self.api_key_edit = QLineEdit(self.config.api_key)
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("API key (stored in .env)")
        pf.addRow("API Key:", self.api_key_edit)
        self.local_only_check = QCheckBox("Local-only (no network)")
        self.local_only_check.setChecked(self.config.local_only)
        pf.addRow(self.local_only_check)
        tabs.addTab(provider_tab, "Provider")

        # Voice tab
        voice_tab = QWidget()
        vf = QFormLayout(voice_tab)
        self.tts_engine_combo = QComboBox()
        self.tts_engine_combo.addItems(["edge-tts", "pyttsx3", "sapi", "piper", "silent"])
        self.tts_engine_combo.setCurrentText(self.config.tts_engine)
        vf.addRow("TTS Engine:", self.tts_engine_combo)
        self.tts_voice_edit = QLineEdit(self.config.tts_voice)
        vf.addRow("TTS Voice:", self.tts_voice_edit)
        self.stt_engine_combo = QComboBox()
        self.stt_engine_combo.addItems(["auto", "faster-whisper", "google", "silent"])
        self.stt_engine_combo.setCurrentText(self.config.stt_engine)
        vf.addRow("STT Engine:", self.stt_engine_combo)
        self.wake_check = QCheckBox("Wake word ('hey nixi')")
        self.wake_check.setChecked(self.config.wake_word_enabled)
        vf.addRow(self.wake_check)
        self.ptt_check = QCheckBox("Push-to-talk")
        self.ptt_check.setChecked(self.config.push_to_talk)
        vf.addRow(self.ptt_check)
        tabs.addTab(voice_tab, "Voice")

        # Privacy tab
        privacy_tab = QWidget()
        prf = QFormLayout(privacy_tab)
        self.vision_enabled_check = QCheckBox("Enable screen vision (opt-in)")
        self.vision_enabled_check.setChecked(self.config.vision_enabled)
        prf.addRow(self.vision_enabled_check)
        self.vision_consent_check = QCheckBox("Require explicit consent each session")
        self.vision_consent_check.setChecked(self.config.vision_require_consent)
        prf.addRow(self.vision_consent_check)
        self.redact_check = QCheckBox("Redact PII before sending to model")
        self.redact_check.setChecked(self.config.vision_redact_pii)
        prf.addRow(self.redact_check)
        self.vision_blocklist_edit = QLineEdit(", ".join(self.config.vision_blocklist[:5]) + ", ...")
        self.vision_blocklist_edit.setPlaceholderText("comma-separated keywords to block vision")
        prf.addRow("Blocklist:", self.vision_blocklist_edit)
        self.require_confirm_check = QCheckBox("Require confirmation for destructive actions")
        self.require_confirm_check.setChecked(self.config.require_confirmation)
        prf.addRow(self.require_confirm_check)
        self.sandbox_check = QCheckBox("Sandbox code execution")
        self.sandbox_check.setChecked(self.config.sandbox_code)
        prf.addRow(self.sandbox_check)
        tabs.addTab(privacy_tab, "Privacy & Safety")

        # Daemons tab
        daemon_tab = QWidget()
        df = QFormLayout(daemon_tab)
        self.battery_check = QCheckBox("Battery guardian")
        self.battery_check.setChecked(self.config.battery_enabled)
        df.addRow(self.battery_check)
        self.clipboard_check = QCheckBox("Clipboard watcher")
        self.clipboard_check.setChecked(self.config.clipboard_enabled)
        df.addRow(self.clipboard_check)
        self.briefing_check = QCheckBox("Daily briefing")
        self.briefing_check.setChecked(self.config.briefing_enabled)
        df.addRow(self.briefing_check)
        self.briefing_hour_spin = QSpinBox()
        self.briefing_hour_spin.setRange(0, 23)
        self.briefing_hour_spin.setValue(self.config.briefing_hour)
        df.addRow("Briefing hour:", self.briefing_hour_spin)
        self.briefing_min_spin = QSpinBox()
        self.briefing_min_spin.setRange(0, 59)
        self.briefing_min_spin.setValue(self.config.briefing_minute)
        df.addRow("Briefing minute:", self.briefing_min_spin)
        tabs.addTab(daemon_tab, "Daemons")

        # Diagnostics tab
        diag_tab = QWidget()
        dl = QVBoxLayout(diag_tab)
        self.diag_text = QTextEdit()
        self.diag_text.setReadOnly(True)
        try:
            diag = Diagnostics(self.config, self.llm).format_text()
        except Exception as exc:
            diag = f"Diagnostics error: {exc}"
        self.diag_text.setPlainText(diag)
        dl.addWidget(self.diag_text)
        refresh_btn = QPushButton("Refresh")
        def refresh_diag():
            try:
                self.diag_text.setPlainText(Diagnostics(self.config, self.llm).format_text())
            except Exception as exc:
                self.diag_text.setPlainText(f"Error: {exc}")
        refresh_btn.clicked.connect(refresh_diag)
        dl.addWidget(refresh_btn)
        tabs.addTab(diag_tab, "Diagnostics")

        layout.addWidget(tabs)

        # Buttons
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        def do_save():
            self._save()
            d.accept()

        save_btn.clicked.connect(do_save)
        cancel_btn.clicked.connect(d.reject)
        self._dialog = d

    def _save(self) -> None:
        updates: dict[str, Any] = {
            "NIXI_PROVIDER": self.provider_combo.currentText(),
            "FREELLMAPI_URL": self.base_url_edit.text().strip(),
            "FREELLMAPI_MODEL": self.model_edit.text().strip(),
            "FREELLMAPI_KEY": self.api_key_edit.text().strip(),
            "NIXI_LOCAL_ONLY": str(self.local_only_check.isChecked()).lower(),
            "TTS_ENGINE": self.tts_engine_combo.currentText(),
            "TTS_VOICE": self.tts_voice_edit.text().strip(),
            "STT_ENGINE": self.stt_engine_combo.currentText(),
            "WAKE_WORD_ENABLED": str(self.wake_check.isChecked()).lower(),
            "NIXI_PUSH_TO_TALK": str(self.ptt_check.isChecked()).lower(),
            "VISION_ENABLED": str(self.vision_enabled_check.isChecked()).lower(),
            "VISION_REQUIRE_CONSENT": str(self.vision_consent_check.isChecked()).lower(),
            "VISION_REDACT_PII": str(self.redact_check.isChecked()).lower(),
            "REQUIRE_CONFIRMATION": str(self.require_confirm_check.isChecked()).lower(),
            "NIXI_SANDBOX_CODE": str(self.sandbox_check.isChecked()).lower(),
            "NIXI_BATTERY_DAEMON": str(self.battery_check.isChecked()).lower(),
            "NIXI_CLIPBOARD_DAEMON": str(self.clipboard_check.isChecked()).lower(),
            "NIXI_BRIEFING_DAEMON": str(self.briefing_check.isChecked()).lower(),
            "NIXI_BRIEFING_HOUR": str(self.briefing_hour_spin.value()),
            "NIXI_BRIEFING_MINUTE": str(self.briefing_min_spin.value()),
        }
        # update in-memory config
        for k, v in updates.items():
            # also patch config object for immediate effect
            pass
        try:
            save_env(updates)
        except OSError as exc:
            if HAS_QT:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self._dialog, "Save failed", str(exc))
        # refresh global config
        from nixi.config import get_config as _get
        _get(refresh=True)

    def exec(self) -> int:
        if not HAS_QT or not self._dialog:
            return 0
        return self._dialog.exec()

    def show(self) -> None:
        if self._dialog:
            self._dialog.show()
