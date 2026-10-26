"""
Nixi Speech-to-Text (STT) Engine
Supports local faster-whisper, speech_recognition, and Windows native voice recognition.
"""
from __future__ import annotations

import io
import wave
import tempfile
import os
import threading
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
    def __init__(self, model_size: str = "tiny.en", preload: bool = False):
        self.whisper_model = None
        self.model_size = model_size
        self._model_loading = False
        self._warm = False
        # Never block GUI startup while Whisper loads/downloads; warm it in background.
        if HAS_FASTER_WHISPER:
            self._ensure_model_async()

        self.sr_recognizer = None
        if HAS_SR:
            try:
                self.sr_recognizer = sr.Recognizer()
                try:
                    self.sr_recognizer.energy_threshold = 300
                    self.sr_recognizer.dynamic_energy_threshold = True
                except Exception:
                    pass
            except Exception:
                pass

    def _ensure_model_async(self):
        if self._model_loading or self.whisper_model:
            return
        self._model_loading = True
        import threading
        def _load():
            try:
                import time
                start = time.time()
                self.whisper_model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
                self._warm = True
                print(f"[STT] whisper {self.model_size} warmed in {time.time()-start:.1f}s")
            except Exception as e:
                print(f"[STT] warm failed: {e}")
            finally:
                self._model_loading = False
        threading.Thread(target=_load, daemon=True).start()

    def warmup(self):
        self._ensure_model_async()

    def transcribe_audio_samples(self, audio_data: np.ndarray, sample_rate: int = 16000, language: str | None = None, on_partial=None, timeout: float = 6.0) -> str:
        """Transcribe a numpy float32/int16 array of audio samples — fast path with timeout."""
        import time as _time
        if len(audio_data) == 0:
            return ""
        # quick reject: too short or silence
        try:
            import numpy as _np
            if len(audio_data) < int(sample_rate * 0.35):  # <350ms ignore
                return ""
            rms = float(_np.sqrt(_np.mean(audio_data.astype(_np.float32)**2))) if len(audio_data) else 0
            if rms < 0.008:  # silence
                return ""
        except Exception:
            pass

        # ensure model is loading if needed
        if not self.whisper_model and HAS_FASTER_WHISPER and not self._warm:
            self._ensure_model_async()

        # Method 1: faster-whisper (Direct numpy support) — with timeout
        if self.whisper_model:
            try:
                # Ensure float32 normalized [-1.0, 1.0]
                if audio_data.dtype != np.float32:
                    audio_float = audio_data.astype(np.float32) / 32768.0
                else:
                    audio_float = audio_data

                # run transcribe with hard timeout to avoid hanging
                result: list[str] = []
                done = threading.Event()
                err_holder: list[Exception] = []
                def _do():
                    try:
                        segs, _ = self.whisper_model.transcribe(audio_float, beam_size=1, language=language, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=300)) if language else self.whisper_model.transcribe(audio_float, beam_size=1, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=300))
                        txt = " ".join([s.text for s in segs]).strip()
                        if txt:
                            result.append(txt)
                    except Exception as e:
                        err_holder.append(e)
                    finally:
                        done.set()
                threading.Thread(target=_do, daemon=True).start()
                if done.wait(timeout=timeout):
                    if result:
                        return result[0]
                else:
                    print(f"[STT] whisper timeout after {timeout}s")
                    return ""
            except Exception:
                pass

        # Method 2: SpeechRecognition via temp WAV — with timeout, skip if whisper already tried and failed quickly
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
                    # google SR with timeout
                    result2: list[str] = []
                    done2 = threading.Event()
                    def _google():
                        try:
                            txt = self.sr_recognizer.recognize_google(audio, language=language or "en-US")
                            if txt:
                                result2.append(txt.strip())
                        except Exception:
                            pass
                        finally:
                            done2.set()
                    threading.Thread(target=_google, daemon=True).start()
                    if done2.wait(timeout=2.5):
                        if result2:
                            return result2[0]
                    else:
                        return ""
                finally:
                    try:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    except Exception:
                        pass
            except Exception:
                pass

        return ""
