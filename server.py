"""
AdminAgent — Shopify Admin MCP Server.

Sprint 1: 21 tools (17 product/collection + 1 ShopifyQL + 3 bulk ops).
Full store management via Claude + MCP.

Run via Claude Code:
    claude mcp add admin-agent /path/to/.venv/bin/python /path/to/server.py
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import Context, FastMCP

from auth import create_token_manager
from bulk import BulkOperationManager
from client import ShopifyAdminClient


@dataclass
class AppContext:
    """Lifespan context holding shared resources."""

    client: ShopifyAdminClient
    bulk: BulkOperationManager


@asynccontextmanager
async def lifespan(app: FastMCP) -> AsyncIterator[AppContext]:
    """Initialize auth, client, bulk manager. Clean up on shutdown."""
    token_manager = create_token_manager()
    client = ShopifyAdminClient.from_env(token_manager)
    bulk = BulkOperationManager(client)
    try:
        yield AppContext(client=client, bulk=bulk)
    finally:
        await client.close()


mcp = FastMCP("Shopify Admin", lifespan=lifespan)


# ─── Helpers (imported by tool modules) ───────────────────────────────────────


def _error(msg: str) -> str:
    """Return a JSON error string for tool responses."""
    return json.dumps({"error": msg})


def _get_client(ctx: Context) -> ShopifyAdminClient:
    """Extract the Shopify Admin client from MCP context."""
    return ctx.request_context.lifespan_context.client


def _get_bulk(ctx: Context) -> BulkOperationManager:
    """Extract the bulk operation manager from MCP context."""
    return ctx.request_context.lifespan_context.bulk


def _check_user_errors(result: dict, operation_key: str) -> str | None:
    """Check mutation result for userErrors. Returns error string or None."""
    op_result = result.get(operation_key, {})
    user_errors = op_result.get("userErrors", [])
    if user_errors:
        return "; ".join(e.get("message", str(e)) for e in user_errors)
    return None


def _flatten_edges(connection: dict) -> list[dict]:
    """Extract node dicts from a Relay connection's edges."""
    return [edge.get("node", {}) for edge in connection.get("edges", [])]


# ─── Register all tool modules ────────────────────────────────────────────────

from tools import register_all_tools  # noqa: E402

register_all_tools(mcp)


if __name__ == "__main__":
    mcp.run(transport="stdio")
