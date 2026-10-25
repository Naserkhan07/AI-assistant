"""Tiny local HTTP API — health, chat, history, tools, undo, plugins."""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from nixi.config import NixiConfig, get_config
from nixi.logging_utils import get_logger, Diagnostics

log = get_logger("server")


class _Handler(BaseHTTPRequestHandler):
    server_ref: "NixiServer"  # set per-instance

    def log_message(self, fmt: str, *args: Any) -> None:
        log.debug(fmt % args)

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _auth_ok(self) -> bool:
        token = self.server_ref.config.api_token
        if not token:
            return True
        auth = self.headers.get("Authorization", "")
        if auth == f"Bearer {token}":
            return True
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if qs.get("token", [""])[0] == token:
            return True
        return False

    def _json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def do_GET(self) -> None:
        if not self._auth_ok():
            self._json({"error": "unauthorized"}, 401)
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        srv = self.server_ref

        if path in ("/", "/health"):
            diag = Diagnostics(srv.config, getattr(srv, "llm", None)).run()
            self._json({"status": "ok" if diag["ok"] else "degraded", "version": "2.0.0",
                        "uptime_s": round(time.time() - srv.started_at, 1), "diagnostics": diag})
        elif path == "/config":
            self._json(srv.config.as_dict(mask_secrets=True))
        elif path == "/history":
            qs = urllib.parse.parse_qs(parsed.query)
            limit = int(qs.get("limit", ["50"])[0])
            hist = getattr(srv, "history_provider", lambda n: [])  # type: ignore
            try:
                self._json({"history": hist(limit)})
            except Exception as exc:
                self._json({"error": str(exc)}, 500)
        elif path == "/tools":
            tools = getattr(srv, "tools_provider", lambda: [])  # type: ignore
            try:
                self._json({"tools": tools()})
            except Exception as exc:
                self._json({"error": str(exc)}, 500)
        elif path == "/plugins":
            pm = getattr(srv, "plugins", None)
            self._json({"plugins": pm.status() if pm else []})
        elif path == "/audit":
            qs = urllib.parse.parse_qs(parsed.query)
            limit = int(qs.get("limit", ["20"])[0])
            journal = getattr(srv, "journal", None)
            self._json({"entries": journal.recent(limit) if journal else []})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        if not self._auth_ok():
            self._json({"error": "unauthorized"}, 401)
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        srv = self.server_ref
        body = self._body()

        if path == "/chat":
            message = str(body.get("message", "")).strip()
            if not message:
                self._json({"error": "message required"}, 400)
                return
            handler = getattr(srv, "chat_handler", None)
            if not handler:
                self._json({"error": "chat not configured"}, 503)
                return
            try:
                result = handler(message)
                self._json({"reply": result})
            except Exception as exc:
                log.exception("chat handler error")
                self._json({"error": str(exc)}, 500)
        elif path == "/command":
            tool = str(body.get("tool", "")).strip()
            args = body.get("args", {})
            handler = getattr(srv, "command_handler", None)
            if not handler or not tool:
                self._json({"error": "tool/command handler not configured"}, 400)
                return
            try:
                result = handler(tool, args if isinstance(args, dict) else {})
                self._json({"result": result})
            except Exception as exc:
                self._json({"error": str(exc)}, 500)
        elif path == "/undo":
            journal = getattr(srv, "journal", None)
            undo_mgr = getattr(srv, "undo_manager", None)
            if undo_mgr:
                self._json({"result": undo_mgr.undo_last()})
            elif journal:
                self._json({"result": "undo not configured"})
            else:
                self._json({"error": "undo unavailable"}, 503)
        else:
            self._json({"error": "not found"}, 404)


class NixiServer:
    def __init__(self, config: NixiConfig | None = None):
        self.config = config or get_config()
        self.started_at = time.time()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        # injected by NixiApp
        self.llm: Any = None
        self.chat_handler: Any = None
        self.command_handler: Any = None
        self.history_provider: Any = None
        self.tools_provider: Any = None
        self.journal: Any = None
        self.undo_manager: Any = None
        self.plugins: Any = None

    def start(self) -> str:
        if self._httpd:
            return f"already running on http://{self.config.api_host}:{self.config.api_port}"
        if not self.config.api_enabled:
            return "API disabled (set NIXI_API_ENABLED=true to enable)"
        handler = type("_BoundHandler", (_Handler,), {"server_ref": self})
        try:
            self._httpd = ThreadingHTTPServer((self.config.api_host, self.config.api_port), handler)
        except OSError as exc:
            return f"could not bind {self.config.api_host}:{self.config.api_port}: {exc}"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True, name="nixi-api")
        self._thread.start()
        url = f"http://{self.config.api_host}:{self.config.api_port}"
        log.info("API listening on %s", url)
        return f"API listening on {url}"

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        log.info("API stopped")

    @property
    def is_running(self) -> bool:
        return self._httpd is not None


def create_server(config: NixiConfig | None = None) -> NixiServer:
    return NixiServer(config)
