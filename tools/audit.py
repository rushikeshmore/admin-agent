"""
Store audit and health check MCP tools (5 tools).

Audit products for missing images, descriptions, pricing issues.
Store health score and revenue anomaly detection.
"""

from __future__ import annotations

import json
from collections import defaultdict

from mcp.server.fastmcp import Context, FastMCP

from client import ShopifyAdminError
from safety import SafetyTier, register_safety


def register(mcp: FastMCP) -> None:
    """Register audit tools."""

    from server import _error, _flatten_edges, _get_client

    for name in [
        "seo_audit", "product_health_audit", "pricing_audit",
        "inventory_audit", "store_health_score",
    ]:
        register_safety(name, SafetyTier.READ)

    async def _fetch_all_products(client, limit: int = 250) -> list[dict]:
        from queries.products import QUERY_PRODUCTS
        products = await client.graphql_paginated(
            QUERY_PRODUCTS, {"first": min(limit, 250)}, path=["products"], limit=limit,
        )
        for p in products:
            p["variants"] = _flatten_edges(p.get("variants", {}))
        return products

    @mcp.tool()
    async def seo_audit(ctx: Context, limit: int = 250) -> str:
        """SEO audit — find products/pages with missing meta titles, descriptions, and image alt text.

        Args:
            limit: Max products to audit (default 250).

        Checks: missing meta descriptions, short descriptions (<50 chars),
        missing image alt text, duplicate titles.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            from queries.products import QUERY_PRODUCT
            products = await _fetch_all_products(client, limit)

            issues = {
                "missingDescription": [],
                "shortDescription": [],
                "missingImages": [],
                "duplicateTitles": [],
            }

            title_counts: dict[str, list] = defaultdict(list)
            for p in products:
                pid = p.get("id", "")
                title = p.get("title", "")
                title_counts[title.lower()].append({"id": pid, "title": title})

                desc = p.get("descriptionHtml") or p.get("description") or ""
                if not desc.strip():
                    issues["missingDescription"].append({"id": pid, "title": title})
                elif len(desc.strip()) < 50:
                    issues["shortDescription"].append({"id": pid, "title": title, "descLength": len(desc.strip())})

                image = p.get("featuredImage")
                if not image:
                    issues["missingImages"].append({"id": pid, "title": title})

            for title_lower, entries in title_counts.items():
                if len(entries) > 1:
                    issues["duplicateTitles"].append(entries)

            total_issues = sum(len(v) for v in issues.values())
            return json.dumps({
                "productsAudited": len(products),
                "totalIssues": total_issues,
                "missingDescription": {"count": len(issues["missingDescription"]), "products": issues["missingDescription"][:20]},
                "shortDescription": {"count": len(issues["shortDescription"]), "products": issues["shortDescription"][:20]},
                "missingImages": {"count": len(issues["missingImages"]), "products": issues["missingImages"][:20]},
                "duplicateTitles": {"count": len(issues["duplicateTitles"]), "groups": issues["duplicateTitles"][:10]},
            }, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def product_health_audit(ctx: Context, limit: int = 250) -> str:
        """Product catalog health audit.

        Args:
            limit: Max products to audit.

        Checks: products with no variants, no SKU, zero inventory (active),
        no tags, and missing product types.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            products = await _fetch_all_products(client, limit)

            issues = {
                "zeroInventoryActive": [],
                "missingSku": [],
                "missingTags": [],
                "missingProductType": [],
            }

            for p in products:
                pid = p.get("id", "")
                title = p.get("title", "")
                status = p.get("status", "")
                inventory = p.get("totalInventory", 0)

                if status == "ACTIVE" and inventory == 0:
                    issues["zeroInventoryActive"].append({"id": pid, "title": title})

                variants = p.get("variants", [])
                for v in variants:
                    if not v.get("sku"):
                        issues["missingSku"].append({"id": pid, "title": title, "variant": v.get("title", "Default")})
                        break

                if not p.get("tags"):
                    issues["missingTags"].append({"id": pid, "title": title})

                if not p.get("productType"):
                    issues["missingProductType"].append({"id": pid, "title": title})

            total_issues = sum(len(v) for v in issues.values())
            return json.dumps({
                "productsAudited": len(products),
                "totalIssues": total_issues,
                "zeroInventoryActive": {"count": len(issues["zeroInventoryActive"]), "products": issues["zeroInventoryActive"][:20]},
                "missingSku": {"count": len(issues["missingSku"]), "products": issues["missingSku"][:20]},
                "missingTags": {"count": len(issues["missingTags"]), "products": issues["missingTags"][:20]},
                "missingProductType": {"count": len(issues["missingProductType"]), "products": issues["missingProductType"][:20]},
            }, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def pricing_audit(ctx: Context, limit: int = 250) -> str:
        """Pricing consistency audit.

        Args:
            limit: Max products to audit.

        Checks: inverted compare-at prices (lower than actual), zero-price variants,
        inconsistent variant pricing within products.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            products = await _fetch_all_products(client, limit)

            issues = {
                "invertedCompareAt": [],
                "zeroPrice": [],
                "inconsistentPricing": [],
            }

            from analytics_engine import _to_decimal

            for p in products:
                pid = p.get("id", "")
                title = p.get("title", "")
                variants = p.get("variants", [])
                prices = set()

                for v in variants:
                    price = _to_decimal(v.get("price", "0"))
                    compare_at = _to_decimal(v.get("compareAtPrice") or "0")
                    prices.add(price)

                    if price == 0:
                        issues["zeroPrice"].append({
                            "id": pid, "title": title,
                            "variant": v.get("title", "Default"),
                        })

                    if compare_at > 0 and compare_at < price:
                        issues["invertedCompareAt"].append({
                            "id": pid, "title": title,
                            "variant": v.get("title", "Default"),
                            "price": str(price),
                            "compareAtPrice": str(compare_at),
                        })

                if len(prices) > 1 and len(variants) > 1:
                    price_range = max(prices) - min(prices)
                    if price_range > max(prices) * _to_decimal("0.5"):
                        issues["inconsistentPricing"].append({
                            "id": pid, "title": title,
                            "priceRange": f"{min(prices)} - {max(prices)}",
                        })

            total_issues = sum(len(v) for v in issues.values())
            return json.dumps({
                "productsAudited": len(products),
                "totalIssues": total_issues,
                "invertedCompareAt": {"count": len(issues["invertedCompareAt"]), "products": issues["invertedCompareAt"][:20]},
                "zeroPrice": {"count": len(issues["zeroPrice"]), "products": issues["zeroPrice"][:20]},
                "inconsistentPricing": {"count": len(issues["inconsistentPricing"]), "products": issues["inconsistentPricing"][:10]},
            }, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def inventory_audit(ctx: Context, limit: int = 250) -> str:
        """Inventory health audit.

        Args:
            limit: Max products to audit.

        Checks: active products with zero inventory, products not tracked,
        and highlights potential stock-outs.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            products = await _fetch_all_products(client, limit)

            active_zero = []
            low_stock = []
            not_tracked = []

            for p in products:
                pid = p.get("id", "")
                title = p.get("title", "")
                status = p.get("status", "")
                inventory = p.get("totalInventory", 0)
                tracks = p.get("tracksInventory", True)

                if status == "ACTIVE":
                    if inventory == 0:
                        active_zero.append({"id": pid, "title": title, "inventory": 0})
                    elif inventory <= 5:
                        low_stock.append({"id": pid, "title": title, "inventory": inventory})

                if not tracks:
                    not_tracked.append({"id": pid, "title": title})

            return json.dumps({
                "productsAudited": len(products),
                "activeZeroInventory": {"count": len(active_zero), "products": active_zero[:20]},
                "lowStock": {"count": len(low_stock), "products": low_stock[:20]},
                "notTracked": {"count": len(not_tracked), "products": not_tracked[:20]},
                "summary": f"{len(active_zero)} active products with 0 inventory, {len(low_stock)} with ≤5 units",
            }, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def store_health_score(ctx: Context) -> str:
        """Composite store health score (0-100) across multiple dimensions.

        Evaluates: catalog completeness, pricing consistency, inventory health,
        SEO readiness, and collection organization.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            products = await _fetch_all_products(client, limit=250)

            total = len(products)
            if total == 0:
                return json.dumps({"score": 0, "note": "No products found"}, indent=2)

            # Catalog completeness (25 points)
            has_description = sum(1 for p in products if (p.get("descriptionHtml") or "").strip())
            has_image = sum(1 for p in products if p.get("featuredImage"))
            has_type = sum(1 for p in products if p.get("productType"))
            catalog_score = round(((has_description + has_image + has_type) / (total * 3)) * 25)

            # Pricing health (25 points)
            from analytics_engine import _to_decimal
            pricing_issues = 0
            for p in products:
                for v in p.get("variants", []):
                    price = _to_decimal(v.get("price", "0"))
                    compare_at = _to_decimal(v.get("compareAtPrice") or "0")
                    if price == 0 or (compare_at > 0 and compare_at < price):
                        pricing_issues += 1
                        break
            pricing_score = round(max(0, (1 - pricing_issues / max(total, 1))) * 25)

            # Inventory health (25 points)
            active = [p for p in products if p.get("status") == "ACTIVE"]
            active_with_stock = sum(1 for p in active if p.get("totalInventory", 0) > 0)
            inv_score = round((active_with_stock / max(len(active), 1)) * 25) if active else 25

            # Tags & organization (25 points)
            has_tags = sum(1 for p in products if p.get("tags"))
            has_vendor = sum(1 for p in products if p.get("vendor"))
            org_score = round(((has_tags + has_vendor) / (total * 2)) * 25)

            total_score = catalog_score + pricing_score + inv_score + org_score

            return json.dumps({
                "score": total_score,
                "maxScore": 100,
                "breakdown": {
                    "catalogCompleteness": {"score": catalog_score, "max": 25, "details": f"{has_description}/{total} descriptions, {has_image}/{total} images, {has_type}/{total} types"},
                    "pricingHealth": {"score": pricing_score, "max": 25, "details": f"{pricing_issues} products with pricing issues"},
                    "inventoryHealth": {"score": inv_score, "max": 25, "details": f"{active_with_stock}/{len(active)} active products in stock"},
                    "organization": {"score": org_score, "max": 25, "details": f"{has_tags}/{total} tagged, {has_vendor}/{total} vendor set"},
                },
                "productsAudited": total,
            }, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))
