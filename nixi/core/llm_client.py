"""LLM client — multi-provider, streaming, tool-calling, offline fallback."""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any, Generator

from nixi.config import NixiConfig, ProviderSpec, get_config
from nixi.logging_utils import get_logger
from nixi.util.text import extract_json

log = get_logger("llm")

SYSTEM_PROMPT = (
    "You are Nixi, a fast, helpful AI desktop assistant. "
    "You have live vision access to the user's screen when vision is enabled. "
    "Never claim you cannot see the screen when an image is attached. "
    "Respond in 1-3 concise sentences unless asked for more detail. "
    "When you need to act, emit a single JSON tool call: {\"tool\": \"name\", \"args\": {...}}."
)

VISION_SYSTEM = (
    "You are Nixi with live screen vision. Describe what you see directly. "
    "Never say you cannot see the screen. Do not emit <think> tags."
)


def _has_image(messages: list[dict[str, Any]]) -> bool:
    for m in messages:
        c = m.get("content")
        if isinstance(c, list) and any(isinstance(p, dict) and p.get("type") == "image_url" for p in c):
            return True
    return False


class OfflineResponder:
    """Useful without any network — answers from local knowledge."""

    RESPONSES: dict[str, str] = {
        "hello": "Hello! I'm Nixi (offline mode). I can help with files, timers, calculations, and local tasks.",
        "help": "Offline: I can organize files, manage timers, calculate, manage your knowledge base, calendar, and run local code. Connect a provider for web search and vision.",
        "time": "I can set timers and check system stats. Try 'set timer for 5 minutes'.",
    }

    def reply(self, messages: list[dict[str, Any]]) -> str:
        last = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                c = m.get("content")
                if isinstance(c, list):
                    last = next((p.get("text","") for p in c if isinstance(p, dict) and p.get("type")=="text"), "")
                else:
                    last = str(c or "")
                break
        lower = last.lower().strip()
        for key, resp in self.RESPONSES.items():
            if key in lower:
                return resp
        if "calculate" in lower or "what is" in lower:
            return "I can calculate that offline — try the calculator tool."
        return "I'm in offline mode. I can still help with local tasks — files, timers, calculations, and your knowledge base."


