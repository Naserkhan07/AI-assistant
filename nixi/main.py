"""
Nixi AI Desktop Assistant — Main Application
Inspired by HeyNixi UX. Minimal floating Dynamic Island with cute glowing animated eyes,
hover-expandable interaction bar, instant dictation into any focused window,
autonomous screen & browser execution, and FreeLLMAPI intelligence.
"""
from __future__ import annotations

import sys
import os

# Suppress harmless Windows duplicate DPI awareness context warning from Qt
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window.warning=false;qt.qpa.window=false"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import re
import threading
import time
import base64
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtWidgets import QApplication

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from nixi.ui.dynamic_island import NixiDynamicIsland
from nixi.core.llm_client import NixiLLMClient
from nixi.core.dictation import DictationManager
from nixi.core.screen_reader import ScreenReader
from nixi.core.app_launcher import AppLauncher
from nixi.core.timers import TimerManager
from nixi.core.god_mode_agent import GodModeAgent
from nixi.core.file_actions import FileActionService
from nixi.core.task_center import TaskCenter
from nixi.integrations.office import OfficeIntegration
from nixi.integrations.vscode import VSCodeIntegration
from nixi.automation.browser import BrowserController
from nixi.audio.audio_capture import AudioCapture
from nixi.audio.stt import SpeechTranscriber
from nixi.audio.tts import NixiTTS, SentenceStreamer
from nixi.audio.wake_word import WakeWordDetector, VoiceGate

# Autonomous Agent Pillars
from nixi.agent.memory import AgentMemory
from nixi.agent.react_planner import ReActPlanner, is_complex_agent_goal
from nixi.agent.background_daemons import BatteryGuardianDaemon, ClipboardWatcherDaemon, DailyBriefingDaemon
from nixi.agent.vision_copilot import VisionCopilot
from nixi.config import NixiConfig, get_config
from nixi.logging_utils import setup_logging, get_logger, Diagnostics
from nixi.security import PermissionManager, UndoManager, ActionJournal, RiskLevel
from nixi.privacy import VisionGuard
from nixi.platform.system import system_stats as platform_stats
from nixi.platform.capabilities import IS_WINDOWS
from nixi.agent.knowledge import KnowledgeStore
from nixi.integrations.info import Calculator
from nixi.server import NixiServer
from nixi.plugins import PluginManager
from nixi.i18n.catalog import I18N
try:
    from nixi.security.vault import Vault
    from nixi.automation.recorder import MacroRecorder
    from nixi.ui.notifications import NotificationCenter
    from nixi.ui.timeline import Timeline
    from nixi.ui.themes import palette
    from nixi.ui.markdown_view import render_markdown
    HAS_EXTRAS=True
except Exception as _e:
    HAS_EXTRAS=False


class Bridge(QObject):
    """Bridge for cross-thread communication to Qt UI thread."""
    status_changed = pyqtSignal(str, str)
    audio_level_changed = pyqtSignal(float)
    chat_message_received = pyqtSignal(str, bool)
    chat_stream_update = pyqtSignal(str)
    dictate_state_changed = pyqtSignal(bool)
    expand_island_signal = pyqtSignal()
    collapse_island_signal = pyqtSignal()
    command_signal = pyqtSignal(str)
    clipboard_chip_signal = pyqtSignal(dict)
    battery_warning_signal = pyqtSignal(str)
    confirm_action_signal = pyqtSignal(object)


