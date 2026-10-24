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
        energy_threshold: float = 0.015,
        silence_duration_sec: float = 0.8,
        on_speech_detected: Optional[Callable[[], None]] = None,
        on_speech_finished: Optional[Callable[[np.ndarray], None]] = None,
        on_audio_level: Optional[Callable[[float], None]] = None,
        is_tts_speaking: Optional[Callable[[], bool]] = None,
    ):
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * (chunk_duration_ms / 1000.0))
        self.energy_threshold = energy_threshold
        self.silence_duration_sec = silence_duration_sec
        self.on_speech_detected = on_speech_detected
        self.on_speech_finished = on_speech_finished
        self.on_audio_level = on_audio_level
        self.is_tts_speaking = is_tts_speaking

        self.is_running = False
        self.stream = None
        self.speech_buffer = []
        self.is_speaking = False
        self.silence_chunks = 0
        self.max_silence_chunks = int(silence_duration_sec / (chunk_duration_ms / 1000.0))
        self.echo_cooldown_until = 0.0

    def start(self):
        if not HAS_SD:
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
            self.echo_cooldown_until = time.time() + 0.55
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

        if self.on_audio_level:
            # Normalized level roughly between 0.0 and 1.0
            norm_level = min(1.0, rms * 15.0)
            self.on_audio_level(norm_level)

        if rms > self.energy_threshold:
            if not self.is_speaking:
                self.is_speaking = True
                self.speech_buffer = []
                if self.on_speech_detected:
                    self.on_speech_detected()

            self.speech_buffer.append(chunk.copy())
            self.silence_chunks = 0
        else:
            if self.is_speaking:
                self.speech_buffer.append(chunk.copy())
                self.silence_chunks += 1
                if self.silence_chunks >= self.max_silence_chunks:
                    # Speech segment ended
                    self.is_speaking = False
                    if self.speech_buffer:
                        full_audio = np.concatenate(self.speech_buffer)
                        self.speech_buffer = []
                        if self.on_speech_finished:
                            threading.Thread(target=self.on_speech_finished, args=(full_audio,), daemon=True).start()
