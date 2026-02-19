"""OAuth callback proxy for Codex-compatible redirect URI.

The Codex OAuth app allows redirect_uri=http://localhost:1455/auth/callback.
This proxy listens on 1455 and forwards to the main app's callback.
"""

from __future__ import annotations

import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_proxy_server: HTTPServer | None = None
_proxy_thread: threading.Thread | None = None


def _make_redirect_handler(target_base: str) -> type[BaseHTTPRequestHandler]:
    """Create a handler class that redirects to target_base + /api/settings/openai-sub/callback."""

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            target = f"{target_base.rstrip('/')}/api/settings/openai-sub/callback"
            if self.path.startswith("/auth/callback"):
                query = self.path.split("?", 1)[1] if "?" in self.path else ""
                if query:
                    target = f"{target}?{query}"
            self.send_response(302)
            self.send_header("Location", target)
            self.end_headers()

        def log_message(self, format, *args):
            logger.debug("OAuth proxy %s", args[0] if args else "")

    return RedirectHandler


def start_callback_proxy(redirect_uri: str, main_app_base: str) -> bool:
    """Start the OAuth callback proxy if redirect_uri uses a different port.
    Returns True if proxy was started."""
    try:
        parsed = urlparse(redirect_uri)
        main_parsed = urlparse(main_app_base)
        redirect_port = parsed.port or (443 if parsed.scheme == "https" else 80)
        main_port = main_parsed.port or (443 if main_parsed.scheme == "https" else 80)
        if redirect_port == main_port:
            return False
        if parsed.path != "/auth/callback":
            return False
        host = parsed.hostname or "localhost"
        if host not in ("localhost", "127.0.0.1"):
            return False

        handler = _make_redirect_handler(main_app_base)
        global _proxy_server, _proxy_thread
        _proxy_server = HTTPServer((host, redirect_port), handler)
        _proxy_thread = threading.Thread(
            target=_proxy_server.serve_forever,
            name="oauth-callback-proxy",
            daemon=True,
        )
        _proxy_thread.start()
        logger.info(
            "OAuth callback proxy listening on %s:%d, forwarding to %s",
            host,
            redirect_port,
            main_app_base,
        )
        return True
    except OSError as e:
        logger.warning("Could not start OAuth callback proxy on %s: %s", redirect_uri, e)
        return False


def stop_callback_proxy() -> None:
    """Stop the OAuth callback proxy if running."""
    global _proxy_server, _proxy_thread
    if _proxy_server:
        _proxy_server.shutdown()
        _proxy_server = None
    if _proxy_thread:
        _proxy_thread.join(timeout=2)
        _proxy_thread = None