class NixiLLMClient:
    def __init__(self, config: NixiConfig | None = None,
                 base_url: str | None = None, api_key: str | None = None, model: str | None = None):
        self.config = config or get_config()
        # explicit args override config (back-compat with old call sites)
        self._override_base = base_url
        self._override_key = api_key
        self._override_model = model
        self.offline = OfflineResponder()
        try:
            import httpx
            self._httpx = httpx
            self._client = httpx.Client(timeout=httpx.Timeout(connect=4.0, read=12.0, write=5.0, pool=5.0))
        except ImportError:
            self._httpx = None  # type: ignore
            self._client = None  # type: ignore

    def _providers(self) -> list[ProviderSpec]:
        specs = self.config.provider_specs()
        if self._override_base or self._override_key or self._override_model:
            specs = [ProviderSpec("override", base_url=self._override_base or specs[0].base_url,
                                  api_key=self._override_key or specs[0].api_key,
                                  model=self._override_model or specs[0].model)] + specs
        return specs

    def is_online(self) -> bool:
        if self.config.local_only or self.config.provider == "offline":
            return False
        if not self._client:
            return False
        for spec in self._providers():
            if spec.is_offline:
                continue
            try:
                headers: dict[str, str] = {}
                if spec.api_key:
                    headers["Authorization"] = f"Bearer {spec.api_key}"
                r = self._client.get(f"{spec.base_url}/models", headers=headers, timeout=3.0)
                if r.status_code in (200, 401, 403):
                    return True
            except Exception:
                continue
        return False

    def _candidate_models(self, vision: bool) -> list[str]:
        if vision:
            return list(self.config.vision_models) or ["auto"]
        # respect provider default but filter known-bad legacy names
        bad = {"gemini-flash", "llama-instant", "groq-compound-mini"}
        preferred = self.config.model if self.config.model not in bad else "mistral-nemo"
        order = [preferred] + [m for m in (self.config.fallback_models or ()) if m not in bad and m != preferred]
        seen: set[str] = set()
        out: list[str] = []
        for m in order:
            if m and m not in seen:
                seen.add(m)
                out.append(m)
        return out or ["auto"]

    def chat_stream(self, messages: list[dict[str, Any]], temperature: float | None = None) -> Generator[str, None, None]:
        temp = temperature if temperature is not None else self.config.temperature
        vision = _has_image(messages)
        full = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        max_tokens = self.config.vision_max_tokens if vision else self.config.max_tokens

        # offline path
        if self.config.local_only or not self._client:
            yield self.offline.reply(messages)
            return

        providers = [p for p in self._providers() if not p.is_offline]
        if not providers:
            yield self.offline.reply(messages)
            return

        has_streamed = False
        for spec in providers:
            for model_name in self._candidate_models(vision):
                url = f"{spec.base_url}/chat/completions"
                headers = {"Content-Type": "application/json"}
                if spec.api_key:
                    headers["Authorization"] = f"Bearer {spec.api_key}"
                payload = {"model": model_name, "messages": full, "temperature": temp, "max_tokens": max_tokens, "stream": True}
                try:
                    with self._client.stream("POST", url, headers=headers, json=payload,
                                             timeout=self._httpx.Timeout(connect=4.0, read=12.0, write=5.0, pool=5.0)) as resp:
                        if resp.status_code != 200:
                            log.debug("model %s -> %s, trying next", model_name, resp.status_code)
                            continue
                        stream_failed = False
                        in_think = False
                        for line in resp.iter_lines():
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
                        if stream_failed:
                            continue
                except Exception as exc:
                    if isinstance(exc, self._httpx.ConnectError):  # type: ignore
                        yield "Connection error — is the LLM gateway running? Check Settings > Provider."
                        return
                    log.debug("stream error %s: %s", model_name, exc)
                    continue

        if not has_streamed:
            # one non-streaming rescue
            for spec in providers:
                for m in ["mistral-nemo", "free-router", "kilo-auto"]:
                    try:
                        url = f"{spec.base_url}/chat/completions"
                        headers = {"Content-Type": "application/json"}
                        if spec.api_key:
                            headers["Authorization"] = f"Bearer {spec.api_key}"
                        r = self._client.post(url, headers=headers,
                                              json={"model": m, "messages": full, "temperature": temp, "max_tokens": 120, "stream": False}, timeout=5.0)
                        if r.status_code == 200:
                            content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                            if content:
                                yield content
                                return
                    except Exception:
                        pass
            yield "All model endpoints are busy. I can still help with local tasks, file search, and knowledge base."

    def chat(self, messages: list[dict[str, Any]], temperature: float | None = None) -> str:
        return "".join(self.chat_stream(messages, temperature=temperature))

    def tool_loop(self, messages: list[dict[str, Any]], tools: dict[str, Any],
                  max_iters: int = 6, temperature: float | None = None) -> str:
        """
        Structured tool-calling loop.
        ``tools`` maps tool name -> {"description": str, "function": callable, "risk": RiskLevel|int}
        The model is instructed to emit {"tool": "...", "args": {...}}; we execute and feed back observations.
        Returns the final assistant message.
        """
        from nixi.security.permissions import PermissionManager, RiskLevel

        tool_desc = "\n".join(f"- {name}: {spec.get('description','')}" for name, spec in tools.items())
        system = (
            f"{SYSTEM_PROMPT}\n\nAvailable tools:\n{tool_desc}\n\n"
            "To act, reply with ONLY a JSON object like {\"tool\": \"name\", \"args\": {...}} on its own line. "
            "When done, reply with {\"final\": \"your answer\"}."
        )
        convo = [{"role": "system", "content": system}] + list(messages)
        pm = getattr(self, "_permission_manager", None)

        for _ in range(max_iters):
            reply = self.chat(convo, temperature=temperature)
            parsed = extract_json(reply)
            if not parsed:
                return reply
            if "final" in parsed:
                return str(parsed["final"])
            tool_name = parsed.get("tool")
            args = parsed.get("args", {})
            if not tool_name or tool_name not in tools:
                convo.append({"role": "assistant", "content": reply})
                convo.append({"role": "user", "content": f"Unknown tool '{tool_name}'. Use one of: {', '.join(tools.keys())} or return {{\"final\": \"...\"}}."})
                continue
            # permission check
            risk = tools[tool_name].get("risk", RiskLevel.SAFE)
            if pm:
                decision = pm.authorize(tool_name, risk, args if isinstance(args, dict) else {})
                if not decision.allowed:
                    convo.append({"role": "assistant", "content": reply})
                    convo.append({"role": "user", "content": f"Tool '{tool_name}' denied: {decision.reason}"})
                    continue
                if decision.dry_run:
                    convo.append({"role": "assistant", "content": reply})
                    convo.append({"role": "user", "content": f"[DRY RUN] Tool '{tool_name}' would run with {args}. No changes made."})
                    continue
            try:
                fn = tools[tool_name]["function"]
                result = fn(**args) if isinstance(args, dict) else fn(args)
                observation = str(result)[:2000]
            except TypeError as exc:
                observation = f"argument error: {exc}"
            except Exception as exc:
                observation = f"error: {exc}"
            convo.append({"role": "assistant", "content": reply})
            convo.append({"role": "user", "content": f"Observation from {tool_name}: {observation}"})
        return reply

    def analyze_screen(self, image_bytes: bytes, prompt: str = "Describe what is on my screen in 1-2 concise sentences.",
                       max_tokens: int | None = None) -> str:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        messages = [
            {"role": "system", "content": VISION_SYSTEM},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]},
        ]
        # reuse providers
        mt = max_tokens or self.config.vision_max_tokens
        if self.config.local_only or not self._client:
            return "Vision requires an online model (local-only mode is on)."
        for spec in [p for p in self._providers() if not p.is_offline]:
            for model_name in self._candidate_models(vision=True):
                try:
                    url = f"{spec.base_url}/chat/completions"
                    headers = {"Content-Type": "application/json"}
                    if spec.api_key:
                        headers["Authorization"] = f"Bearer {spec.api_key}"
                    resp = self._client.post(url, headers=headers,
                                             json={"model": model_name, "messages": messages, "temperature": 0.2, "max_tokens": mt}, timeout=20.0)
                    if resp.status_code == 200:
                        content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                        if content:
                            if "<think>" in content:
                                content = content.split("</think>")[-1].strip()
                            return content
                except Exception:
                    continue
        return "Vision models are temporarily busy. Please retry in a moment."
