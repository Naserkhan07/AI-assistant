"""
LLM Client for Nixi — Turbo Streaming Edition
Connects to FreeLLMAPI gateway (http://127.0.0.1:3001/v1) with low-latency streaming.
"""
from __future__ import annotations

import os
import json
import base64
from typing import Generator, Optional, Dict, Any, List
import httpx

DEFAULT_BASE_URL = os.getenv("FREELLMAPI_URL", "http://127.0.0.1:3001/v1")
DEFAULT_API_KEY = os.getenv("FREELLMAPI_KEY", "dummy-key")
DEFAULT_MODEL = os.getenv("FREELLMAPI_MODEL", "auto:fast")

SYSTEM_PROMPT = """You are Nixi, an ultra-fast Windows AI desktop assistant.
Respond immediately in 1-2 punchy, direct sentences.
Never use markdown, bullet points, or conversational filler."""

class NixiLLMClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, api_key: str = DEFAULT_API_KEY, model: str = DEFAULT_MODEL):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.client = httpx.Client(timeout=15.0)

    def is_online(self) -> bool:
        """Check if FreeLLMAPI or endpoint is reachable."""
        try:
            r = self.client.get(f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"})
            return r.status_code in (200, 401, 403)
        except Exception:
            return False

    def chat_stream(self, messages: List[Dict[str, Any]], temperature: float = 0.25) -> Generator[str, None, None]:
        """Stream response chunks from the LLM with minimal latency."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        
        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": 100,
            "stream": True,
        }

        try:
            with self.client.stream("POST", url, headers=headers, json=payload, timeout=25.0) as response:
                if response.status_code != 200:
                    yield f"Error: Endpoint returned {response.status_code}"
                    return

                for line in response.iter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except Exception:
                        continue
        except httpx.ConnectError:
            yield "FreeLLMAPI connection error. Ensure FreeLLMAPI is running on port 3001."
        except Exception as e:
            yield f"Error: {str(e)}"

    def analyze_screen(self, image_bytes: bytes, prompt: str = "Describe what is on my screen in 1-2 concise sentences.") -> str:
        """Fast screen analysis with compact tokens."""
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

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 200,
        }

        try:
            resp = self.client.post(url, headers=headers, json=payload, timeout=25.0)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "No description returned.")
            else:
                return f"Vision returned status {resp.status_code}."
        except Exception as e:
            return f"Vision error: {str(e)}"
