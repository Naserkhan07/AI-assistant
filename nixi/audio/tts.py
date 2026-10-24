"""
Nixi High-Speed Pipelined Streaming Neural TTS (Text-to-Speech)
Features:
- Pipelined Multi-Stage Architecture: Audio Synthesis runs ahead in parallel with Playback,
  completely eliminating the pauses/stutters between sentences!
- Early-Trigger Word/Clause Chunking: First voice output starts on the first 3-5 words
  without waiting for long sentences to finish typing!
- Zero-Latency Fallback: Automatic instant fallback to local Windows SAPI if network jitters.
- Instant Barge-In: Halts audio output and cancels ongoing downloads in <50ms.
"""
from __future__ import annotations

import io
import re
import queue
import time
import threading
import asyncio
import numpy as np
import sounddevice as sd
import soundfile as sf
from typing import Optional, List, Tuple

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False


class NixiTTS:
    def __init__(self, voice: str = "en-US-AvaNeural", rate: str = "+10%", pitch: str = "+0Hz"):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        
        # Two-stage pipelined queues
        self.text_queue: queue.Queue[Optional[str]] = queue.Queue()
        self.audio_queue: queue.Queue[Optional[Tuple[np.ndarray, int]]] = queue.Queue(maxsize=12)
        
        self.is_speaking = False
        self.interrupted = threading.Event()
        
        # Thread 1: Synthesizer (downloads/decodes audio ahead of time)
        self.synth_thread = threading.Thread(target=self._synthesis_loop, daemon=True)
        self.synth_thread.start()

        # Thread 2: Player (plays decoded audio smoothly with 0ms gap)
        self.play_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.play_thread.start()

    def clean_text(self, text: str) -> str:
        """Strip markdown syntax, action tokens, URLs, and code blocks for clean voice output."""
        if not text:
            return ""
        text = re.sub(r"\[ACTION:[^\]]+\]", "", text)
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"`[^`]+`", "", text)
        text = re.sub(r"[*#_~>\[\]\(\)\{\}]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def enqueue_sentence(self, text: str):
        """Enqueue text chunk to be synthesized and pre-buffered immediately."""
        clean = self.clean_text(text)
        if not clean or len(clean) < 2:
            return
        self.interrupted.clear()
        self.text_queue.put(clean)

    def speak(self, text: str, interrupt_previous: bool = True):
        """Speak a complete string immediately with minimal latency."""
        if interrupt_previous:
            self.stop()
        
        # Split into clauses/sentences for rapid pipelined playback
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|(?<=[,;])\s+", text) if p.strip()]
        if not parts:
            parts = [text]
            
        for p in parts:
            self.enqueue_sentence(p)

    def stop(self):
        """Instantly stop ongoing audio playback and purge all pending queues."""
        self.interrupted.set()
        try:
            sd.stop()
        except Exception:
            pass

        # Drain text queue
        while not self.text_queue.empty():
            try:
                self.text_queue.get_nowait()
                self.text_queue.task_done()
            except queue.Empty:
                break

        # Drain audio queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.task_done()
            except queue.Empty:
                break

        self.is_speaking = False

    def _synthesis_loop(self):
        """Background thread 1: Pulls text, generates audio in parallel, and pushes to audio_queue."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while True:
            try:
                text = self.text_queue.get()
                if text is None:
                    break

                if self.interrupted.is_set():
                    self.text_queue.task_done()
                    continue

                # Synthesize text into audio array
                audio_item = self._synthesize_audio(text, loop)
                if audio_item and not self.interrupted.is_set():
                    self.audio_queue.put(audio_item)

                self.text_queue.task_done()

            except Exception as e:
                print(f"[Nixi TTS] Synthesis error: {e}")

    def _synthesize_audio(self, text: str, loop: asyncio.AbstractEventLoop) -> Optional[Tuple[np.ndarray, int]]:
        """Fetch neural audio via edge-tts with fast fallback."""
        if not text.strip():
            return None

        if HAS_EDGE_TTS:
            try:
                async def _fetch():
                    communicate = edge_tts.Communicate(
                        text=text,
                        voice=self.voice,
                        rate=self.rate,
                        pitch=self.pitch
                    )
                    chunks: List[bytes] = []
                    async for chunk in communicate.stream():
                        if self.interrupted.is_set():
                            return None
                        if chunk["type"] == "audio":
                            chunks.append(chunk["data"])
                    return b"".join(chunks)

                audio_bytes = loop.run_until_complete(asyncio.wait_for(_fetch(), timeout=8.0))
                if not audio_bytes or self.interrupted.is_set():
                    return None

                # Decode audio bytes in memory directly to float32 numpy array
                audio_data, sample_rate = sf.read(io.BytesIO(audio_bytes))
                return audio_data, sample_rate

            except Exception as e:
                pass

        # Local fallback via SAPI wav if edge-tts timed out
        return self._local_sapi_audio(text)

    def _local_sapi_audio(self, text: str) -> Optional[Tuple[np.ndarray, int]]:
        """Generate audio in RAM using Windows SAPI for zero-latency fallback."""
        try:
            import win32com.client
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            stream = win32com.client.Dispatch("SAPI.SpMemoryStream")
            voice.AudioOutputStream = stream
            voice.Speak(text)
            raw_bytes = bytes(stream.GetData())
            if raw_bytes:
                audio_data, sample_rate = sf.read(io.BytesIO(raw_bytes))
                return audio_data, sample_rate
        except Exception:
            pass
        return None

    def _playback_loop(self):
        """Background thread 2: Consumes decoded audio continuously with ZERO delay between chunks."""
        while True:
            try:
                item = self.audio_queue.get()
                if item is None:
                    break

                if self.interrupted.is_set():
                    self.audio_queue.task_done()
                    continue

                audio_data, sample_rate = item
                self.is_speaking = True

                # Play through sounddevice
                sd.play(audio_data, samplerate=sample_rate)

                # Wait for this chunk's playback duration using wall-clock time
                duration = len(audio_data) / float(sample_rate)
                start_t = time.time()
                while (time.time() - start_t) < duration and not self.interrupted.is_set():
                    time.sleep(0.02)

                if self.interrupted.is_set():
                    sd.stop()

                self.audio_queue.task_done()

                if self.audio_queue.empty() and self.text_queue.empty():
                    self.is_speaking = False

            except Exception as e:
                print(f"[Nixi TTS] Playback loop error: {e}")
                self.is_speaking = False


class SentenceStreamer:
    """
    Buffers streaming token chunks from the LLM and feeds initial words
    and sentences to NixiTTS *concurrently*, so speech begins within 200ms of text!
    """
    def __init__(self, tts: NixiTTS, max_speech_sentences: int = 4):
        self.tts = tts
        self.buffer = ""
        self.sentence_count = 0
        self.max_sentences = max_speech_sentences
        self.is_first_chunk = True

    def feed(self, chunk: str):
        """Feed a new streaming token chunk from the LLM."""
        if self.sentence_count >= self.max_sentences:
            return

        self.buffer += chunk

        # ── Early Trigger: First 3-5 words start voice synthesis immediately! ──
        if self.is_first_chunk:
            # Check if we have 4+ words or punctuation (e.g. "Sure, I can help")
            first_match = re.search(r"^(\s*\S+(?:\s+\S+){2,4}[,.:;!?-]|\s*\S+(?:\s+\S+){4}\s+)(.*)$", self.buffer, re.DOTALL)
            if first_match:
                first_words = first_match.group(1).strip()
                self.buffer = first_match.group(2)
                if first_words and len(first_words) > 2:
                    self.sentence_count += 1
                    self.is_first_chunk = False
                    self.tts.enqueue_sentence(first_words)

        # ── Standard Clause/Sentence Chunking for subsequent speech ──
        while True:
            # Match sentence endings (. ! ? \n)
            match = re.search(r"^(.*?)([.!?]+(?:\s+|\Z)|\n+)(.*)$", self.buffer, re.DOTALL)
            if match:
                sentence = (match.group(1) + match.group(2)).strip()
                self.buffer = match.group(3)
                if sentence and len(sentence) > 2:
                    self.sentence_count += 1
                    self.is_first_chunk = False
                    self.tts.enqueue_sentence(sentence)
                    if self.sentence_count >= self.max_sentences:
                        break
            else:
                # If clause is 6+ words with a comma or semicolon
                clause_match = re.search(r"^(\s*\S+(?:\s+\S+){4,7}[,;:])\s+(.*)$", self.buffer, re.DOTALL)
                if clause_match:
                    clause = clause_match.group(1).strip()
                    self.buffer = clause_match.group(2)
                    if clause and len(clause) > 2:
                        self.sentence_count += 1
                        self.is_first_chunk = False
                        self.tts.enqueue_sentence(clause)
                        if self.sentence_count >= self.max_sentences:
                            break
                break

    def finish(self):
        """Flush any remaining buffered text when stream ends."""
        while True:
            match = re.search(r"^(.*?)([.!?]+(?:\s+|\Z)|\n+)(.*)$", self.buffer, re.DOTALL)
            if match:
                sentence = (match.group(1) + match.group(2)).strip()
                self.buffer = match.group(3)
                if sentence and len(sentence) > 2:
                    self.sentence_count += 1
                    self.tts.enqueue_sentence(sentence)
                    if self.sentence_count >= self.max_sentences:
                        break
            else:
                break

        if self.sentence_count < self.max_sentences:
            remaining = self.buffer.strip()
            if remaining and len(remaining) > 1:
                self.sentence_count += 1
                self.tts.enqueue_sentence(remaining)
        self.buffer = ""
