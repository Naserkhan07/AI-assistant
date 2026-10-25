"""
Nixi Speech-to-Text (STT) Engine
Supports local faster-whisper, speech_recognition, and Windows native voice recognition.
"""
from __future__ import annotations

import io
import wave
import tempfile
import os
import numpy as np

# Try faster-whisper
HAS_FASTER_WHISPER = False
try:
    from faster_whisper import WhisperModel
    HAS_FASTER_WHISPER = True
except ImportError:
    HAS_FASTER_WHISPER = False

# Try SpeechRecognition
HAS_SR = False
try:
    import speech_recognition as sr
    HAS_SR = True
except ImportError:
    HAS_SR = False


class SpeechTranscriber:
    def __init__(self, model_size: str = "tiny.en"):
        self.whisper_model = None
        if HAS_FASTER_WHISPER:
            try:
                # Load lightweight CPU-optimized local Whisper
                self.whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
            except Exception:
                self.whisper_model = None

        self.sr_recognizer = None
        if HAS_SR:
            try:
                self.sr_recognizer = sr.Recognizer()
            except Exception:
                pass

    def transcribe_audio_samples(self, audio_data: np.ndarray, sample_rate: int = 16000, language: str | None = None, on_partial=None) -> str:
        """Transcribe a numpy float32/int16 array of audio samples."""
        if len(audio_data) == 0:
            return ""

        # Method 1: faster-whisper (Direct numpy support)
        if self.whisper_model:
            try:
                # Ensure float32 normalized [-1.0, 1.0]
                if audio_data.dtype != np.float32:
                    audio_float = audio_data.astype(np.float32) / 32768.0
                else:
                    audio_float = audio_data

                segments, _ = self.whisper_model.transcribe(audio_float, beam_size=1, language=language) if language else self.whisper_model.transcribe(audio_float, beam_size=1)
                text = " ".join([s.text for s in segments]).strip()
                if text:
                    return text
            except Exception:
                pass

        # Method 2: SpeechRecognition via temp WAV
        if HAS_SR and self.sr_recognizer:
            try:
                # Convert to int16 for WAV
                if audio_data.dtype == np.float32:
                    int_data = (audio_data * 32767).astype(np.int16)
                else:
                    int_data = audio_data.astype(np.int16)

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                    temp_path = tf.name

                with wave.open(temp_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(int_data.tobytes())

                try:
                    with sr.AudioFile(temp_path) as source:
                        audio = self.sr_recognizer.record(source)
                    text = self.sr_recognizer.recognize_google(audio)
                    return text.strip()
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            except Exception:
                pass

        return ""
