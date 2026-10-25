"""Weather, news, calculator and translator — stdlib-first, optional deps layered."""
from __future__ import annotations

import ast
import math
import operator
import re
import time
from typing import Any

from nixi.config import NixiConfig, get_config
from nixi.logging_utils import get_logger

log = get_logger("integrations")


# ── Calculator (safe AST eval) ──────────────────────────────────────────────
_ALLOWED_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}
_ALLOWED_FUNCS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "exp": math.exp, "abs": abs,
    "round": round, "ceil": math.ceil, "floor": math.floor, "factorial": math.factorial,
    "pi": math.pi, "e": math.e,
}


class Calculator:
    def evaluate(self, expression: str) -> dict[str, Any]:
        expr = expression.strip()
        if not expr:
            return {"ok": False, "error": "empty expression"}
        # allow common aliases
        expr = expr.replace("^", "**").replace("×", "*").replace("÷", "/")
        try:
            tree = ast.parse(expr, mode="eval")
            result = self._eval(tree.body)
            return {"ok": True, "expression": expression, "result": result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _eval(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Num):  # py <3.8 compat
            return node.n  # type: ignore
        if isinstance(node, ast.BinOp):
            op = _ALLOWED_OPS.get(type(node.op))
            if not op:
                raise ValueError(f"operator {type(node.op).__name__} not allowed")
            return op(self._eval(node.left), self._eval(node.right))
        if isinstance(node, ast.UnaryOp):
            op = _ALLOWED_OPS.get(type(node.op))
            if not op:
                raise ValueError(f"unary {type(node.op).__name__} not allowed")
            return op(self._eval(node.operand))
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
                raise ValueError(f"function {getattr(node.func, 'id', '?')} not allowed")
            fn = _ALLOWED_FUNCS[node.func.id]
            args = [self._eval(a) for a in node.args]
            return fn(*args)
        if isinstance(node, ast.Name):
            if node.id in _ALLOWED_FUNCS and not callable(_ALLOWED_FUNCS[node.id]):
                return _ALLOWED_FUNCS[node.id]
            raise ValueError(f"unknown name: {node.id}")
        raise ValueError(f"unsupported: {type(node).__name__}")


class Translator:
    """Offline dictionary stub + optional online fallback (disabled in local_only)."""

    _DICT: dict[tuple[str, str], dict[str, str]] = {
        ("en", "hi"): {"hello": "नमस्ते", "goodbye": "अलविदा", "thank you": "धन्यवाद", "please": "कृपया", "yes": "हाँ", "no": "नहीं"},
        ("hi", "en"): {"नमस्ते": "hello", "धन्यवाद": "thank you"},
    }

    def translate(self, text: str, source: str = "auto", target: str = "en") -> dict[str, Any]:
        text = text.strip()
        if not text:
            return {"ok": False, "error": "empty text"}
        source = source.lower()
        target = target.lower()
        key = (source, target) if source != "auto" else None
        # try offline dict
        if key and key in self._DICT:
            lower = text.lower()
            if lower in self._DICT[key]:
                return {"ok": True, "text": self._DICT[key][lower], "source": source, "target": target, "offline": True}
        return {"ok": True, "text": text, "source": source, "target": target, "offline": True,
                "note": "offline dictionary — for full translation configure an API provider"}


class WeatherClient:
    def __init__(self, config: NixiConfig | None = None):
        self.config = config or get_config()

    def get(self) -> dict[str, Any]:
        # open-meteo is free, no key, but respect local_only
        if self.config.local_only:
            return {"ok": False, "error": "local-only mode: weather unavailable offline"}
        lat, lon = self.config.briefing_latitude, self.config.briefing_longitude
        try:
            import urllib.request, json
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=2"
            with urllib.request.urlopen(url, timeout=6) as resp:
                data = json.loads(resp.read().decode())
            cur = data.get("current", {})
            daily = data.get("daily", {})
            return {"ok": True, "current": cur, "daily": daily, "source": "open-meteo"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def format_briefing(self) -> str:
        r = self.get()
        if not r.get("ok"):
            return f"Weather unavailable: {r.get('error','')}"
        cur = r["current"]
        return f"🌤️ {cur.get('temperature_2m','?')}°C, wind {cur.get('wind_speed_10m','?')} km/h"


class NewsClient:
    def __init__(self, config: NixiConfig | None = None):
        self.config = config or get_config()

    def fetch(self, limit: int = 5) -> list[dict[str, Any]]:
        if self.config.local_only:
            return []
        feeds = self.config.briefing_news_feeds
        if not feeds:
            return []
        items: list[dict[str, Any]] = []
        try:
            import feedparser  # type: ignore
            has_fp = True
        except ImportError:
            has_fp = False
        if not has_fp:
            return []
        for url in feeds[:3]:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:limit]:
                    items.append({"title": entry.get("title",""), "link": entry.get("link",""), "published": entry.get("published","")})
            except Exception:
                continue
        return items[:limit]

    def format_briefing(self) -> str:
        items = self.fetch(limit=3)
        if not items:
            return "No news feeds configured (set NIXI_NEWS_FEEDS)."
        return "📰 Headlines:\n" + "\n".join(f"• {it['title']}" for it in items)
