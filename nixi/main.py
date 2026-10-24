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

# Autonomous Agent Pillars
from nixi.agent.memory import AgentMemory
from nixi.agent.react_planner import ReActPlanner, is_complex_agent_goal
from nixi.agent.background_daemons import BatteryGuardianDaemon, ClipboardWatcherDaemon, DailyBriefingDaemon
from nixi.agent.vision_copilot import VisionCopilot


class Bridge(QObject):
    """Bridge for cross-thread communication to Qt UI thread."""
    status_changed = pyqtSignal(str, str)
    audio_level_changed = pyqtSignal(float)
    chat_message_received = pyqtSignal(str, bool)
    dictate_state_changed = pyqtSignal(bool)
    expand_island_signal = pyqtSignal()
    collapse_island_signal = pyqtSignal()
    command_signal = pyqtSignal(str)
    clipboard_chip_signal = pyqtSignal(dict)
    battery_warning_signal = pyqtSignal(str)


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

        # Agent Pillars: Persistent Memory, ReAct Planner, Vision Co-Pilot
        self.memory = AgentMemory()
        self.react_planner = ReActPlanner(self.llm, self.memory)
        self.vision_copilot = VisionCopilot(self.llm, self.screen_reader)

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
        self._wire_signals()

        # Start Proactive Background Daemons
        self.battery_daemon.start()
        self.clipboard_daemon.start()
        self.briefing_daemon.start()

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

    def _delayed_status(self, text: str = "Idle", mood: str = "happy", delay: float = 2.5):
        """Thread-safe delayed status reset without QTimer cross-thread warnings."""
        def run():
            time.sleep(delay)
            self.bridge.status_changed.emit(text, mood)
        threading.Thread(target=run, daemon=True).start()

    def _wire_signals(self):
        # Bridge to UI
        self.bridge.status_changed.connect(self.island.set_status)
        self.bridge.audio_level_changed.connect(self.island.set_audio_level)
        self.bridge.chat_message_received.connect(lambda msg, is_user: self.island.set_response(msg))
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
            except Exception:
                pass
        t = threading.Thread(target=listen, daemon=True)
        t.start()

    def _on_screen_always_toggled(self, enabled: bool):
        state = "on" if enabled else "off"
        self.tts.speak(f"Screen vision {state}")

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
            if not self.dictation.is_active and not self.tts.is_speaking:
                self.bridge.status_changed.emit("Idle", "happy")
            return

        print(f"[Nixi Voice] Heard: '{text}'")

        # Acoustic Echo & Self-Interruption Guard:
        # If assistant is currently speaking or synthesizing, only allow explicit stop commands
        if self.tts.is_speaking:
            interrupt_words = {"stop", "quiet", "shut up", "cancel", "pause", "halt"}
            lower_txt = text.lower().strip()
            if any(w in lower_txt for w in interrupt_words):
                self.tts.stop()
                self.bridge.status_changed.emit("Stopped", "happy")
                self._delayed_status("Idle", "happy", 1.5)
            # Discard any noise/echo transcribed while Nixi is speaking
            return

        # Case 1: Dictation mode is active -> inject directly into focused app!
        if self.dictation.is_active:
            if "stop dictation" in text.lower():
                self.island.mic_btn.setChecked(False)
                return
            self.dictation.inject_text(text)
            self.bridge.status_changed.emit(f"Typed: {text[:14]}", "listening")
            return

        # Case 2: Standard assistant speech routing
        wake_enabled = os.getenv("WAKE_WORD_ENABLED", "false").lower() == "true"
        is_wake, command = self.wake_detector.check(text)

        # Allow command if: wake word is disabled, or wake word was spoken, or island is expanded
        should_process = (not wake_enabled) or is_wake or self.island.is_expanded

        if should_process:
            actual_cmd = (command if is_wake and command else text).strip()
            print(f"[Nixi Voice] Executing command: '{actual_cmd}'")
            self.bridge.status_changed.emit("Thinking...", "thinking")
            # Show the user's voice message in the chat display so they see it was heard
            self.bridge.chat_message_received.emit(f"🗣️ {actual_cmd}", True)
            self.bridge.command_signal.emit(actual_cmd)
        else:
            print(f"[Nixi Voice] Ignored (wake word required): '{text}'")
            self.bridge.status_changed.emit("Idle", "happy")

    def _execute_command_text(self, cmd: str):
        """Analyze user command asynchronously without freezing the UI thread."""
        if not cmd or not cmd.strip():
            self.bridge.status_changed.emit("Idle", "happy")
            return

        cmd = cmd.strip()

        def runner():
            try:
                self.tts.stop()
                lower = cmd.lower().strip()

                # Clean conversational politeness prefixes
                clean = re.sub(r"^(?:please\s+|can\s+you\s+|could\s+you\s+|would\s+you\s+|hey\s+nixi\s+|nixi\s+)", "", lower).strip()

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
                        self.bridge.status_changed.emit(f"Step {curr}/{total}: {step_name[:18]}", "thinking")
                        self.tts.speak(f"Executing step {curr} of {total}: {step_name}")

                    summary = self.react_planner.plan_and_execute(clean, on_step_progress=on_step_progress)
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

                # 5. General LLM Query with concurrent sentence-by-sentence voice streaming
                self._ask_llm(cmd)
            except Exception as e:
                err_text = f"Notice: {e}"
                self.bridge.chat_message_received.emit(err_text, False)
                self.tts.speak(err_text)
                self._delayed_status("Idle", "happy", 2.5)

        threading.Thread(target=runner, daemon=True).start()

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

    def _ask_llm(self, query: str):
        """Stream message from FreeLLMAPI in real time with concurrent sentence-by-sentence voice output and live screen vision."""
        self.tts.stop()

        # Check if live screen vision should be included (Always-On mode OR visual intent)
        include_screen = getattr(self.island, "is_screen_always_on", True) or self._is_visual_query(query)
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
            # Concurrent sentence streamer feeds voice *then and there* while text streams!
            streamer = SentenceStreamer(self.tts, max_speech_sentences=50)
            try:
                for chunk in self.llm.chat_stream(stream_messages):
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
                self._delayed_status("Idle", "happy", 2.5)

        threading.Thread(target=worker, daemon=True).start()

    def run(self):
        self.island.show()
        self.audio.start()
        sys.exit(self.app.exec())


if __name__ == "__main__":
    app = NixiApp()
    app.run()
