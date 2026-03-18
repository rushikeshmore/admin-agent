"""
ShopifyQL analytics MCP tool (Sprint 1 prototype — 1 tool).

Executes ShopifyQL queries against the store's analytics data.
Requires `read_reports` scope.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context, FastMCP

from client import ShopifyAdminError
from queries.analytics import QUERY_SHOPIFYQL
from safety import SafetyTier, register_safety


def register(mcp: FastMCP) -> None:
    """Register analytics tools."""

    from server import _error, _get_client

    register_safety("run_shopifyql", SafetyTier.READ)

    @mcp.tool()
    async def run_shopifyql(query: str, ctx: Context) -> str:
        """Execute a ShopifyQL query against your store's analytics data.

        Args:
            query: ShopifyQL query string. Examples:
                'FROM orders SHOW sum(net_sales) AS revenue SINCE -30d'
                'FROM orders SHOW sum(net_sales) GROUP BY day SINCE -7d'
                'FROM products SHOW sum(net_sales), sum(ordered_product_quantity) GROUP BY product_title SINCE -90d ORDER BY net_sales DESC LIMIT 10'
                'FROM orders SHOW count() GROUP BY billing_country SINCE -30d'
                'FROM orders SHOW avg(net_sales) AS aov SINCE -30d COMPARE -60d UNTIL -31d'

        Available tables: orders, products, sessions, customers, payments.
        Functions: sum(), count(), avg(), min(), max().
        Time: SINCE -Nd (relative), SINCE YYYY-MM-DD (absolute), COMPARE for periods.
        Group by: day, week, month, product_title, product_type, vendor, channel,
            billing_country, billing_city, discount_code, payment_method, etc.

        Returns tabular data (columns + rows) or parse error details.
        Note: Data has 1-3 hour lag for sales, 12-48 hours for sessions.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            data = await client.graphql(QUERY_SHOPIFYQL, {"query": query})

            result = data.get("shopifyqlQuery", {})
            typename = result.get("__typename", "")

            # Check for parse errors
            parse_errors = result.get("parseErrors", [])
            if parse_errors:
                return json.dumps(
                    {
                        "error": "ShopifyQL parse error",
                        "details": parse_errors,
                    },
                    indent=2,
                )

            # Table response (most common)
            if typename == "TableResponse":
                table_data = result.get("tableData", {})
                columns = table_data.get("columns", [])
                rows = table_data.get("rowData", [])
                return json.dumps(
                    {
                        "type": "table",
                        "columns": [c.get("name", "") for c in columns],
                        "columnTypes": [c.get("dataType", "") for c in columns],
                        "rows": rows,
                        "rowCount": len(rows),
                    },
                    indent=2,
                )

            # PolarisViz response (chart data)
            if typename == "PolarisVizResponse":
                viz_data = result.get("data", [])
                return json.dumps(
                    {"type": "chart", "data": viz_data},
                    indent=2,
                )

            return json.dumps({"type": typename, "raw": result}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))
