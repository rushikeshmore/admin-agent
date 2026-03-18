"""ShopifyQL analytics MCP tools (15 tools).

14 convenience wrappers for common analytics queries + 1 raw ShopifyQL executor.
Requires `read_reports` scope.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context, FastMCP

from client import ShopifyAdminError
from queries.analytics import QUERY_SHOPIFYQL
from safety import SafetyTier, register_safety


def _run_shopifyql_query(client, query: str):
    """Helper to execute ShopifyQL and format result."""
    return client.graphql(QUERY_SHOPIFYQL, {"query": query})


def _format_shopifyql_result(data: dict) -> str:
    result = data.get("shopifyqlQuery", {})
    typename = result.get("__typename", "")
    parse_errors = result.get("parseErrors", [])
    if parse_errors:
        return json.dumps({"error": "ShopifyQL parse error", "details": parse_errors}, indent=2)
    if typename == "TableResponse":
        td = result.get("tableData", {})
        columns = td.get("columns", [])
        rows = td.get("rowData", [])
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
    if typename == "PolarisVizResponse":
        return json.dumps({"type": "chart", "data": result.get("data", [])}, indent=2)
    return json.dumps({"type": typename, "raw": result}, indent=2)


def register(mcp: FastMCP) -> None:
    """Register all analytics tools."""
    from server import _error, _get_client

    for name in [
        "run_shopifyql",
        "revenue_dashboard",
        "revenue_by_product",
        "revenue_by_channel",
        "revenue_by_geography",
        "revenue_by_discount",
        "customer_acquisition",
        "conversion_funnel",
        "product_sales_detail",
        "time_analysis",
        "yoy_comparison",
        "custom_date_comparison",
        "channel_attribution",
        "shipping_analysis",
        "sales_trend",
    ]:
        register_safety(name, SafetyTier.READ)

    async def _exec(client, query: str) -> str:
        data = await client.graphql(QUERY_SHOPIFYQL, {"query": query})
        return _format_shopifyql_result(data)

    @mcp.tool()
    async def run_shopifyql(query: str, ctx: Context) -> str:
        """Execute any ShopifyQL query against your store's analytics data.

        Args:
            query: ShopifyQL query string. Examples:
                'FROM orders SHOW sum(net_sales) AS revenue SINCE -30d'
                'FROM products SHOW sum(net_sales) GROUP BY product_title SINCE -90d ORDER BY net_sales DESC LIMIT 10'
                'FROM orders SHOW count() GROUP BY billing_country SINCE -30d'
                'FROM orders SHOW avg(net_sales) AS aov SINCE -30d COMPARE -60d UNTIL -31d'

        Tables: orders, products, sessions. Functions: sum, count, avg, min, max.
        Time: SINCE -Nd/-Nm/-Ny, UNTIL, COMPARE. GROUP BY: day, week, month, product_title, etc.
        Note: Data has 1-3 hour lag for sales, 12-48 hours for sessions.

        [SAFETY: Tier 0 — Read]
        """
        try:
            return await _exec(_get_client(ctx), query)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def revenue_dashboard(
        ctx: Context,
        period: str = "-30d",
        compare: bool = False,
    ) -> str:
        """Revenue overview — total sales, orders, AOV for a period.

        Args:
            period: Time range (e.g., '-7d', '-30d', '-90d', '-1y', or '2026-01-01').
            compare: If True, compare against previous equal period.

        [SAFETY: Tier 0 — Read]
        """
        try:
            q = f"FROM orders SHOW sum(net_sales) AS revenue, count() AS orders, avg(net_sales) AS aov SINCE {period}"
            if compare:
                q += f" COMPARE {period}"
            return await _exec(_get_client(ctx), q)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def revenue_by_product(
        ctx: Context,
        period: str = "-30d",
        limit: int = 20,
    ) -> str:
        """Revenue breakdown by product.

        Args:
            period: Time range.
            limit: Max products to return (default 20).

        [SAFETY: Tier 0 — Read]
        """
        try:
            q = f"FROM products SHOW sum(net_sales) AS revenue, sum(ordered_product_quantity) AS units GROUP BY product_title SINCE {period} ORDER BY revenue DESC LIMIT {limit}"
            return await _exec(_get_client(ctx), q)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def revenue_by_channel(ctx: Context, period: str = "-30d") -> str:
        """Revenue breakdown by sales channel.

        Args:
            period: Time range.

        [SAFETY: Tier 0 — Read]
        """
        try:
            q = f"FROM orders SHOW sum(net_sales) AS revenue, count() AS orders GROUP BY channel SINCE {period} ORDER BY revenue DESC"
            return await _exec(_get_client(ctx), q)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def revenue_by_geography(
        ctx: Context, period: str = "-30d", group_by: str = "billing_country"
    ) -> str:
        """Revenue breakdown by geography.

        Args:
            period: Time range.
            group_by: 'billing_country', 'billing_city', or 'billing_region'.

        [SAFETY: Tier 0 — Read]
        """
        try:
            q = f"FROM orders SHOW sum(net_sales) AS revenue, count() AS orders GROUP BY {group_by} SINCE {period} ORDER BY revenue DESC LIMIT 30"
            return await _exec(_get_client(ctx), q)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def revenue_by_discount(ctx: Context, period: str = "-30d") -> str:
        """Revenue breakdown by discount code.

        Args:
            period: Time range.

        [SAFETY: Tier 0 — Read]
        """
        try:
            q = f"FROM orders SHOW sum(net_sales) AS revenue, count() AS orders, avg(net_sales) AS aov GROUP BY discount_code SINCE {period} ORDER BY revenue DESC LIMIT 20"
            return await _exec(_get_client(ctx), q)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def customer_acquisition(ctx: Context, period: str = "-30d") -> str:
        """New vs returning customer metrics.

        Args:
            period: Time range.

        [SAFETY: Tier 0 — Read]
        """
        try:
            q = f"FROM orders SHOW sum(net_sales) AS revenue, count() AS orders GROUP BY customer_type SINCE {period}"
            return await _exec(_get_client(ctx), q)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def conversion_funnel(ctx: Context, period: str = "-30d") -> str:
        """Conversion funnel — sessions, add-to-cart, checkout, purchase rates.

        Args:
            period: Time range.

        Uses ShopifyQL products table which has built-in conversion metrics.
        Note: Session data has 12-48 hour lag.

        [SAFETY: Tier 0 — Read]
        """
        try:
            q = f"FROM products SHOW sum(sessions) AS sessions, sum(cart_additions) AS add_to_cart, sum(checkouts) AS checkouts, sum(orders) AS purchases SINCE {period}"
            return await _exec(_get_client(ctx), q)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def product_sales_detail(
        ctx: Context,
        period: str = "-30d",
        limit: int = 30,
    ) -> str:
        """Detailed product sales — units, revenue, returns, conversion rate.

        Args:
            period: Time range.
            limit: Max products (default 30).

        [SAFETY: Tier 0 — Read]
        """
        try:
            q = f"FROM products SHOW product_title, sum(net_sales) AS revenue, sum(ordered_product_quantity) AS units, sum(returned_quantity) AS returns, sum(sessions) AS views GROUP BY product_title SINCE {period} ORDER BY revenue DESC LIMIT {limit}"
            return await _exec(_get_client(ctx), q)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def time_analysis(
        ctx: Context,
        period: str = "-30d",
        group_by: str = "day",
        metric: str = "net_sales",
    ) -> str:
        """Revenue/orders over time (daily, weekly, monthly, hourly).

        Args:
            period: Time range.
            group_by: 'hour', 'day', 'week', or 'month'.
            metric: 'net_sales', 'gross_sales', 'orders' (count).

        [SAFETY: Tier 0 — Read]
        """
        try:
            show = f"sum({metric}) AS value" if metric != "orders" else "count() AS value"
            q = f"FROM orders SHOW {show} GROUP BY {group_by} SINCE {period}"
            return await _exec(_get_client(ctx), q)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def yoy_comparison(
        ctx: Context,
        metric: str = "net_sales",
        period: str = "-30d",
    ) -> str:
        """Year-over-year comparison for any metric.

        Args:
            metric: 'net_sales', 'gross_sales', 'orders'.
            period: Current period (e.g., '-30d'). Compared against same period last year.

        [SAFETY: Tier 0 — Read]
        """
        try:
            show = f"sum({metric}) AS value" if metric != "orders" else "count() AS value"
            q = f"FROM orders SHOW {show} GROUP BY month SINCE {period} COMPARE -1y"
            return await _exec(_get_client(ctx), q)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def custom_date_comparison(
        current_start: str,
        current_end: str,
        compare_start: str,
        compare_end: str,
        ctx: Context,
    ) -> str:
        """Compare two custom date ranges (e.g., Black Friday 2025 vs 2024).

        Args:
            current_start: Start date (YYYY-MM-DD).
            current_end: End date (YYYY-MM-DD).
            compare_start: Comparison start date.
            compare_end: Comparison end date.

        [SAFETY: Tier 0 — Read]
        """
        try:
            q = f"FROM orders SHOW sum(net_sales) AS revenue, count() AS orders, avg(net_sales) AS aov SINCE {current_start} UNTIL {current_end} COMPARE {compare_start} UNTIL {compare_end}"
            return await _exec(_get_client(ctx), q)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def channel_attribution(ctx: Context, period: str = "-30d") -> str:
        """Traffic and revenue by UTM source/medium.

        Args:
            period: Time range.

        Note: ~60% of traffic may show as 'Direct' due to tracking limitations.

        [SAFETY: Tier 0 — Read]
        """
        try:
            q = f"FROM orders SHOW sum(net_sales) AS revenue, count() AS orders GROUP BY referrer_source SINCE {period} ORDER BY revenue DESC LIMIT 20"
            return await _exec(_get_client(ctx), q)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def shipping_analysis(ctx: Context, period: str = "-30d") -> str:
        """Shipping revenue and methods analysis.

        Args:
            period: Time range.

        [SAFETY: Tier 0 — Read]
        """
        try:
            q = f"FROM orders SHOW sum(shipping) AS shipping_revenue, count() AS orders GROUP BY shipping_method SINCE {period} ORDER BY shipping_revenue DESC"
            return await _exec(_get_client(ctx), q)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def sales_trend(
        ctx: Context,
        period: str = "-90d",
        group_by: str = "week",
    ) -> str:
        """Sales trend over time — revenue, orders, and AOV by period.

        Args:
            period: Time range (default -90d for trend visibility).
            group_by: 'day', 'week', or 'month'.

        [SAFETY: Tier 0 — Read]
        """
        try:
            q = f"FROM orders SHOW sum(net_sales) AS revenue, count() AS orders, avg(net_sales) AS aov GROUP BY {group_by} SINCE {period}"
            return await _exec(_get_client(ctx), q)
        except ShopifyAdminError as e:
            return _error(str(e))
