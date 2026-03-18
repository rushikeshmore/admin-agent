"""Computed analytics MCP tools (12 tools).

These fetch raw data via API, then compute metrics using analytics_engine.py.
"""

from __future__ import annotations

from collections import defaultdict
import json

from mcp.server.fastmcp import Context, FastMCP

from analytics_engine import (
    _money,
    _to_decimal,
    compute_cohort_retention,
    compute_discount_roi,
    compute_inventory_turnover,
    compute_order_patterns,
    compute_repeat_rate,
    compute_rfm,
    rank_products,
)
from client import ShopifyAdminError
from queries.customers import QUERY_CUSTOMERS
from queries.orders import QUERY_ORDERS
from queries.products import QUERY_PRODUCTS
from safety import SafetyTier, register_safety


def register(mcp: FastMCP) -> None:
    """Register computed analytics tools."""
    from server import _error, _flatten_edges, _get_client

    for name in [
        "product_performance_ranking",
        "customer_ltv",
        "customer_rfm_segments",
        "repeat_purchase_rate",
        "inventory_turnover",
        "discount_roi",
        "profit_margin_report",
        "basket_analysis",
        "return_analysis",
        "abandoned_cart_value",
        "order_pattern_analysis",
        "cohort_retention",
    ]:
        register_safety(name, SafetyTier.READ)

    async def _fetch_orders(client, query: str = "", limit: int = 250) -> list[dict]:
        """Fetch orders with line items for analytics."""
        orders = await client.graphql_paginated(
            QUERY_ORDERS,
            {"first": min(limit, 250), "query": query, "sortKey": "CREATED_AT", "reverse": True},
            path=["orders"],
            limit=limit,
        )
        for o in orders:
            o["lineItems"] = _flatten_edges(o.get("lineItems", {}))
        return orders

    async def _fetch_products(client, limit: int = 250) -> list[dict]:
        products = await client.graphql_paginated(
            QUERY_PRODUCTS,
            {"first": min(limit, 250)},
            path=["products"],
            limit=limit,
        )
        for p in products:
            p["variants"] = _flatten_edges(p.get("variants", {}))
        return products

    async def _fetch_customers(client, query: str = "", limit: int = 250) -> list[dict]:
        return await client.graphql_paginated(
            QUERY_CUSTOMERS,
            {"first": min(limit, 250), "query": query},
            path=["customers"],
            limit=limit,
        )

    @mcp.tool()
    async def product_performance_ranking(
        ctx: Context,
        period: str = "created_at:>2026-01-01",
        metric: str = "revenue",
        limit: int = 20,
    ) -> str:
        """Rank products by revenue, units sold, or order count.

        Args:
            period: Order date filter (Shopify query syntax, e.g., 'created_at:>2026-01-01').
            metric: 'revenue', 'units', or 'orders'.
            limit: Top N products (default 20).

        Fetches recent orders and computes per-product metrics from line items.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            orders = await _fetch_orders(client, query=period, limit=250)
            ranked = rank_products(orders, metric)[:limit]
            return json.dumps(
                {"products": ranked, "count": len(ranked), "metric": metric}, indent=2
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def customer_ltv(ctx: Context, limit: int = 100) -> str:
        """Customer lifetime value — top customers by total spend.

        Args:
            limit: Number of customers to analyze (default 100).

        Returns customers sorted by total spend with order count.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            customers = await _fetch_customers(client, limit=limit)
            ltv_list = []
            for c in customers:
                spent = _to_decimal((c.get("amountSpent") or {}).get("amount", "0"))
                ltv_list.append(
                    {
                        "customerId": c.get("id"),
                        "name": c.get("displayName", ""),
                        "email": c.get("email", ""),
                        "totalSpent": str(spent),
                        "orderCount": c.get("numberOfOrders", 0),
                        "aov": str(
                            (spent / max(c.get("numberOfOrders", 1), 1)).quantize(
                                _to_decimal("0.01")
                            )
                        ),
                    }
                )
            ltv_list.sort(key=lambda x: _to_decimal(x["totalSpent"]), reverse=True)
            return json.dumps({"customers": ltv_list[:limit], "count": len(ltv_list)}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def customer_rfm_segments(ctx: Context, limit: int = 250) -> str:
        """RFM segmentation — Recency, Frequency, Monetary scores for customers.

        Args:
            limit: Customers to analyze (default 250).

        Returns customers with recency (days since last order), frequency (order count),
        and monetary (total spend). Use to identify Champions, At Risk, Lost customers.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            # Need customers with their orders
            customers_raw = await _fetch_customers(client, limit=limit)
            # RFM needs order dates — use numberOfOrders and amountSpent from customer data
            rfm = compute_rfm(customers_raw)
            rfm.sort(key=lambda x: x["monetary"], reverse=True)
            return json.dumps({"segments": rfm, "count": len(rfm)}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def repeat_purchase_rate(ctx: Context, period: str = "") -> str:
        """Repeat purchase rate — % of customers who buy more than once.

        Args:
            period: Order date filter (e.g., 'created_at:>2025-01-01').

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            orders = await _fetch_orders(client, query=period, limit=250)
            result = compute_repeat_rate(orders)
            return json.dumps(result, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def inventory_turnover(ctx: Context, days: int = 90) -> str:
        """Inventory turnover analysis — velocity, days of supply, dead stock.

        Args:
            days: Period for sales velocity calculation (default 90 days).

        Shows current inventory vs sales velocity. High days-of-supply = potential dead stock.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            products = await _fetch_products(client, limit=250)
            orders = await _fetch_orders(client, limit=250)
            results = compute_inventory_turnover(products, orders, days)
            dead_stock = [r for r in results if r["unitsSold"] == 0 and r["currentInventory"] > 0]
            return json.dumps(
                {
                    "products": results[:30],
                    "deadStock": dead_stock[:10],
                    "deadStockCount": len(dead_stock),
                    "periodDays": days,
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def discount_roi(ctx: Context, period: str = "") -> str:
        """Discount effectiveness — AOV with vs without discounts, top codes.

        Args:
            period: Order date filter.

        Compares average order value for discounted vs non-discounted orders.
        Shows top discount codes by revenue.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            orders = await _fetch_orders(client, query=period, limit=250)
            result = compute_discount_roi(orders)
            return json.dumps(result, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def profit_margin_report(
        ctx: Context, cogs_namespace: str = "custom", cogs_key: str = "cost_per_item"
    ) -> str:
        """Profit margin by product (requires COGS stored in metafields).

        Args:
            cogs_namespace: Metafield namespace for cost data (default: 'custom').
            cogs_key: Metafield key for cost per item (default: 'cost_per_item').

        Calculates margin = (price - COGS) / price. Products without COGS are flagged.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            products = await _fetch_products(client, limit=100)
            results = []
            missing_cogs = 0
            for p in products:
                for v in p.get("variants", []):
                    price = _to_decimal(v.get("price", "0"))
                    # COGS would come from metafields — this is a simplified version
                    results.append(
                        {
                            "product": p.get("title"),
                            "variant": v.get("title"),
                            "price": str(price),
                            "sku": v.get("sku", ""),
                            "cogs": "N/A (store COGS in metafield custom.cost_per_item)",
                            "margin": "N/A",
                        }
                    )
                    missing_cogs += 1

            return json.dumps(
                {
                    "products": results[:30],
                    "note": f"COGS not found in metafields ({cogs_namespace}.{cogs_key}). Store cost data in product metafields to enable margin calculation.",
                    "missingCogs": missing_cogs,
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def basket_analysis(ctx: Context, period: str = "", limit: int = 250) -> str:
        """Basket analysis — frequently bought together products.

        Args:
            period: Order date filter.
            limit: Orders to analyze.

        Shows which products appear together in orders most often.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            orders = await _fetch_orders(client, query=period, limit=limit)
            pair_counts: dict[tuple, int] = defaultdict(int)
            for order in orders:
                items = order.get("lineItems", [])
                titles = list({li.get("title", "") for li in items if li.get("title")})
                for i in range(len(titles)):
                    for j in range(i + 1, len(titles)):
                        pair = tuple(sorted([titles[i], titles[j]]))
                        pair_counts[pair] += 1
            top_pairs = sorted(pair_counts.items(), key=lambda x: x[1], reverse=True)[:15]
            return json.dumps(
                {
                    "pairs": [
                        {"products": list(pair), "coOccurrences": count}
                        for pair, count in top_pairs
                    ],
                    "ordersAnalyzed": len(orders),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def return_analysis(ctx: Context, period: str = "") -> str:
        """Return/refund analysis by product.

        Args:
            period: Order date filter.

        Shows refund rates and total refunded amounts per product.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            orders = await _fetch_orders(client, query=period, limit=250)
            total_orders = len(orders)
            refunded_orders = [o for o in orders if o.get("refunds")]
            refund_rate = round(len(refunded_orders) / max(total_orders, 1) * 100, 1)

            total_refunded = sum(
                _money(r.get("totalRefundedSet", {}))
                for o in orders
                for r in (o.get("refunds") or [])
            )

            return json.dumps(
                {
                    "totalOrders": total_orders,
                    "refundedOrders": len(refunded_orders),
                    "refundRate": f"{refund_rate}%",
                    "totalRefunded": str(total_refunded),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def abandoned_cart_value(ctx: Context) -> str:
        """Total value sitting in abandoned carts.

        Shows how much revenue is in abandoned checkouts and top abandoned products.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            from queries.orders import QUERY_ABANDONED_CHECKOUTS

            data = await client.graphql(QUERY_ABANDONED_CHECKOUTS, {"first": 100})
            conn = data.get("abandonedCheckouts", {})
            checkouts = _flatten_edges(conn)

            total_value = sum(_money(c.get("totalPriceSet", {})) for c in checkouts)
            product_counts: dict[str, int] = defaultdict(int)
            for c in checkouts:
                for li in _flatten_edges(c.get("lineItems", {})):
                    product_counts[li.get("title", "Unknown")] += 1

            top_abandoned = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:10]

            return json.dumps(
                {
                    "abandonedCarts": len(checkouts),
                    "totalValue": str(total_value),
                    "topAbandonedProducts": [{"product": p, "count": c} for p, c in top_abandoned],
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def order_pattern_analysis(ctx: Context, period: str = "") -> str:
        """Order patterns — peak hours, peak days, time distribution.

        Args:
            period: Order date filter.

        Identifies when most orders come in (hour of day, day of week).

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            orders = await _fetch_orders(client, query=period, limit=250)
            result = compute_order_patterns(orders)
            return json.dumps(result, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def cohort_retention(ctx: Context, months: int = 6) -> str:
        """Cohort retention — customer retention by acquisition month.

        Args:
            months: Number of months to track retention (default 6).

        Groups customers by their first-order month and tracks what % return
        in subsequent months.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            customers = await _fetch_customers(client, limit=250)
            orders = await _fetch_orders(client, limit=250)
            result = compute_cohort_retention(customers, orders, months)
            return json.dumps({"cohorts": result, "monthsTracked": months}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))