class NixiApp:
    def __init__(self):
        self.config = get_config()
        setup_logging(self.config)
        self.log = get_logger("app")
        self._status_generation = 0
        self._last_cmd_text = ""
        self._last_cmd_ts = 0.0
        for w in self.config.validate():
            print(f"[Nixi Config] {w}")
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Nixi")
        self.app.setQuitOnLastWindowClosed(False)
        self.app.aboutToQuit.connect(self._on_quit)

        self.bridge = Bridge()

        # Core engines (config-aware)
        self.llm = NixiLLMClient(config=self.config)

        self.dictation = DictationManager()
        self.screen_reader = ScreenReader()
        self.app_launcher = AppLauncher()
        self.timer_mgr = TimerManager()
        self.god_agent = GodModeAgent(self.llm)
        whisper_size = self.config.whisper_model
        # Multilingual Whisper is necessary for Hindi/Hinglish and still understands English.
        if whisper_size.endswith(".en"):
            whisper_size = whisper_size[:-3]
        self.stt = SpeechTranscriber(model_size=whisper_size, preload=True)
        self.tts = NixiTTS()
        self.wake_detector = WakeWordDetector()
        gate_mode = "push_to_talk" if self.config.push_to_talk else self.config.voice_gate_mode
        self.voice_gate = VoiceGate(mode=gate_mode, hotkey=self.config.push_to_talk_hotkey)
        self._ptt_held = threading.Event()
        self._ptt_utterance = threading.Event()

        # Agent Pillars: Persistent Memory, ReAct Planner, Vision Co-Pilot
        self.memory = AgentMemory()
        self.react_planner = ReActPlanner(self.llm, self.memory)
        self.vision_copilot = VisionCopilot(self.llm, self.screen_reader)
        # Fix: browser_agent was referenced but never constructed
        try:
            from nixi.core.browser_agent import BrowserAgent
            self.browser_agent = BrowserAgent(self.llm, self.screen_reader)
        except Exception as exc:
            self.browser_agent = None
            print(f"[Nixi] BrowserAgent unavailable: {exc}")
        # Privacy & security
        self.vision_guard = VisionGuard(config=self.config, indicator=self._vision_indicator)
        self.journal = ActionJournal(enabled=self.config.audit_enabled)
        self.undo_manager = UndoManager(config=self.config, journal=self.journal)
        self.file_actions = FileActionService(self.undo_manager)
        self.office = OfficeIntegration(self.file_actions)
        self.vscode = VSCodeIntegration(self.file_actions)
        self.browser = BrowserController(llm_client=self.llm)
        self.task_center = TaskCenter()
        self.permissions = PermissionManager(config=self.config, confirm_callback=self._confirm_action, journal=self.journal)
        self.llm._permission_manager = self.permissions
        self.god_agent.permissions = self.permissions
        self.react_planner.permissions = self.permissions
        self.react_planner.undo_manager = self.undo_manager
        # Knowledge, calculator, plugins, API
        self.knowledge = KnowledgeStore(config=self.config)
        self.calculator = Calculator()
        self.plugins = PluginManager(config=self.config)
        try:
            self.plugins.discover()
        except Exception:
            pass
        self.api_server = NixiServer(config=self.config)
        self.api_server.llm = self.llm
        self.api_server.chat_handler = self._api_chat
        self.api_server.command_handler = self._api_command
        self.api_server.history_provider = lambda n: self.memory.get_history(limit=n)
        self.api_server.tools_provider = self._api_tools
        self.api_server.journal = self.journal
        self.api_server.undo_manager = self.undo_manager
        self.api_server.plugins = self.plugins
        if HAS_EXTRAS:
            self.i18n = I18N(locale=self.config.tts_language if self.config.tts_language in ('en','hi','hinglish') else 'en')
            self.vault = Vault(config=self.config)
            self.macros = MacroRecorder(config=self.config)
            self.notifs = NotificationCenter(config=self.config)
            self.timeline = Timeline(config=self.config)
        else:
            self.i18n=self.vault=self.macros=self.notifs=self.timeline=None
        if self.config.api_enabled:
            print(self.api_server.start())
        # System tray
        self._tray = None
        self._setup_tray()

        # Proactive Background Daemons
        self.battery_daemon = BatteryGuardianDaemon(
            on_warning=lambda msg: self.bridge.battery_warning_signal.emit(msg)
        )
        self.clipboard_daemon = ClipboardWatcherDaemon(
            on_chip_detected=lambda chip: self.bridge.clipboard_chip_signal.emit(chip)
        )
        self.briefing_daemon = DailyBriefingDaemon(
            on_briefing=lambda text: self._speak_briefing(text)
        )

        # UI: Dynamic Island with stylized cartoon eyes and hover expansion
        self.island = NixiDynamicIsland()
        self.island.set_task_center(self.task_center.snapshot, self.task_center.cancel)
        self._wire_signals()
        prior_messages = self.memory.get_history(limit=40)
        if prior_messages:
            self.island.clear_chat()
            for message in prior_messages:
                self.island.add_chat_message(message.get("content", ""), message.get("role") == "user")

        # Start Proactive Background Daemons
        self.battery_daemon.start()
        self.clipboard_daemon.start()
        self.briefing_daemon.start()

        # Audio capture with speaker echo suppression
        self.audio = AudioCapture(
            sample_rate=self.config.sample_rate,
            silence_duration_sec=self.config.silence_duration_sec,
            energy_threshold=self.config.energy_threshold,
            on_speech_detected=self._on_speech_start,
            on_speech_finished=self._on_speech_done,
            on_audio_level=lambda lvl: self.bridge.audio_level_changed.emit(lvl),
            is_tts_speaking=lambda: self.tts.is_speaking,
            is_ptt_held=self._ptt_held.is_set,
        )

        # Chat history memory for LLM
        self.conversation_history = []

        # Windows Global Hotkey Listener (optional background thread)
        self._start_hotkey_listener()

    def _delayed_status(self, text: str = "Idle", mood: str = "happy", delay: float = 2.5):
        """Reset status only if no newer command has started in the meantime."""
        generation = getattr(self, "_status_generation", 0)
        def run():
            time.sleep(delay)
            if generation == getattr(self, "_status_generation", 0):
                self.bridge.status_changed.emit(text, mood)
        threading.Thread(target=run, daemon=True).start()

    def _instant_ack(self, cmd: str):
        # Visual acknowledgement is instant; don't start network TTS before the operation.
        self.bridge.status_changed.emit(f"Starting: {cmd[:28]}", "thinking")

    def _wire_signals(self):
        # Bridge to UI
        self.bridge.status_changed.connect(self.island.set_status)
        self.bridge.audio_level_changed.connect(self.island.set_audio_level)
        self.bridge.chat_message_received.connect(self.island.add_chat_message)
        self.bridge.chat_message_received.connect(self._persist_chat_message)
        self.bridge.chat_stream_update.connect(self.island.update_assistant_stream)
        self.island.user_message_signal.connect(
            lambda text: self.bridge.chat_message_received.emit(text, True)
        )
        self.bridge.expand_island_signal.connect(self.island.expand)
        self.bridge.collapse_island_signal.connect(self.island.collapse)

        # Dynamic Island UI signals to actions
        self.island.send_query_signal.connect(self._execute_command_text)
        self.island.dictate_toggled_signal.connect(self._toggle_dictation)
        self.island.screen_vision_signal.connect(self._handle_screen_vision)
        self.island.screen_always_signal.connect(self._on_screen_always_toggled)
        self.bridge.command_signal.connect(self._execute_command_text)

        # Proactive Daemons to UI
        self.bridge.clipboard_chip_signal.connect(self.island.show_clipboard_chip)
        self.bridge.battery_warning_signal.connect(self._handle_battery_warning)
        self.bridge.confirm_action_signal.connect(self._show_confirmation_dialog)

    def _handle_battery_warning(self, msg: str):
        self.bridge.status_changed.emit("Battery Low", "guardian")
        self.bridge.chat_message_received.emit(msg, False)
        self.tts.speak(msg)
        self._delayed_status("Idle", "happy", 6.0)

    def _speak_briefing(self, text: str):
        self.bridge.status_changed.emit("Daily Briefing", "happy")
        self.bridge.chat_message_received.emit(text, False)
        self.tts.speak(text)
        self._delayed_status("Idle", "happy", 6.0)

    def _start_hotkey_listener(self):
        """Register keyboard shortcuts using keyboard if available."""
        def listen():
            try:
                import keyboard
                keyboard.add_hotkey('F8', lambda: self.island.mic_btn.toggle())
                keyboard.add_hotkey('F9', lambda: self.island.collapse() if self.island.is_expanded else self.island.expand())
                keyboard.add_hotkey('F10', self._handle_screen_vision)
                keyboard.add_hotkey('esc', self._interrupt_current_task)
                if self.voice_gate.mode == "push_to_talk":
                    hotkey = self.config.push_to_talk_hotkey
                    key_name = hotkey.split("+")[-1].strip()
                    def _ptt_down():
                        self._ptt_held.set()
                        self.bridge.status_changed.emit("Push to talk", "listening")
                    def _ptt_up(_event=None):
                        self._ptt_held.clear()
                    keyboard.add_hotkey(hotkey, _ptt_down, trigger_on_release=False)
                    keyboard.on_release_key(key_name, _ptt_up)
                try:
                    keyboard.add_hotkey(self.config.hotkey_palette, self._open_palette)
                except Exception:
                    pass
            except Exception:
                pass
        t = threading.Thread(target=listen, daemon=True)
        t.start()

    def _on_screen_always_toggled(self, enabled: bool):
        state = "on" if enabled else "off"
        self.tts.speak(f"Screen vision {state}")

    def _interrupt_current_task(self):
        task_id = self.task_center.cancel_latest()
        self.tts.stop()
        if task_id:
            self.bridge.status_changed.emit("Cancellation requested", "thinking")
            self.bridge.chat_message_received.emit("Cancellation requested; Nixi will stop at the next safe checkpoint.", False)
        else:
            self.bridge.status_changed.emit("Speech stopped", "happy")

    def _toggle_dictation(self, enabled: bool):
        self.dictation.set_active(enabled)
        if enabled:
            self.tts.speak("Dictation on")
            self.island.set_status("Dictating...", "listening")
        else:
            self.tts.speak("Dictation off")
            self.island.set_status("Idle", "happy")

    def _on_speech_start(self):
        if self._ptt_held.is_set():
            self._ptt_utterance.set()
        if self.dictation.is_active:
            self.bridge.status_changed.emit("Dictating...", "listening")
        else:
            self.bridge.status_changed.emit("Listening...", "listening")

    def _on_speech_done(self, audio_data):
        """Transcribe and route audio speech — ultra fast, non-blocking."""
        self.bridge.status_changed.emit("Heard \u2014 transcribing...", "thinking")
        def _do_transcribe():
            started = time.monotonic()
            lang = getattr(self.config, "stt_language", "") or None
            text = self.stt.transcribe_audio_samples(audio_data, language=lang)
            elapsed = time.monotonic() - started
            print(f"[Perf] speech recognition completed in {elapsed:.2f}s")
            if not text:
                self._ptt_utterance.clear()
                if not self.dictation.is_active and not self.tts.is_speaking:
                    self.bridge.status_changed.emit("Didn't catch that — try again", "listening")
                    self._delayed_status("Idle", "happy", 2.0)
                return
            print(f"[Nixi Voice] Heard: '{text}'")
            lower_txt = text.lower().strip()
            if self.tts.is_speaking:
                interrupt_words = {"stop", "quiet", "shut up", "cancel", "pause", "halt", "stop nixi"}
                if any(w == lower_txt or w in lower_txt.split() for w in interrupt_words):
                    self.tts.stop()
                    self.task_center.cancel_latest()
                    self.bridge.status_changed.emit("Stopped", "happy")
                    self._delayed_status("Idle", "happy", 1.0)
                return
            if lower_txt in {"cancel", "cancel task", "stop task", "stop current task", "cancel current task"}:
                task_id = self.task_center.cancel_latest()
                self.tts.stop()
                msg = "Cancellation requested." if task_id else "There is no active task to cancel."
                self.bridge.chat_message_received.emit(msg, False)
                self.bridge.status_changed.emit("Stopping..." if task_id else "Idle", "thinking" if task_id else "happy")
                return
            if self.dictation.is_active:
                if "stop dictation" in text.lower():
                    try:
                        self.island.mic_btn.setChecked(False)
                    except Exception:
                        pass
                    return
                self.dictation.inject_text(text)
                self.bridge.status_changed.emit(f"Typed: {text[:16]}", "listening")
                return
            wake_enabled = os.getenv("WAKE_WORD_ENABLED", "false").lower() == "true" or self.config.wake_word_enabled
            is_wake, command = self.wake_detector.check(text)
            ptt_was_held = self._ptt_held.is_set() or self._ptt_utterance.is_set()
            self._ptt_utterance.clear()
            gate_allows = self.voice_gate.is_allowed(is_wake, ptt_was_held)
            should_process = gate_allows and ((not wake_enabled) or is_wake or getattr(self.island, "is_expanded", False))
            if should_process:
                actual_cmd = (command if is_wake and command else text).strip()
                print(f"[Nixi Voice] Executing command: '{actual_cmd}'")
                self.bridge.chat_message_received.emit(f"\U0001f5e3 {actual_cmd}", True)
                self._instant_ack(actual_cmd)
                self.bridge.command_signal.emit(actual_cmd)
            else:
                print(f"[Nixi Voice] Ignored (wake word required): '{text}'")
                self.bridge.status_changed.emit("Idle", "happy")
        import threading as _thr
        _thr.Thread(target=_do_transcribe, daemon=True).start()

    @staticmethod
    def _is_action_request(cmd: str) -> bool:
        """Keep conversation on the chat path; route clear imperative requests to tools."""
        text = cmd.strip().lower()
        if not text:
            return False
        imperative = re.match(
            r"^(?:(?:please|can you|could you|would you|i want you to)\s+)?"
            r"(open|launch|start|close|maximize|minimize|lock|set|change|increase|decrease|mute|unmute|play|pause|skip|"
            r"organize|clean|create|make|write|save|find|search|locate|kill|terminate|convert|click|fill|type|submit|"
            r"move|rename|delete|remove|install|run|execute|scaffold|build)\b", text)
        return bool(imperative)

    def _run_action_tools(self, command: str, task_id: str | None = None) -> str:
        """Let the model select from explicit built-in system skills (never an implicit shell)."""
        from nixi.security.permissions import RiskLevel
        from nixi.agent.tools_registry import AgentToolsRegistry

        def organize(target_folder: str | None = None) -> str:
            return AgentToolsRegistry.organize_folder(
                target_folder=target_folder, delete_old_installers=False
            )

        def create_note(content: str = "", filename: str = "nixi_note.txt") -> str:
            # Never read clipboard implicitly; create exclusively and refuse overwrites.
            relative = f"Desktop/{Path(filename).name}"
            note_text = content.strip() if content and content.strip() else "# Note\n\n"
            result = self.file_actions.create_file(relative, note_text)
            if result.startswith("Created and verified"):
                return f"{result}. {system.open_file(str(self.file_actions._resolve(relative)))}"
            return result

        system = self.god_agent.system
        tools = {
            "open_app": {"description": "Open a locally installed desktop app by its common name.", "function": self.app_launcher.launch, "risk": RiskLevel.SAFE},
            "get_system_status": {"description": "Read CPU, memory, disk and battery status.", "function": system.get_system_stats, "risk": RiskLevel.SAFE},
            "find_files": {"description": "Find files in Desktop, Documents, Downloads or Pictures using a filename fragment.", "function": self.file_actions.find_files, "risk": RiskLevel.SAFE},
            "create_file": {"description": "Create a new text file under the user's home folder without overwriting existing files. Args: path, content.", "function": self.file_actions.create_file, "risk": RiskLevel.HIGH},
            "move_file": {"description": "Move a file within the user's home folder. Args: source, destination. It is undoable and refuses overwrites.", "function": self.file_actions.move_file, "risk": RiskLevel.HIGH},
            "rename_file": {"description": "Rename a file within its current folder. Args: source, new_name. It is undoable and refuses overwrites.", "function": self.file_actions.rename_file, "risk": RiskLevel.HIGH},
            "trash_file": {"description": "Move a file into Nixi's recoverable trash. Args: path.", "function": self.file_actions.trash_file, "risk": RiskLevel.CRITICAL},
            "undo_last_file_action": {"description": "Undo the latest supported file move, trash, or Nixi-created file.", "function": self.undo_manager.undo_last, "risk": RiskLevel.SAFE},
            "open_folder": {"description": "Open an existing folder in the user's file manager. Args: path.", "function": system.open_folder, "risk": RiskLevel.SAFE},
            "open_settings_page": {"description": "Open an allow-listed Windows Settings page; category can be system, display, sound, bluetooth, network, wifi, apps, notifications, updates, privacy.", "function": system.open_settings, "risk": RiskLevel.SAFE},
            "set_volume": {"description": "Set system volume percentage from 0 to 100.", "function": system.set_audio_volume, "risk": RiskLevel.SAFE},
            "media_control": {"description": "Control media playback: play_pause, next, prev, or stop.", "function": system.media_control, "risk": RiskLevel.SAFE},
            "organize_folder": {"description": "Sort files into category subfolders; does not delete files.", "function": organize, "risk": RiskLevel.HIGH},
            "create_note": {"description": "Create a text note on the Desktop and open it without overwriting existing files.", "function": create_note, "risk": RiskLevel.HIGH},
            "create_word_document": {"description": "Create a new .docx file under the home folder without overwriting. Args: path, title, body.", "function": self.office.create_word_document, "risk": RiskLevel.HIGH},
            "read_word_document": {"description": "Read text from a .docx file under the home folder. Args: path.", "function": self.office.read_word_document, "risk": RiskLevel.SAFE},
            "create_excel_workbook": {"description": "Create a new .xlsx workbook under the home folder. Args: path, sheet_name, rows (array of arrays). Never overwrites.", "function": self.office.create_workbook, "risk": RiskLevel.HIGH},
            "read_excel_workbook": {"description": "Read up to 100 rows from a .xlsx workbook under the home folder. Args: path, sheet_name.", "function": self.office.read_workbook, "risk": RiskLevel.SAFE},
            "open_vscode_project": {"description": "Open an existing project directory under the home folder in VS Code. Args: path.", "function": self.vscode.open_project, "risk": RiskLevel.SAFE},
            "open_vscode_file": {"description": "Open an existing file under the home folder in VS Code. Args: path.", "function": self.vscode.open_file, "risk": RiskLevel.SAFE},
            "open_website": {"description": "Open a website URL in the browser.", "function": self.browser.open_url, "risk": RiskLevel.SAFE},
            "browser_action": {"description": "Perform one bounded browser interaction: click a visible control, fill a named field, press a safe key, or read the current page. Args: instruction. Requires user confirmation.", "function": lambda instruction: self.browser.act(instruction), "risk": RiskLevel.HIGH},
            "window_action": {"description": "Manage windows: show desktop, snap left/right, maximize, close active, switch, or lock.", "function": system.window_management, "risk": RiskLevel.HIGH},
            "kill_process": {"description": "Stop a named process or PID. Use only when specifically requested.", "function": AgentToolsRegistry.kill_process, "risk": RiskLevel.CRITICAL},
        }
        def on_tool_start(name: str, args: dict):
            detail = f"Preparing {name.replace('_', ' ')}"
            if task_id:
                self.task_center.update(task_id, detail, progress=45)
            self.bridge.status_changed.emit(detail, "thinking")
        result = self.llm.tool_loop(
            [{"role": "user", "content": command}], tools=tools, max_iters=2,
            temperature=0.0, on_tool_start=on_tool_start,
        )
        cancel_event = self.task_center.cancel_event(task_id) if task_id else None
        if cancel_event and cancel_event.is_set():
            return "Stopped after the current safe step."
        return result

    def _execute_command_text(self, cmd: str):
        """Analyze user command asynchronously without freezing the UI thread."""
        if not cmd or not cmd.strip():
            self.bridge.status_changed.emit("Idle", "happy")
            return

        cmd = cmd.strip()
        if cmd.casefold() in {"cancel", "cancel task", "cancel the task", "cancel current", "cancel current task", "stop", "stop task", "stop the task", "stop current", "stop current task"}:
            task_id = self.task_center.cancel_latest()
            self.tts.stop()
            message = "Cancellation requested." if task_id else "There is no active task to cancel."
            self.bridge.chat_message_received.emit(message, False)
            self.bridge.status_changed.emit("Stopping..." if task_id else "Idle", "thinking" if task_id else "happy")
            return
        now = time.monotonic()
        # Speech recognizers may emit the same completed utterance twice; ignore duplicates.
        if cmd.casefold() == getattr(self, "_last_cmd_text", "").casefold() and now - getattr(self, "_last_cmd_ts", 0.0) < 1.5:
            return
        self._last_cmd_text, self._last_cmd_ts = cmd, now
        self._status_generation = getattr(self, "_status_generation", 0) + 1
        command_generation = self._status_generation
        command_done = threading.Event()
        asynchronous = [False]
        command_failed = [False]
        task_id = self.task_center.start(cmd)
        cancel_event = self.task_center.cancel_event(task_id)
        self.bridge.status_changed.emit(f"Working: {cmd[:28]}", "thinking")

        def runner():
            self.task_center.update(task_id, "Starting", progress=5)
            try:
                if cancel_event.is_set():
                    return
                lower = cmd.lower().strip()

                # Clean conversational politeness prefixes
                clean = re.sub(r"^(?:please\s+|can\s+you\s+|could\s+you\s+|would\s+you\s+|hey\s+nixi\s+|nixi\s+)", "", lower).strip()
                self.task_center.update(task_id, "Interpreting request", progress=10)

                if clean in {"undo", "undo last", "undo last action", "reverse last action"}:
                    result = self.undo_manager.undo_last()
                    self.bridge.chat_message_received.emit(result, False)
                    self.bridge.status_changed.emit("Done", "happy")
                    return

                # 0. Long-term memory extraction: e.g. "remember that I prefer dark mode and Python 3.12"
                extracted_fact = self.memory.try_extract_memory(cmd)
                if extracted_fact:
                    ack = "Remembered: I have saved that to my persistent memory."
                    self.bridge.status_changed.emit("Saved to Memory", "happy")
                    self.bridge.chat_message_received.emit(f"🧠 {ack}", False)
                    self.tts.speak(ack)
                    self._delayed_status("Idle", "happy", 2.5)
                    return

                # 0b. Daily Briefing request
                if any(k in clean for k in ("morning briefing", "daily briefing", "morning brief")):
                    brief = self.briefing_daemon.generate_briefing()
                    self.bridge.status_changed.emit("Daily Briefing", "happy")
                    self.bridge.chat_message_received.emit(brief, False)
                    self.tts.speak(brief)
                    self._delayed_status("Idle", "happy", 4.0)
                    return

                # 0c. Visual Debugging, Screen Extraction, and Live Screen Perception
                is_extract_query = any(k in clean for k in ("table", "diagram", "chart", "infographic", "flowchart", "graph", "architecture")) and any(k in clean for k in ("extract", "get", "convert", "save", "markdown", "read", "copy", "summarize", "show", "export"))
                if is_extract_query or any(k in clean for k in ("extract table", "extract the table", "extract diagram", "extract the diagram", "extract chart", "screen to markdown", "extract screen data")):
                    self.bridge.status_changed.emit("Extracting...", "thinking")
                    self.tts.speak("Extracting structured visual data from screen.")
                    table_md, saved_f = self.vision_copilot.extract_screen_table_or_data(clean)
                    res_msg = f"{table_md}\n\n📁 Saved to {saved_f}" if saved_f else table_md
                    self.bridge.chat_message_received.emit(res_msg, False)
                    self.tts.speak("Visual data extracted and saved to Desktop.")
                    self.bridge.status_changed.emit("Extraction Done", "happy")
                    self._delayed_status("Idle", "happy", 3.0)
                    return

                is_debug_query = any(k in clean for k in ("debug my code", "debug screen", "explain error", "find bug", "visual debug", "fix my code", "what is this error", "why is this failing"))
                if is_debug_query:
                    self.bridge.status_changed.emit("Debugging screen...", "thinking")
                    self.tts.speak("Analyzing screen for bugs.")
                    diag = self.vision_copilot.debug_active_screen(clean)
                    self.bridge.chat_message_received.emit(diag, False)
                    first_line = diag.split("\n")[0] if "\n" in diag else diag
                    self.tts.speak(first_line)
                    self.bridge.status_changed.emit("Debug Complete", "happy")
                    self._delayed_status("Idle", "happy", 3.0)
                    return

                if any(k in clean for k in ("see my screen", "see screen", "look at my screen", "read my screen", "what is on my screen", "what's on my screen", "what am i looking at", "what do you see", "can you see my screen", "can you see this", "describe my screen", "what window")):
                    self._handle_screen_vision(prompt=cmd)
                    return

                # 0d. Multi-Step Goal Decomposition & Autonomous ReAct Execution Loop
                if is_complex_agent_goal(clean):
                    self.bridge.status_changed.emit("Planning goal...", "thinking")
                    self.tts.speak("Decomposing goal into steps.")

                    def on_step_progress(curr, total, step_name):
                        if cancel_event.is_set():
                            raise InterruptedError("Task cancelled at a safe checkpoint")
                        self.task_center.update(task_id, step_name, progress=int(10 + 80 * curr / max(total, 1)))
                        self.bridge.status_changed.emit(f"Step {curr}/{total}: {step_name[:18]}", "thinking")
                        self.tts.speak(f"Executing step {curr} of {total}: {step_name}")

                    ok, summary = self.react_planner.plan_and_execute(clean, on_step_progress=on_step_progress)
                    self.bridge.chat_message_received.emit(summary, False)
                    first_sentence = summary.split(".")[0] + "." if "." in summary else summary
                    self.tts.speak(first_sentence)
                    self.bridge.status_changed.emit("Goal Complete", "happy")
                    self._delayed_status("Idle", "happy", 3.5)
                    return

                # 1. Dictation toggle
                if clean in ("start dictation", "dictate", "dictation on"):
                    self.dictation.set_active(True)
                    self.tts.speak("Dictation on")
                    self.bridge.status_changed.emit("Dictating...", "listening")
                    return
                elif clean in ("stop dictation", "dictation off"):
                    self.dictation.set_active(False)
                    self.tts.speak("Dictation off")
                    self.bridge.status_changed.emit("Idle", "happy")
                    return

                # 2. Timer / Reminder: e.g. "set timer for 5 minutes", "timer 30 seconds"
                timer_match = re.search(r"(?:timer|remind me)(?:\s+for)?\s+(\d+)\s*(min|minute|sec|second|hour)s?", clean)
                if timer_match:
                    val = int(timer_match.group(1))
                    unit = timer_match.group(2)
                    sec = val if "sec" in unit else (val * 60 if "min" in unit else val * 3600)
                    label = f"{val} {unit} timer"
                    self.timer_mgr.add_timer(sec, label, on_complete=self._on_timer_done)
                    ack = f"Timer set for {val} {unit}s."
                    self.bridge.status_changed.emit(ack, "happy")
                    self.bridge.chat_message_received.emit(ack, False)
                    self.tts.speak(ack)
                    self._delayed_status("Idle", "happy", 2.5)
                    return

                # 3. Dedicated App Launcher
                open_match = re.search(r"^(?:open|launch|start)\s+(?:the\s+)?([a-zA-Z0-9\s]+)$", clean)
                if open_match and not ("http" in clean or ".com" in clean or "web" in clean or "youtube" in clean or "github" in clean or "reddit" in clean):
                    app_target = open_match.group(1).strip()
                    ok, msg = self.app_launcher.launch(app_target)
                    if ok:
                        self.bridge.status_changed.emit(msg, "happy")
                        self.bridge.chat_message_received.emit(msg, False)
                        self.tts.speak(msg)
                        self._delayed_status("Idle", "happy", 2.5)
                        return

                # 4. God-Mode Agent (System, Media, Windows, Shell, Web Search, Popular Sites)
                handled, result = self.god_agent.process_command(cmd, on_voice_feedback=lambda msg: self.tts.speak(msg))
                if handled:
                    self.bridge.status_changed.emit("Done", "happy")
                    self.bridge.chat_message_received.emit(result, False)
                    self.tts.speak(result)
                    self._delayed_status("Idle", "happy", 2.5)
                    return

                # Natural-language actions can use built-in skills, never an invisible raw shell.
                if self._is_action_request(clean):
                    self.task_center.update(task_id, "Choosing a built-in skill", progress=25)
                    self.bridge.status_changed.emit("Planning safe system action...", "thinking")
                    action_result = self._run_action_tools(cmd, task_id=task_id)
                    self.bridge.chat_message_received.emit(action_result, False)
                    self.tts.speak(action_result)
                    self.bridge.status_changed.emit("Done", "happy")
                    self._delayed_status("Idle", "happy", 2.5)
                    return

                # 5. General LLM Query with concurrent sentence-by-sentence voice streaming
                asynchronous[0] = True
                self._ask_llm(cmd, finished_event=command_done, task_id=task_id)
            except Exception as e:
                command_failed[0] = True
                err_text = "Task cancelled at a safe checkpoint." if cancel_event.is_set() else f"Notice: {e}"
                self.bridge.chat_message_received.emit(err_text, False)
                if not cancel_event.is_set():
                    self.tts.speak(err_text)
                self._delayed_status("Idle", "happy", 2.5)
                command_done.set()
                self.task_center.finish(task_id, err_text, failed=not cancel_event.is_set())
            finally:
                if not asynchronous[0]:
                    command_done.set()
                    self.task_center.finish(
                        task_id,
                        "Cancelled" if cancel_event.is_set() else "Completed",
                        failed=command_failed[0] and not cancel_event.is_set(),
                    )

        threading.Thread(target=runner, name="nixi-command", daemon=True).start()
        def command_watchdog():
            if not command_done.wait(8.0) and command_generation == getattr(self, "_status_generation", 0):
                self.bridge.status_changed.emit(f"Still working: {cmd[:24]}", "thinking")
        threading.Thread(target=command_watchdog, name="nixi-command-watchdog", daemon=True).start()

    def _on_timer_done(self, label: str):
        msg = f"⏰ Time is up! ({label})"
        self.bridge.status_changed.emit(msg, "happy")
        self.bridge.chat_message_received.emit(msg, False)
        self.tts.speak(f"Time is up! Your {label} has finished.")
        self._delayed_status("Idle", "happy", 5.0)

    def _handle_screen_action(self, goal: str):
        """Execute autonomous computer & browser actions on the user's screen with high speed."""
        self.tts.stop()
        self.bridge.status_changed.emit("Executing...", "thinking")
        self.island.is_executing = True

        # Immediate voice feedback then and there!
        self.tts.speak("Executing now.", interrupt_previous=True)

        # Smoothly collapse island so the browser form is completely unobstructed
        self.island.collapse()

        def worker():
            try:
                # Minimal wait for window redraw
                time.sleep(0.06)
                img_bytes = self.screen_reader.capture_screen()
                if not self.browser_agent:
                    raise RuntimeError("Browser automation is unavailable on this platform.")
                summary = self.browser_agent.execute_screen_goal(goal, img_bytes)
                
                # Expand island and display confirmation immediately
                self.bridge.expand_island_signal.emit()
                self.bridge.chat_message_received.emit(f"✦ {summary}", False)
                self.bridge.status_changed.emit("Complete", "happy")
                self.tts.speak(summary)
            except Exception as e:
                self.bridge.expand_island_signal.emit()
                self.bridge.chat_message_received.emit(f"Action error: {str(e)}", False)
            finally:
                self.island.is_executing = False
                self._delayed_status("Idle", "happy", 2.5)

        threading.Thread(target=worker, daemon=True).start()

    def _handle_screen_vision(self, prompt: str = ""):
        """Take screenshot and send to Vision LLM with live direct perception."""
        self.tts.stop()
        self.bridge.status_changed.emit("Analyzing screen...", "thinking")
        self.tts.speak("Checking screen.", interrupt_previous=True)
        
        # Collapse so island is not in screenshot
        self.island.collapse()

        def worker():
            try:
                time.sleep(0.06)
                img_bytes = self.screen_reader.capture_screen()
                p = prompt if prompt else "Describe what is on my screen in 1-2 concise sentences."
                analysis = self.llm.analyze_screen(img_bytes, prompt=p, max_tokens=800)
                
                self.bridge.expand_island_signal.emit()
                self.bridge.chat_message_received.emit(analysis, False)
                self.bridge.status_changed.emit("Done", "happy")
                first_sentence = analysis.split(".")[0] + "." if "." in analysis else analysis
                self.tts.speak(first_sentence)
            except Exception as e:
                self.bridge.expand_island_signal.emit()
                self.bridge.chat_message_received.emit(f"Vision error: {str(e)}", False)
            finally:
                self._delayed_status("Idle", "happy", 2.5)

        threading.Thread(target=worker, daemon=True).start()

    def _is_visual_query(self, text: str) -> bool:
        lower = text.lower()
        triggers = (
            "screen", "look at", "see", "what is this", "what's this", "what am i looking at",
            "what do you see", "can you see", "visible", "on my screen", "read this",
            "summarize this", "debug this", "extract", "table", "diagram", "chart",
            "infographic", "flowchart", "architecture", "what window", "active window"
        )
        return any(trig in lower for trig in triggers)

    def _ask_llm(self, query: str, finished_event: threading.Event | None = None, task_id: str | None = None):
        """Stream model response with live progress and a bounded wait/fallback."""
        request_generation = getattr(self, "_status_generation", 0)
        cancel_event = self.task_center.cancel_event(task_id) if task_id else None
        response_started = threading.Event()
        self.bridge.status_changed.emit("Connecting...", "thinking")
        if task_id:
            self.task_center.update(task_id, "Waiting for response", progress=25)
        self.tts.stop()

        # Check if live screen vision should be included (Always-On mode OR visual intent)
        # Privacy: vision is opt-in via Settings; respect VisionGuard
        guard_ok = self.vision_guard.check(explicit=self._is_visual_query(query))
        include_screen = bool(guard_ok) or self._is_visual_query(query)
        if not guard_ok and not self._is_visual_query(query):
            print(f"[Privacy] Vision blocked: {guard_ok.reason}")
        img_bytes = None
        if include_screen:
            try:
                img_bytes = self.screen_reader.capture_screen(max_dimension=900)
            except Exception:
                img_bytes = None

        if img_bytes:
            b64_img = base64.b64encode(img_bytes).decode("utf-8")
            user_turn_content = [
                {"type": "text", "text": query},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
            ]
        else:
            user_turn_content = query

        self.conversation_history.append({"role": "user", "content": query})
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]

        # Inject persistent memory facts (user profile, preferences, projects)
        mem_prompt = self.memory.get_system_context_prompt()
        stream_messages = []
        if mem_prompt:
            stream_messages.append({"role": "system", "content": mem_prompt})

        # Add history text (without obsolete images to preserve performance)
        for h in self.conversation_history[:-1]:
            stream_messages.append(h)

        # Current turn with live image context
        stream_messages.append({"role": "user", "content": user_turn_content})

        def worker():
            collected = []
            first_chunk = True
            failed = False
            # Concurrent sentence streamer feeds voice while text streams.
            streamer = SentenceStreamer(self.tts, max_speech_sentences=50)
            try:
                for chunk in self.llm.chat_stream(stream_messages):
                    if cancel_event and cancel_event.is_set():
                        self.tts.stop()
                        break
                    collected.append(chunk)
                    if first_chunk:
                        first_chunk = False
                        response_started.set()
                        if task_id:
                            self.task_center.update(task_id, "Receiving response", progress=55)
                        self.bridge.status_changed.emit("Answering...", "thinking")
                    self.bridge.chat_stream_update.emit("".join(collected))
                    streamer.feed(chunk)

                was_cancelled = bool(cancel_event and cancel_event.is_set())
                full_reply = "".join(collected).strip()
                if was_cancelled:
                    self.tts.stop()
                    if collected:
                        self.bridge.chat_stream_update.emit(full_reply + "\n\n[Cancelled]")
                    else:
                        self.bridge.chat_message_received.emit("Task cancelled.", False)
                    self.bridge.status_changed.emit("Cancelled", "happy")
                else:
                    streamer.finish()
                    full_reply = full_reply or "I didn't receive a response from the model."
                    self.conversation_history.append({"role": "assistant", "content": full_reply})
                    try:
                        self.memory.add_message("assistant", full_reply)
                    except Exception:
                        pass
                    self.bridge.status_changed.emit("Done", "happy")
                if task_id:
                    self.task_center.finish(task_id, "Cancelled" if was_cancelled else (full_reply or "No response"))

            except Exception as e:
                failed = True
                err_text = str(e)
                fallback_msg = "The model request was interrupted." if cancel_event and cancel_event.is_set() else f"Notice: {err_text}"
                self.bridge.chat_message_received.emit(fallback_msg, False)
                if not (cancel_event and cancel_event.is_set()):
                    self.tts.speak(fallback_msg)
                if task_id:
                    self.task_center.finish(task_id, fallback_msg, failed=True)
            finally:
                response_started.set()
                if task_id and failed:
                    self.task_center.finish(task_id, "Request failed", failed=True)
                if finished_event is not None:
                    finished_event.set()
                self._delayed_status("Idle", "happy", 2.5)

        def progress_watchdog():
            if not response_started.wait(5.0) and request_generation == getattr(self, "_status_generation", 0):
                self.bridge.status_changed.emit("Still waiting for the model...", "thinking")
        threading.Thread(target=progress_watchdog, name="nixi-response-watchdog", daemon=True).start()
        threading.Thread(target=worker, name="nixi-llm", daemon=True).start()

    # ── New helpers ─────────────────────────────────────────────────
    def _persist_chat_message(self, text: str, is_user: bool) -> None:
        try:
            self.memory.add_message("user" if is_user else "assistant", text)
        except Exception:
            pass

    def _vision_indicator(self, active: bool, title: str) -> None:
        try:
            if active:
                self.bridge.status_changed.emit("Screen capture", "thinking")
            self.island.set_vision_active(active)
        except Exception:
            pass

    def _confirm_action(self, action: str, risk, args) -> bool:
        """Ask on the Qt/UI thread; never create modal Qt widgets from workers."""
        event = threading.Event()
        request = {"action": action, "risk": risk, "args": args, "event": event, "approved": False}
        try:
            self.bridge.confirm_action_signal.emit(request)
            return bool(event.wait(timeout=60.0) and request["approved"])
        except Exception:
            return False

    def _show_confirmation_dialog(self, request: dict) -> None:
        """Runs on Qt thread and unblocks the requesting worker after user decision."""
        try:
            from PyQt6.QtWidgets import QMessageBox
            risk = request.get("risk")
            risk_name = getattr(risk, "name", str(risk))
            box = QMessageBox(self.island)
            box.setWindowTitle("Confirm system action")
            box.setIcon(QMessageBox.Icon.Warning)
            box.setText(f"Allow '{request.get('action')}'?\nRisk: {risk_name}\nDetails: {request.get('args')}")
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            request["approved"] = box.exec() == QMessageBox.StandardButton.Yes
        except Exception:
            request["approved"] = False
        finally:
            request["event"].set()

    def _api_chat(self, message: str) -> str:
        try:
            return self.llm.chat([{"role": "user", "content": message}])
        except Exception as exc:
            return f"Error: {exc}"

    def _api_command(self, tool: str, args: dict) -> str:
        # Route through GodModeAgent for now
        handled, result = self.god_agent.process_command(f"{tool} {args}")
        return result if handled else f"Unknown tool: {tool}"

    def _api_tools(self) -> list:
        return [{"name": n, "description": s.get("description","")} for n, s in getattr(self.god_agent, 'tools', {}).items()] or ["system", "web", "files"]

    def _setup_tray(self) -> None:
        try:
            from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
            from PyQt6.QtGui import QIcon, QAction
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return
            self._tray = QSystemTrayIcon(self.island)
            menu = QMenu()
            show_act = QAction("Show Nixi", menu)
            show_act.triggered.connect(self.island.show)
            menu.addAction(show_act)
            expand_act = QAction("Expand", menu)
            expand_act.triggered.connect(self.island.expand)
            menu.addAction(expand_act)
            quit_act = QAction("Quit Nixi", menu)
            quit_act.triggered.connect(self._quit_app)
            menu.addAction(quit_act)
            self._tray.setContextMenu(menu)
            self._tray.show()
        except Exception:
            pass

    def _quit_app(self) -> None:
        try:
            self.audio.stop()
        except Exception:
            pass
        try:
            if getattr(self, "browser", None):
                self.browser.close()
        except Exception:
            pass
        for d in (getattr(self, 'battery_daemon', None), getattr(self, 'clipboard_daemon', None), getattr(self, 'briefing_daemon', None)):
            try:
                if d: d.stop()
            except Exception:
                pass
        try:
            if getattr(self, 'api_server', None): self.api_server.stop()
        except Exception:
            pass
        self.app.quit()

    def _on_quit(self) -> None:
        self._quit_app()

    def _open_palette(self) -> None:
        try:
            from nixi.ui.palette import CommandPalette
            actions = [
                {"label": "Open Settings", "description": "Configure provider, voice, privacy", "action": "settings"},
                {"label": "Toggle Vision", "description": "Enable/disable screen vision", "action": "vision"},
                {"label": "Show Diagnostics", "description": "Health checks and capabilities", "action": "doctor"},
                {"label": "Knowledge: Search", "description": "Search your indexed documents", "action": "knowledge"},
                {"label": "Undo Last Action", "description": "Revert last file operation", "action": "undo"},
            ]
            def on_pick(a):
                if a.get("action") == "settings": self._open_settings()
                elif a.get("action") == "vision": self.vision_guard.set_enabled(not self.config.vision_enabled)
                elif a.get("action") == "undo": self.undo_manager.undo_last()
            pal = CommandPalette(actions=actions, on_selected=on_pick, parent=self.island)
            pal.exec()
        except Exception as exc:
            print(f"[Palette] {exc}")

    def _open_settings(self) -> None:
        try:
            from nixi.ui.settings_dialog import SettingsDialog
            dlg = SettingsDialog(config=self.config, llm=self.llm, parent=self.island)
            dlg.exec()
        except Exception as exc:
            print(f"[Settings] {exc}")

    def run(self):
        self.island.show()
        self.audio.start()
        sys.exit(self.app.exec())


if __name__ == "__main__":
    app = NixiApp()
    app.run()
