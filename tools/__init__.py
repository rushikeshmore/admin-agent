"""Tool registration hub. Each domain module exports a register function."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register_all_tools(mcp: FastMCP) -> None:
    """Register all tool modules with the shared MCP instance."""
    from tools.products import register as register_products
    from tools.analytics import register as register_analytics
    from tools.bulk_ops import register as register_bulk_ops

    register_products(mcp)
    register_analytics(mcp)
    register_bulk_ops(mcp)
