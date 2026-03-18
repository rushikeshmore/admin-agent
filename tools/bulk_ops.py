"""
Bulk operation MCP tools (3 tools).

Submit async queries, check status, cancel operations.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context, FastMCP

from client import ShopifyAdminError
from safety import SafetyTier, register_safety


def register(mcp: FastMCP) -> None:
    """Register bulk operation tools."""

    from server import _error, _get_bulk

    register_safety("run_bulk_query", SafetyTier.BULK)
    register_safety("check_bulk_operation", SafetyTier.READ)
    register_safety("cancel_bulk_operation", SafetyTier.DESTRUCTIVE)

    @mcp.tool()
    async def run_bulk_query(query: str, ctx: Context) -> str:
        """Submit a bulk GraphQL query for async execution.

        Args:
            query: GraphQL query to run in bulk. Must NOT include pagination
                arguments (first, after) — Shopify handles pagination internally.
                Example: '{ products { edges { node { id title } } } }'

        Bulk operations run server-side and bypass rate limits.
        Use for large data exports (all products, all orders, etc.).
        Only ONE bulk query can run at a time per store.

        Returns the operation ID and status. Use check_bulk_operation
        to poll for completion and get the download URL.

        [SAFETY: Tier 3 — Bulk] Confirm the query scope before executing.
        """
        try:
            bulk = _get_bulk(ctx)
            result = await bulk.submit(query)
            return json.dumps(
                {
                    "submitted": True,
                    "bulkOperation": result,
                    "next_step": "Use check_bulk_operation with the operation ID to poll for completion.",
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def check_bulk_operation(operation_id: str, ctx: Context) -> str:
        """Check the status of a running bulk operation.

        Args:
            operation_id: Bulk operation GID (e.g., 'gid://shopify/BulkOperation/123').

        Returns status (CREATED, RUNNING, COMPLETED, FAILED, CANCELED),
        object count, file size, and download URL (when completed).

        [SAFETY: Tier 0 — Read]
        """
        try:
            bulk = _get_bulk(ctx)
            result = await bulk.poll_status(operation_id)
            return json.dumps(result, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def cancel_bulk_operation(operation_id: str, ctx: Context) -> str:
        """Cancel a running bulk operation.

        Args:
            operation_id: Bulk operation GID.

        [SAFETY: Tier 2 — Destructive] Requires confirmation.
        """
        try:
            bulk = _get_bulk(ctx)
            result = await bulk.cancel(operation_id)
            return json.dumps({"canceled": True, "bulkOperation": result}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))
