"""Tool registration hub. Each domain module exports a register function."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register_all_tools(mcp: FastMCP) -> None:
    """Register all tool modules with the shared MCP instance."""
    from tools.analytics import register as register_analytics
    from tools.audit import register as register_audit
    from tools.bulk_ops import register as register_bulk_ops
    from tools.computed import register as register_computed
    from tools.content import register as register_content
    from tools.customers import register as register_customers
    from tools.discounts import register as register_discounts
    from tools.fulfillment import register as register_fulfillment
    from tools.inventory import register as register_inventory
    from tools.metafields import register as register_metafields
    from tools.orders import register as register_orders
    from tools.products import register as register_products
    from tools.store import register as register_store

    register_products(mcp)
    register_orders(mcp)
    register_customers(mcp)
    register_inventory(mcp)
    register_fulfillment(mcp)
    register_discounts(mcp)
    register_content(mcp)
    register_metafields(mcp)
    register_store(mcp)
    register_analytics(mcp)
    register_computed(mcp)
    register_audit(mcp)
    register_bulk_ops(mcp)
