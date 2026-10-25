"""Optional local HTTP API + WebSocket bridge (stdlib http.server, no FastAPI required)."""
from .app import NixiServer, create_server

__all__ = ["NixiServer", "create_server"]
