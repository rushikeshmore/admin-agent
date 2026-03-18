"""Shopify Admin GraphQL API client.

Cost-based rate limiting, cursor pagination, GID normalization.
Modeled on partner-agent's ShopifyPartnerClient.
"""

from __future__ import annotations

import asyncio
import os
import time

from dotenv import load_dotenv
import httpx

from auth import AuthError, TokenManager, create_token_manager

API_VERSION = "2026-04"


class ShopifyAdminError(Exception):
    """Raised when a Shopify Admin API call fails."""

    def __init__(self, status_code: int, message: str) -> None:
        """Initialize with HTTP status code and error message."""
        self.status_code = status_code
        super().__init__(f"Shopify Admin API {status_code}: {message}")


class ShopifyAdminClient:
    """Async client for the Shopify Admin GraphQL API."""

    def __init__(
        self,
        store: str,
        token_manager: TokenManager,
        api_version: str = API_VERSION,
        debug: bool = False,
    ):
        """Initialize with store domain, token manager, and optional config."""
        self.store = store
        self.endpoint = f"https://{store}.myshopify.com/admin/api/{api_version}/graphql.json"
        self._token_manager = token_manager
        self._debug = debug
        self._client: httpx.AsyncClient | None = None

        # Cost-based rate limiting state
        self._cost_available: float = 1000.0
        self._cost_restore_rate: float = 100.0  # Standard plan default
        self._last_cost_update: float = time.monotonic()

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-init shared httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close httpx client. Called in lifespan teardown."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def graphql(self, query: str, variables: dict | None = None) -> dict:
        """Execute a single GraphQL request with cost-based rate limiting.

        Returns the `data` dict from the response.
        Raises ShopifyAdminError on HTTP errors, GraphQL errors, or rate limits.
        """
        client = await self._get_client()
        token = await self._token_manager.get_valid_token()

        headers = {"X-Shopify-Access-Token": token}
        if self._debug:
            headers["Shopify-GraphQL-Cost-Debug"] = "1"

        body: dict = {"query": query}
        if variables:
            body["variables"] = variables

        # Exponential backoff on 429
        for attempt in range(4):
            try:
                resp = await client.post(self.endpoint, json=body, headers=headers)
                resp.raise_for_status()
                break
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < 3:
                    wait = 2**attempt  # 1s, 2s, 4s
                    await asyncio.sleep(wait)
                    # Refresh token in case it expired during wait
                    token = await self._token_manager.get_valid_token()
                    headers["X-Shopify-Access-Token"] = token
                    continue
                text = e.response.text[:300]
                raise ShopifyAdminError(e.response.status_code, text) from e
            except httpx.RequestError as e:
                raise ShopifyAdminError(0, f"Connection error: {e}") from e

        result = resp.json()

        # GraphQL errors inside HTTP 200
        if "errors" in result:
            messages = [err.get("message", str(err)) for err in result["errors"]]
            raise ShopifyAdminError(200, "; ".join(messages))

        # Track cost budget from extensions
        self._update_cost_budget(result)

        return result.get("data", {})

    def _update_cost_budget(self, result: dict) -> None:
        """Update rate limit state from response extensions."""
        extensions = result.get("extensions", {})
        cost = extensions.get("cost", {})
        throttle = cost.get("throttleStatus", {})

        if "currentlyAvailable" in throttle:
            self._cost_available = float(throttle["currentlyAvailable"])
        if "restoreRate" in throttle:
            self._cost_restore_rate = float(throttle["restoreRate"])
        self._last_cost_update = time.monotonic()

    async def _wait_for_budget(self, estimated_cost: float = 50.0) -> None:
        """Sleep if cost budget is too low for the next request."""
        now = time.monotonic()
        elapsed = now - self._last_cost_update
        restored = elapsed * self._cost_restore_rate
        self._cost_available = min(self._cost_available + restored, 1000.0)
        self._last_cost_update = now

        if self._cost_available < estimated_cost:
            wait = (estimated_cost - self._cost_available) / self._cost_restore_rate
            await asyncio.sleep(min(wait, 10.0))

    async def graphql_paginated(
        self,
        query: str,
        variables: dict,
        path: list[str],
        limit: int = 0,
    ) -> list:
        """Follow Relay cursor pagination until all results or limit.

        Args:
            query: GraphQL query with $first/$after variables and pageInfo.
            variables: Initial variables dict (must include "first").
            path: Keys to navigate to the connection (e.g., ["products"]).
            limit: Max results (0 = all).

        Returns list of node dicts.
        """
        all_nodes: list = []
        has_next = True

        while has_next:
            await self._wait_for_budget()
            data = await self.graphql(query, variables)

            # Navigate to connection object
            connection = data
            for key in path:
                connection = connection.get(key, {})

            edges = connection.get("edges", [])
            for edge in edges:
                all_nodes.append(edge.get("node", {}))
                if limit and len(all_nodes) >= limit:
                    return all_nodes[:limit]

            page_info = connection.get("pageInfo", {})
            has_next = page_info.get("hasNextPage", False)
            if has_next:
                end_cursor = page_info.get("endCursor")
                if end_cursor:
                    variables["after"] = end_cursor
                else:
                    break

        return all_nodes

    @staticmethod
    def normalize_gid(resource_type: str, id_input: str | int) -> str:
        """Normalize any ID format to Shopify GID.

        normalize_gid("Product", "123") -> "gid://shopify/Product/123"
        normalize_gid("Product", "gid://shopify/Product/123") -> unchanged
        """
        id_str = str(id_input)
        if id_str.startswith("gid://"):
            return id_str
        return f"gid://shopify/{resource_type}/{id_str}"

    @classmethod
    def from_env(cls, token_manager: TokenManager | None = None) -> ShopifyAdminClient:
        """Create client from environment variables."""
        load_dotenv()

        store = os.environ.get("SHOPIFY_STORE", "")
        if not store:
            raise AuthError("SHOPIFY_STORE not set in .env")

        if token_manager is None:
            token_manager = create_token_manager()

        api_version = os.environ.get("SHOPIFY_API_VERSION", API_VERSION)
        debug = os.environ.get("SHOPIFY_DEBUG", "0") == "1"

        return cls(
            store=store,
            token_manager=token_manager,
            api_version=api_version,
            debug=debug,
        )
