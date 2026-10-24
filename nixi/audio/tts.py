"""
Nixi High-Speed Streaming Neural TTS (Text-to-Speech)
Provides sub-second voice streaming directly concurrent with LLM token generation.
Uses Microsoft Neural Voices (Ava/Aria) via edge-tts with in-memory decoding,
instant sentence queuing, interruption support, and fallback capabilities.
"""
from __future__ import annotations

import io
import re
import queue
import threading
import asyncio
import sounddevice as sd
import soundfile as sf
from typing import Optional, List

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

# Lazy torch check to keep module import instantaneous (<10ms)
HAS_TORCH_CUDA = False


class NixiTTS:
    def __init__(self, voice: str = "en-US-AvaNeural", rate: str = "+5%", pitch: str = "+0Hz"):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        
        self.sentence_queue: queue.Queue[Optional[str]] = queue.Queue()
        self.is_speaking = False
        self.interrupted = threading.Event()
        
        # Dedicated audio playback thread
        self.worker_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.worker_thread.start()

    def clean_text(self, text: str) -> str:
        """Strip markdown syntax, action tokens, URLs, and code blocks for clean voice output."""
        if not text:
            return ""
        # Remove actions like [ACTION:CLICK...]
        text = re.sub(r"\[ACTION:[^\]]+\]", "", text)
        # Remove URLs
        text = re.sub(r"https?://\S+", "", text)
        # Remove markdown code blocks & inline code
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"`[^`]+`", "", text)
        # Remove bold, italics, headers, bullets
        text = re.sub(r"[*#_~>\[\]\(\)]", " ", text)
        # Collapse multiple spaces
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def enqueue_sentence(self, text: str):
        """Enqueue a sentence to be spoken immediately in real-time sequence."""
        clean = self.clean_text(text)
        if not clean:
            return
        self.interrupted.clear()
        self.sentence_queue.put(clean)

    def speak(self, text: str, interrupt_previous: bool = True):
        """Speak a complete string immediately."""
        if interrupt_previous:
            self.stop()
        
        # Split into sentences if multi-sentence
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        if not sentences:
            sentences = [text]
            
        for s in sentences:
            self.enqueue_sentence(s)

    def stop(self):
        """Instantly stop ongoing speech and clear the pending queue."""
        self.interrupted.set()
        try:
            sd.stop()
        except Exception:
            pass
        # Drain queue
        while not self.sentence_queue.empty():
            try:
                self.sentence_queue.get_nowait()
                self.sentence_queue.task_done()
            except queue.Empty:
                break
        self.is_speaking = False

    def _playback_loop(self):
        """Worker loop that continuously synthesizes and plays queued sentences."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while True:
            try:
                text = self.sentence_queue.get()
                if text is None:
                    break

                if self.interrupted.is_set():
                    self.sentence_queue.task_done()
                    continue

                self.is_speaking = True
                self._synthesize_and_play(text, loop)
                self.sentence_queue.task_done()

                if self.sentence_queue.empty():
                    self.is_speaking = False

            except Exception as e:
                print(f"[Nixi TTS] Error in playback loop: {e}")
                self.is_speaking = False

    def _synthesize_and_play(self, text: str, loop: asyncio.AbstractEventLoop):
        """Synthesize text using edge-tts directly into memory and play through sounddevice."""
        if not text.strip():
            return

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

                audio_bytes = loop.run_until_complete(_fetch())
                if not audio_bytes or self.interrupted.is_set():
                    return

                # Decode audio bytes in memory
                audio_data, sample_rate = sf.read(io.BytesIO(audio_bytes))

                if self.interrupted.is_set():
                    return

                # Play via sounddevice and wait for this sentence to finish
                sd.play(audio_data, samplerate=sample_rate)
                
                # Check interruption while playing
                duration = len(audio_data) / float(sample_rate)
                step = 0.05
                elapsed = 0.0
                while elapsed < duration and not self.interrupted.is_set():
                    loop.run_until_complete(asyncio.sleep(step))
                    elapsed += step

                if self.interrupted.is_set():
                    sd.stop()

                return

            except Exception as e:
                print(f"[Nixi TTS] edge-tts error: {e}, falling back to system speech.")

        # Fallback to Windows SAPI Speech if edge-tts failed or offline
        self._system_fallback(text)

    def _system_fallback(self, text: str):
        """Fallback to Windows built-in speech engine."""
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Speak(text)
        except Exception:
            pass


class SentenceStreamer:
    """
    Buffers streaming token chunks from the LLM and feeds complete sentences
    to NixiTTS *then and there*, concurrent with text display!
    """
    def __init__(self, tts: NixiTTS, max_speech_sentences: int = 4):
        self.tts = tts
        self.buffer = ""
        self.sentence_count = 0
        self.max_sentences = max_speech_sentences

    def feed(self, chunk: str):
        """Feed a new streaming token chunk from the LLM."""
        if self.sentence_count >= self.max_sentences:
            return

        self.buffer += chunk

        # Detect sentence boundary (. ! ? followed by space or newline, or newline alone)
        # Also handle long clauses (comma after 8+ words)
        while True:
            # Match standard sentence end
            match = re.search(r"^(.*?)([.!?]+(?:\s+|\Z)|\n+)(.*)$", self.buffer, re.DOTALL)
            if match:
                sentence = (match.group(1) + match.group(2)).strip()
                self.buffer = match.group(3)
                if sentence and len(sentence) > 1:
                    self.sentence_count += 1
                    self.tts.enqueue_sentence(sentence)
                    if self.sentence_count >= self.max_sentences:
                        break
            else:
                # If buffer is getting very long (>80 chars) and contains a comma or semicolon
                clause_match = re.search(r"^(.{25,}?)([,;:]\s+)(.*)$", self.buffer, re.DOTALL)
                if clause_match:
                    clause = clause_match.group(1).strip()
                    self.buffer = clause_match.group(3)
                    if clause:
                        self.sentence_count += 1
                        self.tts.enqueue_sentence(clause)
                        if self.sentence_count >= self.max_sentences:
                            break
                break

    def finish(self):
        """Flush any remaining buffered text when stream ends."""
        if self.sentence_count < self.max_sentences:
            remaining = self.buffer.strip()
            if remaining and len(remaining) > 1:
                self.sentence_count += 1
                self.tts.enqueue_sentence(remaining)
        self.buffer = ""
