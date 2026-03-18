"""
Inventory & Location MCP tools (8 tools).

Inventory: get levels, get product inventory, adjust, set, activate, deactivate
Locations: get, list
"""

from __future__ import annotations

import json
import uuid

from mcp.server.fastmcp import Context, FastMCP

from client import ShopifyAdminError
from queries.inventory import (
    MUTATION_INVENTORY_ACTIVATE,
    MUTATION_INVENTORY_ADJUST,
    MUTATION_INVENTORY_DEACTIVATE,
    MUTATION_INVENTORY_SET,
    QUERY_INVENTORY_LEVELS,
    QUERY_LOCATION,
    QUERY_LOCATIONS,
    QUERY_PRODUCT_INVENTORY,
)
from safety import SafetyTier, register_safety


def register(mcp: FastMCP) -> None:
    """Register inventory and location tools."""

    from server import _check_user_errors, _error, _flatten_edges, _get_client

    register_safety("get_inventory_levels", SafetyTier.READ)
    register_safety("get_product_inventory", SafetyTier.READ)
    register_safety("adjust_inventory", SafetyTier.WRITE)
    register_safety("set_inventory", SafetyTier.WRITE)
    register_safety("activate_inventory_at_location", SafetyTier.WRITE)
    register_safety("deactivate_inventory_at_location", SafetyTier.DESTRUCTIVE)
    register_safety("get_location", SafetyTier.READ)
    register_safety("list_locations", SafetyTier.READ)

    @mcp.tool()
    async def get_inventory_levels(inventory_item_id: str, ctx: Context) -> str:
        """Get inventory levels for an inventory item across all locations.

        Args:
            inventory_item_id: Inventory item ID (numeric or GID).
                Find this via get_product (variant.inventoryItem.id).

        Returns quantities (available, committed, on_hand, etc.) at each location.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("InventoryItem", inventory_item_id)
            data = await client.graphql(QUERY_INVENTORY_LEVELS, {"inventoryItemId": gid})
            item = data.get("inventoryItem")
            if not item:
                return _error(f"Inventory item not found: {inventory_item_id}")
            item["inventoryLevels"] = _flatten_edges(item.get("inventoryLevels", {}))
            return json.dumps(item, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def get_product_inventory(product_id: str, ctx: Context) -> str:
        """Get inventory for all variants of a product across all locations.

        Args:
            product_id: Product ID (numeric or GID).

        Returns each variant with its inventory levels at each location.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Product", product_id)
            data = await client.graphql(QUERY_PRODUCT_INVENTORY, {"id": gid})
            product = data.get("product")
            if not product:
                return _error(f"Product not found: {product_id}")
            variants = _flatten_edges(product.get("variants", {}))
            for v in variants:
                inv_item = v.get("inventoryItem", {})
                if inv_item:
                    inv_item["inventoryLevels"] = _flatten_edges(
                        inv_item.get("inventoryLevels", {})
                    )
            product["variants"] = variants
            return json.dumps(product, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def adjust_inventory(
        inventory_item_id: str,
        location_id: str,
        delta: int,
        ctx: Context,
        reason: str = "correction",
        name: str = "available",
    ) -> str:
        """Adjust inventory quantity by a delta (positive or negative).

        Args:
            inventory_item_id: Inventory item ID (numeric or GID).
            location_id: Location ID (numeric or GID).
            delta: Quantity change (+5 to add, -3 to remove).
            reason: Reason for adjustment (correction, cycle_count_available,
                damaged, movement_created, movement_received, movement_canceled,
                movement_updated, other, promotion, quality_control,
                received, reservation_created, reservation_deleted,
                reservation_updated, restock, safety_stock, shrinkage).
            name: Quantity name to adjust (default: 'available').

        [SAFETY: Tier 1 — Write] Show the adjustment before executing.
        """
        try:
            client = _get_client(ctx)
            item_gid = client.normalize_gid("InventoryItem", inventory_item_id)
            loc_gid = client.normalize_gid("Location", location_id)

            data = await client.graphql(
                MUTATION_INVENTORY_ADJUST,
                {
                    "input": {
                        "reason": reason,
                        "name": name,
                        "referenceDocumentUri": f"adminagent://adjustment/{uuid.uuid4().hex[:12]}",
                        "changes": [
                            {
                                "inventoryItemId": item_gid,
                                "locationId": loc_gid,
                                "delta": delta,
                            }
                        ],
                    }
                },
            )
            err = _check_user_errors(data, "inventoryAdjustQuantities")
            if err:
                return _error(err)
            group = data.get("inventoryAdjustQuantities", {}).get("inventoryAdjustmentGroup", {})
            return json.dumps(group, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def set_inventory(
        inventory_item_id: str,
        location_id: str,
        quantity: int,
        ctx: Context,
        reason: str = "correction",
        name: str = "available",
    ) -> str:
        """Set inventory to an absolute quantity.

        Args:
            inventory_item_id: Inventory item ID (numeric or GID).
            location_id: Location ID (numeric or GID).
            quantity: Absolute quantity to set.
            reason: Reason (same options as adjust_inventory).
            name: Quantity name (default: 'available').

        [SAFETY: Tier 1 — Write] Show the new quantity before executing.
        """
        try:
            client = _get_client(ctx)
            item_gid = client.normalize_gid("InventoryItem", inventory_item_id)
            loc_gid = client.normalize_gid("Location", location_id)

            data = await client.graphql(
                MUTATION_INVENTORY_SET,
                {
                    "input": {
                        "reason": reason,
                        "name": name,
                        "referenceDocumentUri": f"adminagent://set/{uuid.uuid4().hex[:12]}",
                        "quantities": [
                            {
                                "inventoryItemId": item_gid,
                                "locationId": loc_gid,
                                "quantity": quantity,
                            }
                        ],
                    }
                },
            )
            err = _check_user_errors(data, "inventorySetQuantities")
            if err:
                return _error(err)
            group = data.get("inventorySetQuantities", {}).get("inventoryAdjustmentGroup", {})
            return json.dumps(group, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def activate_inventory_at_location(
        inventory_item_id: str,
        location_id: str,
        ctx: Context,
    ) -> str:
        """Start tracking inventory for an item at a specific location.

        Args:
            inventory_item_id: Inventory item ID (numeric or GID).
            location_id: Location ID (numeric or GID).

        [SAFETY: Tier 1 — Write]
        """
        try:
            client = _get_client(ctx)
            item_gid = client.normalize_gid("InventoryItem", inventory_item_id)
            loc_gid = client.normalize_gid("Location", location_id)
            data = await client.graphql(
                MUTATION_INVENTORY_ACTIVATE,
                {"inventoryItemId": item_gid, "locationId": loc_gid},
            )
            err = _check_user_errors(data, "inventoryActivate")
            if err:
                return _error(err)
            return json.dumps(data.get("inventoryActivate", {}).get("inventoryLevel", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def deactivate_inventory_at_location(
        inventory_level_id: str,
        ctx: Context,
    ) -> str:
        """Stop tracking inventory for an item at a location.

        Args:
            inventory_level_id: Inventory level ID (the connection between item and location).

        WARNING: This removes the inventory level. Stock data at this location will be lost.

        [SAFETY: Tier 2 — Destructive] Requires confirmation.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("InventoryLevel", inventory_level_id)
            data = await client.graphql(MUTATION_INVENTORY_DEACTIVATE, {"inventoryLevelId": gid})
            err = _check_user_errors(data, "inventoryDeactivate")
            if err:
                return _error(err)
            return json.dumps({"deactivated": True}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def get_location(location_id: str, ctx: Context) -> str:
        """Get details for a single location.

        Args:
            location_id: Location ID (numeric or GID).

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Location", location_id)
            data = await client.graphql(QUERY_LOCATION, {"id": gid})
            location = data.get("location")
            if not location:
                return _error(f"Location not found: {location_id}")
            return json.dumps(location, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def list_locations(ctx: Context, first: int = 50, after: str = "") -> str:
        """List all store locations.

        Args:
            first: Results per page (max 250, default 50).
            after: Pagination cursor.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            variables: dict = {"first": min(first, 250)}
            if after:
                variables["after"] = after
            data = await client.graphql(QUERY_LOCATIONS, variables)
            conn = data.get("locations", {})
            locations = _flatten_edges(conn)
            page_info = conn.get("pageInfo", {})
            return json.dumps(
                {
                    "locations": locations,
                    "count": len(locations),
                    "hasNextPage": page_info.get("hasNextPage", False),
                    "endCursor": page_info.get("endCursor"),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))
