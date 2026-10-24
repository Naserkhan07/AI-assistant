"""
LLM Client for Nixi — Turbo Streaming Edition with Multi-Model Resilient Failover
Connects to FreeLLMAPI gateway (http://127.0.0.1:3001/v1).
Automatically handles 502/429/500/504 errors by failing over across healthy free models seamlessly.
"""
from __future__ import annotations

import os
from pathlib import Path
import json
import base64
from typing import Generator, Optional, Dict, Any, List
import httpx
from dotenv import load_dotenv

# Ensure environment variables from .env are loaded
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()

DEFAULT_BASE_URL = os.getenv("FREELLMAPI_URL", "http://127.0.0.1:3001/v1")
DEFAULT_API_KEY = os.getenv("FREELLMAPI_KEY", "")
DEFAULT_MODEL = os.getenv("FREELLMAPI_MODEL", "mistral-nemo")

SYSTEM_PROMPT = """You are Nixi, an ultra-fast Windows AI desktop assistant.
Respond immediately in 1-2 punchy, direct sentences.
Never use markdown, bullet points, or conversational filler."""

class NixiLLMClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, api_key: str = DEFAULT_API_KEY, model: str = DEFAULT_MODEL):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("FREELLMAPI_KEY", "")
        self.model = model or "mistral-nemo"
        # Fast connect and responsive read timeout
        self.client = httpx.Client(timeout=httpx.Timeout(connect=3.5, read=6.0, write=5.0, pool=5.0))

    def is_online(self) -> bool:
        """Check if FreeLLMAPI or endpoint is reachable."""
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            r = self.client.get(f"{self.base_url}/models", headers=headers, timeout=3.0)
            return r.status_code in (200, 401, 403)
        except Exception:
            return False

    def _get_candidate_models(self) -> List[str]:
        """Returns ordered list of verified free models to try in case of 502/429 upstream errors."""
        unusable = {"gemini-flash", "llama-instant", "groq-compound-mini", "auto:fast"}
        preferred = self.model if self.model not in unusable else "mistral-nemo"
        order = [
            preferred,
            "mistral-nemo",
            "free-router",
            "kilo-auto",
            "dots3-note-preview",
            "auto",
        ]
        seen = set()
        candidates = []
        for m in order:
            if m and m not in seen and m not in unusable:
                seen.add(m)
                candidates.append(m)
        return candidates

    def chat_stream(self, messages: List[Dict[str, Any]], temperature: float = 0.25) -> Generator[str, None, None]:
        """
        Stream response chunks from the LLM with automatic failover.
        If a provider returns 502, 504, 500, or 429, seamlessly falls over to the next free model.
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        
        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        models_to_try = self._get_candidate_models()
        has_streamed = False

        for model_name in models_to_try:
            payload = {
                "model": model_name,
                "messages": full_messages,
                "temperature": temperature,
                "max_tokens": 120,
                "stream": True,
            }

            try:
                with self.client.stream("POST", url, headers=headers, json=payload, timeout=httpx.Timeout(connect=3.5, read=6.0, write=5.0, pool=5.0)) as response:
                    if response.status_code == 200:
                        stream_failed = False
                        in_think = False
                        for line in response.iter_lines():
                            line = line.strip()
                            if not line or not line.startswith("data: "):
                                continue
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                if "error" in chunk:
                                    stream_failed = True
                                    break
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if not content:
                                    continue

                                # Suppress internal reasoning or thinking tags if present
                                if "<think>" in content:
                                    in_think = True
                                if in_think:
                                    if "</think>" in content:
                                        in_think = False
                                        content = content.split("</think>")[-1]
                                    else:
                                        continue

                                if content:
                                    has_streamed = True
                                    yield content
                            except Exception:
                                continue
                        
                        if has_streamed and not stream_failed:
                            return
                        elif stream_failed:
                            print(f"[Nixi LLM] Model '{model_name}' returned error in chunk. Trying fallback...")
                            continue
                    else:
                        print(f"[Nixi LLM] Model '{model_name}' returned status {response.status_code}. Auto-failing over to next free model...")
                        continue

            except httpx.ConnectError:
                yield "FreeLLMAPI connection error. Ensure FreeLLMAPI is running on port 3001."
                return
            except Exception as e:
                print(f"[Nixi LLM] Model '{model_name}' stream error: {e}. Trying fallback...")
                continue

        # Fast non-streaming rescue attempt if streaming tokens stalled
        if not has_streamed:
            for rescue_model in ["mistral-nemo", "free-router", "kilo-auto"]:
                try:
                    rescue_payload = {
                        "model": rescue_model,
                        "messages": full_messages,
                        "temperature": temperature,
                        "max_tokens": 120,
                        "stream": False,
                    }
                    r = self.client.post(url, headers=headers, json=rescue_payload, timeout=5.0)
                    if r.status_code == 200:
                        content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                        if content:
                            yield content
                            return
                except Exception:
                    pass

            yield "All cloud model endpoints are temporarily busy. I am ready to help with local tasks, system controls, and web search."

    def analyze_screen(self, image_bytes: bytes, prompt: str = "Describe what is on my screen in 1-2 concise sentences.") -> str:
        """Fast screen analysis with automatic multi-model failover."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
                    }
                ]
            }
        ]

        models_to_try = self._get_candidate_models()
        for model_name in models_to_try:
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 140,
            }

            try:
                resp = self.client.post(url, headers=headers, json=payload, timeout=12.0)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content and not content.startswith("Error"):
                        return content
            except Exception:
                continue

        return "Vision models are temporarily busy. Please retry in a few seconds."
