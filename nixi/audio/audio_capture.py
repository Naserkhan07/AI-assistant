"""
Nixi Audio Capture & Voice Activity Detection (VAD)
Continuously listens to microphone, detects speech start/end, and emits speech buffers.
"""
from __future__ import annotations

import time
import threading
from typing import Callable, Optional
import numpy as np

try:
    import sounddevice as sd
    HAS_SD = True
except ImportError:
    HAS_SD = False

class AudioCapture:
    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_duration_ms: int = 30,
        energy_threshold: float = 0.005,
        silence_duration_sec: float = 0.7,
        on_speech_detected: Optional[Callable[[], None]] = None,
        on_speech_finished: Optional[Callable[[np.ndarray], None]] = None,
        on_audio_level: Optional[Callable[[float], None]] = None,
        is_tts_speaking: Optional[Callable[[], bool]] = None,
    ):
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * (chunk_duration_ms / 1000.0))
        self.energy_threshold = energy_threshold
        self.ambient_energy = 0.0025
        self.silence_duration_sec = silence_duration_sec
        self.on_speech_detected = on_speech_detected
        self.on_speech_finished = on_speech_finished
        self.on_audio_level = on_audio_level
        self.is_tts_speaking = is_tts_speaking

        self.is_running = False
        self.stream = None
        self.speech_buffer = []
        self.pre_buffer = []  # 4 chunks (~120ms) to preserve initial consonants
        self.max_pre_chunks = 4
        self.is_speaking = False
        self.silence_chunks = 0
        self.max_silence_chunks = int(silence_duration_sec / (chunk_duration_ms / 1000.0))
        self.echo_cooldown_until = 0.0

    def start(self):
        if not HAS_SD:
            print("[Nixi Audio] sounddevice is not available. Microphone disabled.")
            return
        self.is_running = True
        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=self.chunk_size,
                callback=self._audio_callback
            )
            self.stream.start()
            print("[+] Nixi Voice Listener online and actively listening for commands.")
        except Exception as e:
            print(f"[Nixi Audio] Error starting audio stream: {e}")

    def stop(self):
        self.is_running = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    def _audio_callback(self, indata, frames, time_info, status):
        if not self.is_running:
            return

        # Acoustic Echo Prevention: Ignore mic feedback when Nixi is speaking
        tts_active = self.is_tts_speaking() if self.is_tts_speaking else False
        if tts_active:
            self.echo_cooldown_until = time.time() + 0.6
            self.is_speaking = False
            self.speech_buffer = []
            self.silence_chunks = 0
            return

        if time.time() < self.echo_cooldown_until:
            self.is_speaking = False
            self.speech_buffer = []
            self.silence_chunks = 0
            return

        chunk = indata[:, 0]
        # RMS energy
        rms = float(np.sqrt(np.mean(chunk**2)))

        # Dynamic noise floor adaptation
        if not self.is_speaking:
            self.ambient_energy = 0.98 * self.ambient_energy + 0.02 * rms
            trigger_threshold = max(self.energy_threshold, self.ambient_energy * 1.8)
        else:
            trigger_threshold = max(self.energy_threshold * 0.75, self.ambient_energy * 1.35)

        if self.on_audio_level:
            # Scaled normalized level between 0.0 and 1.0 for eye reaction
            norm_level = min(1.0, max(0.0, (rms - self.ambient_energy * 0.8) * 35.0))
            self.on_audio_level(norm_level)

        if rms > trigger_threshold:
            if not self.is_speaking:
                self.is_speaking = True
                # Include pre-buffer so starting syllables are intact
                self.speech_buffer = list(self.pre_buffer) + [chunk.copy()]
                if self.on_speech_detected:
                    self.on_speech_detected()
            else:
                self.speech_buffer.append(chunk.copy())

            self.silence_chunks = 0
        else:
            if self.is_speaking:
                self.speech_buffer.append(chunk.copy())
                self.silence_chunks += 1
                if self.silence_chunks >= self.max_silence_chunks:
                    # Speech segment ended
                    self.is_speaking = False
                    # Minimum valid speech length: at least 8 chunks (~240ms) to discard blips/coughs
                    if len(self.speech_buffer) >= 8:
                        full_audio = np.concatenate(self.speech_buffer)
                        self.speech_buffer = []
                        if self.on_speech_finished:
                            threading.Thread(target=self.on_speech_finished, args=(full_audio,), daemon=True).start()
                    else:
                        self.speech_buffer = []
            else:
                # Keep rolling pre-buffer while idle
                self.pre_buffer.append(chunk.copy())
                if len(self.pre_buffer) > self.max_pre_chunks:
                    self.pre_buffer.pop(0)
