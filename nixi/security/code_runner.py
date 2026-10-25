"""Sandboxed code runner — temp directory, resource limits, no silent self-heal."""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from nixi.config import NixiConfig, get_config
from nixi.logging_utils import get_logger

log = get_logger("code_runner")

_FORBIDDEN_PATTERNS = [
    r"\bos\.system\s*\(",
    r"\bsubprocess\.",
    r"\b__import__\s*\(\s*['\"]os['\"]",
    r"\bopen\s*\(.*['\"]w['\"]",
    r"\bshutil\.rmtree",
]


def _check_sandbox(code: str) -> str | None:
    for pattern in _FORBIDDEN_PATTERNS:
        if re.search(pattern, code):
            return f"blocked pattern: {pattern}"
    return None


def run_code(
    code: str,
    language: str = "python",
    timeout: int | None = None,
    allow_network: bool | None = None,
    config: NixiConfig | None = None,
) -> dict:
    """
    Execute ``code`` in an isolated temp directory.
    Returns {"ok": bool, "stdout": str, "stderr": str, "elapsed_ms": float}.
    """
    cfg = config or get_config()
    timeout = timeout if timeout is not None else cfg.code_timeout
    allow_network = allow_network if allow_network is not None else cfg.code_network

    code = code.strip()
    if code.startswith("```"):
        code = re.sub(r"^```[a-zA-Z]*\n?", "", code)
        code = re.sub(r"\n?```$", "", code)
        code = code.strip()
    if not code:
        return {"ok": False, "stdout": "", "stderr": "empty code", "elapsed_ms": 0}

    sandbox = cfg.sandbox_code
    if sandbox:
        blocked = _check_sandbox(code)
        if blocked:
            return {"ok": False, "stdout": "", "stderr": f"sandbox: {blocked}", "elapsed_ms": 0}

    start = time.perf_counter()
    if language.lower() not in ("python", "py", "python3"):
        return {"ok": False, "stdout": "", "stderr": f"unsupported language: {language}", "elapsed_ms": 0}

    with tempfile.TemporaryDirectory(prefix="nixi-code-") as tmpdir:
        script = Path(tmpdir) / "snippet.py"
        script.write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True, text=True, timeout=timeout, cwd=tmpdir,
            )
            elapsed = (time.perf_counter() - start) * 1000
            return {
                "ok": proc.returncode == 0,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
                "elapsed_ms": round(elapsed, 1),
            }
        except subprocess.TimeoutExpired:
            elapsed = (time.perf_counter() - start) * 1000
            return {"ok": False, "stdout": "", "stderr": f"timed out after {timeout}s", "elapsed_ms": round(elapsed, 1)}
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return {"ok": False, "stdout": "", "stderr": str(exc), "elapsed_ms": round(elapsed, 1)}


def run_self_healing(
    code: str,
    language: str = "python",
    max_retries: int = 1,
    llm_client=None,
    config: NixiConfig | None = None,
) -> dict:
    """Run code, and if it fails ask the LLM once to fix it (explicit opt-in)."""
    result = run_code(code, language=language, config=config)
    if result["ok"] or not llm_client or max_retries < 1:
        return result
    try:
        prompt = [
            {"role": "system", "content": "You are a code fixing assistant. Return ONLY the corrected code, no markdown."},
            {"role": "user", "content": f"Code:\n{code}\n\nError:\n{result['stderr']}\n\nFix it:"},
        ]
        healed = ""
        for chunk in llm_client.chat_stream(prompt, temperature=0.1):
            healed += chunk
        healed = healed.strip()
        if healed.startswith("```"):
            healed = re.sub(r"^```[a-zA-Z]*\n?", "", healed)
            healed = re.sub(r"\n?```$", "", healed)
        if healed:
            log.info("Self-heal retry with %d chars", len(healed))
            return run_code(healed, language=language, config=config)
    except Exception as exc:
        log.warning("Self-heal failed: %s", exc)
    return result
