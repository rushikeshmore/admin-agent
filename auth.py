"""Token manager for Shopify Admin API authentication.

Supports two modes:
- Legacy custom app tokens (shpat_*): static, never expire
- OAuth client credentials (shpua_*): 24h expiry, auto-refresh
"""

from __future__ import annotations

import asyncio
import os
import time

from dotenv import load_dotenv
import httpx


class AuthError(Exception):
    """Raised when authentication fails."""


class TokenManager:
    """Manages Shopify Admin API authentication with dual-mode support."""

    def __init__(
        self,
        store: str,
        access_token: str = "",
        client_id: str = "",
        client_secret: str = "",
    ):
        """Initialize with store domain and auth credentials."""
        self.store = store
        self._access_token = access_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_expiry: float = 0.0
        self._lock = asyncio.Lock()

        if self.is_oauth and self._access_token:
            # Both legacy token and OAuth credentials provided — OAuth takes precedence.
            # Clear legacy token to avoid confusion.
            self._access_token = ""

        if not self.is_oauth and not self._access_token:
            raise AuthError(
                "No authentication configured. "
                "Set SHOPIFY_ACCESS_TOKEN (legacy) or "
                "SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET (OAuth)."
            )

    @property
    def is_oauth(self) -> bool:
        """True if using OAuth client credentials flow."""
        return bool(self._client_id and self._client_secret)

    async def get_valid_token(self) -> str:
        """Return a valid access token, refreshing if needed.

        Legacy tokens are returned directly (never expire).
        OAuth tokens are refreshed 1 hour before expiry.
        Thread-safe via asyncio.Lock.
        """
        if not self.is_oauth:
            return self._access_token

        async with self._lock:
            # Refresh if token missing or expiring within 1 hour
            buffer = 3600  # 1 hour
            if not self._access_token or time.monotonic() >= (self._token_expiry - buffer):
                await self._refresh_oauth()
            return self._access_token

    async def _refresh_oauth(self) -> None:
        """Exchange client credentials for a new access token.

        POST https://{store}.myshopify.com/admin/oauth/access_token
        Body: client_id, client_secret, grant_type=client_credentials
        Returns: access_token with 24h TTL (86,399 seconds)
        """
        url = f"https://{self.store}.myshopify.com/admin/oauth/access_token"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    url,
                    data={
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "grant_type": "client_credentials",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise AuthError(
                    f"OAuth token refresh failed ({e.response.status_code}): "
                    f"{e.response.text[:300]}"
                ) from e
            except httpx.RequestError as e:
                raise AuthError(f"OAuth token refresh connection error: {e}") from e

        data = resp.json()
        self._access_token = data.get("access_token", "")
        expires_in = data.get("expires_in", 86399)
        self._token_expiry = time.monotonic() + expires_in

        if not self._access_token:
            raise AuthError("OAuth response missing access_token")


def create_token_manager() -> TokenManager:
    """Create TokenManager from environment variables."""
    load_dotenv()

    store = os.environ.get("SHOPIFY_STORE", "")
    if not store:
        raise AuthError("SHOPIFY_STORE not set in .env")

    return TokenManager(
        store=store,
        access_token=os.environ.get("SHOPIFY_ACCESS_TOKEN", ""),
        client_id=os.environ.get("SHOPIFY_CLIENT_ID", ""),
        client_secret=os.environ.get("SHOPIFY_CLIENT_SECRET", ""),
    )
