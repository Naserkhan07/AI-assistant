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
from nixi.audio.audio_capture import AudioCapture
from nixi.audio.stt import SpeechTranscriber
from nixi.audio.tts import NixiTTS, SentenceStreamer
from nixi.audio.wake_word import WakeWordDetector


class Bridge(QObject):
    """Bridge for cross-thread communication to Qt UI thread."""
    status_changed = pyqtSignal(str, str)
    audio_level_changed = pyqtSignal(float)
    chat_message_received = pyqtSignal(str, bool)
    dictate_state_changed = pyqtSignal(bool)


class NixiApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Nixi")
        self.app.setQuitOnLastWindowClosed(False)

        self.bridge = Bridge()

        # Core engines
        self.llm = NixiLLMClient()
        self.dictation = DictationManager()
        self.screen_reader = ScreenReader()
        self.app_launcher = AppLauncher()
        self.timer_mgr = TimerManager()
        self.god_agent = GodModeAgent(self.llm)
        self.stt = SpeechTranscriber()
        self.tts = NixiTTS()
        self.wake_detector = WakeWordDetector()

        # UI: Dynamic Island with cute eyes and hover expansion
        self.island = NixiDynamicIsland()
        self._wire_signals()

        # Audio capture with speaker echo suppression
        self.audio = AudioCapture(
            on_speech_detected=self._on_speech_start,
            on_speech_finished=self._on_speech_done,
            on_audio_level=lambda lvl: self.bridge.audio_level_changed.emit(lvl),
            is_tts_speaking=lambda: self.tts.is_speaking
        )

        # Chat history memory for LLM
        self.conversation_history = []

        # Windows Global Hotkey Listener (optional background thread)
        self._start_hotkey_listener()

    def _wire_signals(self):
        # Bridge to UI
        self.bridge.status_changed.connect(self.island.set_status)
        self.bridge.audio_level_changed.connect(self.island.set_audio_level)
        self.bridge.chat_message_received.connect(lambda msg, is_user: self.island.set_response(msg))

        # Dynamic Island UI signals to actions
        self.island.send_query_signal.connect(self._execute_command_text)
        self.island.dictate_toggled_signal.connect(self._toggle_dictation)
        self.island.screen_vision_signal.connect(self._handle_screen_vision)

    def _start_hotkey_listener(self):
        """Register keyboard shortcuts using keyboard if available."""
        def listen():
            try:
                import keyboard
                keyboard.add_hotkey('F8', lambda: self.island.mic_btn.toggle())
                keyboard.add_hotkey('F9', lambda: self.island.collapse() if self.island.is_expanded else self.island.expand())
                keyboard.add_hotkey('F10', self._handle_screen_vision)
            except Exception:
                pass
        t = threading.Thread(target=listen, daemon=True)
        t.start()

    def _toggle_dictation(self, enabled: bool):
        self.dictation.set_active(enabled)
        if enabled:
            self.tts.speak("Dictation on")
            self.island.set_status("Dictating...", "listening")
        else:
            self.tts.speak("Dictation off")
            self.island.set_status("Idle", "happy")

    def _on_speech_start(self):
        if self.dictation.is_active:
            self.bridge.status_changed.emit("Dictating...", "listening")
        else:
            self.bridge.status_changed.emit("Listening...", "listening")

    def _on_speech_done(self, audio_data):
        """Transcribe and route audio speech."""
        text = self.stt.transcribe_audio_samples(audio_data)
        if not text:
            if not self.dictation.is_active:
                self.bridge.status_changed.emit("Idle", "happy")
            return

        # Case 1: Dictation mode is active -> inject directly into focused app!
        if self.dictation.is_active:
            if "stop dictation" in text.lower():
                self.island.mic_btn.setChecked(False)
                return
            self.dictation.inject_text(text)
            self.bridge.status_changed.emit(f"Typed: {text[:14]}", "listening")
            return

        # Case 2: Standard assistant wake word check
        is_wake, command = self.wake_detector.check(text)
        if is_wake or self.island.is_expanded:
            self.bridge.status_changed.emit("Thinking...", "thinking")
            self._execute_command_text(command if command else text)
        else:
            self.bridge.status_changed.emit("Idle", "happy")

    def _execute_command_text(self, cmd: str):
        """Analyze user command: match built-in local actions, god-mode operations, or LLM."""
        if not cmd:
            self.bridge.status_changed.emit("Idle", "happy")
            return

        # Stop any ongoing speech immediately when a new command arrives
        self.tts.stop()

        lower = cmd.lower().strip()

        # 1. Dictation toggle
        if "start dictation" in lower or "dictate" == lower:
            self.island.mic_btn.setChecked(True)
            return
        elif "stop dictation" in lower:
            self.island.mic_btn.setChecked(False)
            return

        # 2. Timer / Reminder: e.g. "set timer for 5 minutes", "timer 30 seconds"
        timer_match = re.search(r"(?:timer|remind me)(?:\s+for)?\s+(\d+)\s*(min|minute|sec|second|hour)s?", lower)
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
            QTimer.singleShot(2500, lambda: self.bridge.status_changed.emit("Idle", "happy"))
            return

        # 3. Dedicated App Launcher
        open_match = re.search(r"^(?:open|launch|start)\s+([a-zA-Z0-9\s]+)$", lower)
        if open_match and not ("http" in lower or ".com" in lower or "web" in lower or "youtube" in lower or "github" in lower):
            app_target = open_match.group(1).strip()
            ok, msg = self.app_launcher.launch(app_target)
            if ok:
                self.bridge.status_changed.emit(msg, "happy")
                self.bridge.chat_message_received.emit(msg, False)
                self.tts.speak(msg)
                QTimer.singleShot(2500, lambda: self.bridge.status_changed.emit("Idle", "happy"))
                return

        # 4. God-Mode Agent (System, Media, Windows, Shell, Web Search, Screen Form Automation, Files)
        handled, result = self.god_agent.process_command(cmd, on_voice_feedback=lambda msg: self.tts.speak(msg))
        if handled:
            self.bridge.status_changed.emit("Done", "happy")
            self.bridge.chat_message_received.emit(result, False)
            self.tts.speak(result)
            QTimer.singleShot(2500, lambda: self.bridge.status_changed.emit("Idle", "happy"))
            return

        # 5. General LLM Query with concurrent sentence-by-sentence voice streaming
        self._ask_llm(cmd)

    def _on_timer_done(self, label: str):
        msg = f"⏰ Time is up! ({label})"
        self.bridge.status_changed.emit(msg, "happy")
        self.bridge.chat_message_received.emit(msg, False)
        self.tts.speak(f"Time is up! Your {label} has finished.")
        QTimer.singleShot(5000, lambda: self.bridge.status_changed.emit("Idle", "happy"))

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
                summary = self.browser_agent.execute_screen_goal(goal, img_bytes)
                
                # Expand island and display confirmation immediately
                QTimer.singleShot(50, self.island.expand)
                self.bridge.chat_message_received.emit(f"✦ {summary}", False)
                self.bridge.status_changed.emit("Complete", "happy")
                self.tts.speak(summary)
            except Exception as e:
                QTimer.singleShot(50, self.island.expand)
                self.bridge.chat_message_received.emit(f"Action error: {str(e)}", False)
            finally:
                self.island.is_executing = False
                QTimer.singleShot(2500, lambda: self.bridge.status_changed.emit("Idle", "happy"))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_screen_vision(self):
        """Take screenshot and send to Vision LLM."""
        self.tts.stop()
        self.bridge.status_changed.emit("Analyzing screen...", "thinking")
        self.tts.speak("Checking screen.", interrupt_previous=True)
        
        # Collapse so island is not in screenshot
        self.island.collapse()

        def worker():
            try:
                time.sleep(0.06)
                img_bytes = self.screen_reader.capture_screen()
                analysis = self.llm.analyze_screen(img_bytes)
                
                QTimer.singleShot(50, self.island.expand)
                self.bridge.chat_message_received.emit(analysis, False)
                self.bridge.status_changed.emit("Done", "happy")
                first_sentence = analysis.split(".")[0] + "." if "." in analysis else analysis
                self.tts.speak(first_sentence)
            except Exception as e:
                QTimer.singleShot(50, self.island.expand)
                self.bridge.chat_message_received.emit(f"Vision error: {str(e)}", False)
            finally:
                QTimer.singleShot(2500, lambda: self.bridge.status_changed.emit("Idle", "happy"))

        threading.Thread(target=worker, daemon=True).start()

    def _ask_llm(self, query: str):
        """Stream message from FreeLLMAPI in real time with concurrent sentence-by-sentence voice output."""
        self.tts.stop()
        self.conversation_history.append({"role": "user", "content": query})
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]

        def worker():
            collected = []
            first_chunk = True
            # Concurrent sentence streamer feeds voice *then and there* while text streams!
            streamer = SentenceStreamer(self.tts, max_speech_sentences=50)
            try:
                for chunk in self.llm.chat_stream(self.conversation_history):
                    collected.append(chunk)
                    if first_chunk:
                        first_chunk = False
                        self.bridge.status_changed.emit("Answering...", "thinking")
                    # Real-time token streaming into the UI!
                    self.bridge.chat_message_received.emit("".join(collected), False)
                    # Feed chunk into sentence audio streamer immediately!
                    streamer.feed(chunk)

                # Flush any remaining text in sentence buffer to voice
                streamer.finish()

                full_reply = "".join(collected).strip()
                if not full_reply:
                    full_reply = "I didn't receive a response from the model."

                self.conversation_history.append({"role": "assistant", "content": full_reply})
                self.bridge.status_changed.emit("Idle", "happy")

            except Exception as e:
                err_text = str(e)
                if "502" in err_text or "Bad Gateway" in err_text:
                    fallback_msg = "Upstream provider is momentarily busy. Retrying in background..."
                else:
                    fallback_msg = f"Notice: {err_text}"
                self.bridge.chat_message_received.emit(fallback_msg, False)
                self.tts.speak(fallback_msg)
            finally:
                QTimer.singleShot(2500, lambda: self.bridge.status_changed.emit("Idle", "happy"))

        threading.Thread(target=worker, daemon=True).start()

    def run(self):
        self.island.show()
        self.audio.start()
        sys.exit(self.app.exec())


if __name__ == "__main__":
    app = NixiApp()
    app.run()
