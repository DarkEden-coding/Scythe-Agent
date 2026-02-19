"""OAuth 2.1 + PKCE flow for OpenAI subscription authentication."""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from urllib.parse import urlencode
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTH_BASE = "https://auth.openai.com"
TOKEN_URL = f"{AUTH_BASE}/oauth/token"
AUTH_URL = f"{AUTH_BASE}/oauth/authorize"
SCOPES = "openid profile email"  # offline_access causes invalid_scope for this OAuth app

_pkce_store: dict[str, str] = {}


def generate_pkce(state: str) -> tuple[str, str]:
    """Generate code_verifier and code_challenge for PKCE. Store verifier keyed by state."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    _pkce_store[state] = verifier
    return verifier, challenge


def consume_verifier(state: str) -> str | None:
    """Retrieve and remove code_verifier for the given state."""
    return _pkce_store.pop(state, None)


def build_auth_url(redirect_uri: str, state: str) -> str:
    """Build the OAuth authorization URL with PKCE."""
    _, challenge = generate_pkce(state)
    params = {
        "client_id": OAUTH_CLIENT_ID,
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_token(
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> dict[str, Any]:
    """Exchange authorization code for access and refresh tokens."""
    data = {
        "grant_type": "authorization_code",
        "client_id": OAUTH_CLIENT_ID,
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(TOKEN_URL, data=data)
        resp.raise_for_status()
        return resp.json()
