"""Discount MCP tools (8 tools).

Discounts: get, list, create code, create automatic, activate, deactivate, delete
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context, FastMCP

from client import ShopifyAdminError
from queries.discounts import (
    MUTATION_DISCOUNT_AUTOMATIC_ACTIVATE,
    MUTATION_DISCOUNT_AUTOMATIC_BASIC_CREATE,
    MUTATION_DISCOUNT_AUTOMATIC_DEACTIVATE,
    MUTATION_DISCOUNT_AUTOMATIC_DELETE,
    MUTATION_DISCOUNT_CODE_ACTIVATE,
    MUTATION_DISCOUNT_CODE_BASIC_CREATE,
    MUTATION_DISCOUNT_CODE_DEACTIVATE,
    MUTATION_DISCOUNT_DELETE,
    QUERY_DISCOUNT,
    QUERY_DISCOUNTS,
)
from safety import SafetyTier, register_safety


def register(mcp: FastMCP) -> None:
    """Register discount tools."""
    from server import _check_user_errors, _error, _flatten_edges, _get_client

    register_safety("get_discount", SafetyTier.READ)
    register_safety("list_discounts", SafetyTier.READ)
    register_safety("create_code_discount", SafetyTier.WRITE)
    register_safety("create_automatic_discount", SafetyTier.WRITE)
    register_safety("activate_discount", SafetyTier.WRITE)
    register_safety("deactivate_discount", SafetyTier.WRITE)
    register_safety("delete_discount", SafetyTier.DESTRUCTIVE)

    @mcp.tool()
    async def get_discount(discount_id: str, ctx: Context) -> str:
        """Get full details for a discount.

        Args:
            discount_id: Discount node ID (numeric or GID like 'gid://shopify/DiscountNode/123'
                or 'gid://shopify/DiscountCodeNode/123' or 'gid://shopify/DiscountAutomaticNode/123').

        Returns discount type, title, status, dates, usage, codes, value, and combination rules.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("DiscountNode", discount_id)
            data = await client.graphql(QUERY_DISCOUNT, {"id": gid})
            node = data.get("discountNode")
            if not node:
                return _error(f"Discount not found: {discount_id}")
            discount = node.get("discount", {})
            if "codes" in discount:
                discount["codes"] = _flatten_edges(discount.get("codes", {}))
            return json.dumps({"id": node["id"], **discount}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def list_discounts(
        ctx: Context,
        query: str = "",
        first: int = 25,
        after: str = "",
    ) -> str:
        """List and search discounts.

        Args:
            query: Shopify search filter. Examples:
                'status:active' — active discounts
                'title:*summer*' — by title
                'discount_type:code_discount' or 'discount_type:automatic_discount'
            first: Results per page (max 250, default 25).
            after: Pagination cursor.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            variables: dict = {"first": min(first, 250)}
            if query:
                variables["query"] = query
            if after:
                variables["after"] = after

            data = await client.graphql(QUERY_DISCOUNTS, variables)
            conn = data.get("discountNodes", {})
            nodes = _flatten_edges(conn)
            discounts = []
            for node in nodes:
                d = node.get("discount", {})
                d["id"] = node.get("id")
                discounts.append(d)
            page_info = conn.get("pageInfo", {})

            return json.dumps(
                {
                    "discounts": discounts,
                    "count": len(discounts),
                    "hasNextPage": page_info.get("hasNextPage", False),
                    "endCursor": page_info.get("endCursor"),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def create_code_discount(
        title: str,
        code: str,
        ctx: Context,
        discount_type: str = "percentage",
        value: str = "10",
        starts_at: str = "",
        ends_at: str = "",
        usage_limit: int = 0,
        once_per_customer: bool = False,
        minimum_subtotal: str = "",
        minimum_quantity: int = 0,
    ) -> str:
        """Create a discount code (customer enters code at checkout).

        Args:
            title: Internal discount title.
            code: The code customers enter (e.g., 'SUMMER20').
            discount_type: 'percentage' (default) or 'fixed_amount'.
            value: Discount value. For percentage: '10' = 10% off.
                For fixed_amount: '5.00' = $5 off.
            starts_at: When discount becomes active (ISO datetime, default: now).
            ends_at: When discount expires (ISO datetime, empty = no expiry).
            usage_limit: Max total uses (0 = unlimited).
            once_per_customer: Limit to one use per customer.
            minimum_subtotal: Minimum order subtotal (e.g., '50.00').
            minimum_quantity: Minimum item quantity.

        [SAFETY: Tier 1 — Write] Show discount details before creating.
        """
        try:
            client = _get_client(ctx)
            discount_input: dict = {
                "title": title,
                "code": code,
                "startsAt": starts_at or None,
                "customerSelection": {"allCustomers": True},
                "combinesWith": {
                    "orderDiscounts": False,
                    "productDiscounts": False,
                    "shippingDiscounts": True,
                },
            }

            if discount_type == "percentage":
                discount_input["customerGets"] = {
                    "value": {"percentage": float(value) / 100},
                    "items": {"all": True},
                }
            else:
                discount_input["customerGets"] = {
                    "value": {"discountAmount": {"amount": value, "appliesOnEachItem": False}},
                    "items": {"all": True},
                }

            if ends_at:
                discount_input["endsAt"] = ends_at
            if usage_limit:
                discount_input["usageLimit"] = usage_limit
            if once_per_customer:
                discount_input["appliesOncePerCustomer"] = True
            if minimum_subtotal:
                discount_input["minimumRequirement"] = {
                    "subtotal": {"greaterThanOrEqualToSubtotal": minimum_subtotal}
                }
            elif minimum_quantity:
                discount_input["minimumRequirement"] = {
                    "quantity": {"greaterThanOrEqualToQuantity": str(minimum_quantity)}
                }

            data = await client.graphql(
                MUTATION_DISCOUNT_CODE_BASIC_CREATE,
                {"basicCodeDiscount": discount_input},
            )
            err = _check_user_errors(data, "discountCodeBasicCreate")
            if err:
                return _error(err)
            node = data.get("discountCodeBasicCreate", {}).get("codeDiscountNode", {})
            return json.dumps(node, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def create_automatic_discount(
        title: str,
        ctx: Context,
        discount_type: str = "percentage",
        value: str = "10",
        starts_at: str = "",
        ends_at: str = "",
        minimum_subtotal: str = "",
        minimum_quantity: int = 0,
    ) -> str:
        """Create an automatic discount (applied automatically at checkout).

        Args:
            title: Discount title (shown to customers).
            discount_type: 'percentage' or 'fixed_amount'.
            value: Discount value (same as create_code_discount).
            starts_at: Start datetime (ISO, default: now).
            ends_at: End datetime (ISO, empty = no expiry).
            minimum_subtotal: Minimum order subtotal.
            minimum_quantity: Minimum item quantity.

        [SAFETY: Tier 1 — Write] Show discount details before creating.
        """
        try:
            client = _get_client(ctx)
            discount_input: dict = {
                "title": title,
                "startsAt": starts_at or None,
                "combinesWith": {
                    "orderDiscounts": False,
                    "productDiscounts": False,
                    "shippingDiscounts": True,
                },
            }

            if discount_type == "percentage":
                discount_input["customerGets"] = {
                    "value": {"percentage": float(value) / 100},
                    "items": {"all": True},
                }
            else:
                discount_input["customerGets"] = {
                    "value": {"discountAmount": {"amount": value, "appliesOnEachItem": False}},
                    "items": {"all": True},
                }

            if ends_at:
                discount_input["endsAt"] = ends_at
            if minimum_subtotal:
                discount_input["minimumRequirement"] = {
                    "subtotal": {"greaterThanOrEqualToSubtotal": minimum_subtotal}
                }
            elif minimum_quantity:
                discount_input["minimumRequirement"] = {
                    "quantity": {"greaterThanOrEqualToQuantity": str(minimum_quantity)}
                }

            data = await client.graphql(
                MUTATION_DISCOUNT_AUTOMATIC_BASIC_CREATE,
                {"automaticBasicDiscount": discount_input},
            )
            err = _check_user_errors(data, "discountAutomaticBasicCreate")
            if err:
                return _error(err)
            node = data.get("discountAutomaticBasicCreate", {}).get("automaticDiscountNode", {})
            return json.dumps(node, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def activate_discount(discount_id: str, ctx: Context, is_automatic: bool = False) -> str:
        """Activate a discount (make it usable).

        Args:
            discount_id: Discount ID (numeric or GID).
            is_automatic: True for automatic discounts, False for code discounts.

        [SAFETY: Tier 1 — Write]
        """
        try:
            client = _get_client(ctx)
            resource = "DiscountAutomaticNode" if is_automatic else "DiscountCodeNode"
            gid = client.normalize_gid(resource, discount_id)
            mutation = (
                MUTATION_DISCOUNT_AUTOMATIC_ACTIVATE
                if is_automatic
                else MUTATION_DISCOUNT_CODE_ACTIVATE
            )
            op_key = "discountAutomaticActivate" if is_automatic else "discountCodeActivate"

            data = await client.graphql(mutation, {"id": gid})
            err = _check_user_errors(data, op_key)
            if err:
                return _error(err)
            result_key = "automaticDiscountNode" if is_automatic else "codeDiscountNode"
            return json.dumps(data.get(op_key, {}).get(result_key, {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def deactivate_discount(
        discount_id: str, ctx: Context, is_automatic: bool = False
    ) -> str:
        """Deactivate a discount (make it unusable without deleting).

        Args:
            discount_id: Discount ID (numeric or GID).
            is_automatic: True for automatic discounts, False for code discounts.

        [SAFETY: Tier 1 — Write]
        """
        try:
            client = _get_client(ctx)
            resource = "DiscountAutomaticNode" if is_automatic else "DiscountCodeNode"
            gid = client.normalize_gid(resource, discount_id)
            mutation = (
                MUTATION_DISCOUNT_AUTOMATIC_DEACTIVATE
                if is_automatic
                else MUTATION_DISCOUNT_CODE_DEACTIVATE
            )
            op_key = "discountAutomaticDeactivate" if is_automatic else "discountCodeDeactivate"

            data = await client.graphql(mutation, {"id": gid})
            err = _check_user_errors(data, op_key)
            if err:
                return _error(err)
            result_key = "automaticDiscountNode" if is_automatic else "codeDiscountNode"
            return json.dumps(data.get(op_key, {}).get(result_key, {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def delete_discount(discount_id: str, ctx: Context, is_automatic: bool = False) -> str:
        """Delete a discount permanently.

        Args:
            discount_id: Discount ID (numeric or GID).
            is_automatic: True for automatic discounts, False for code discounts.

        WARNING: Cannot be undone.

        [SAFETY: Tier 2 — Destructive] Requires explicit user confirmation.
        """
        try:
            client = _get_client(ctx)
            resource = "DiscountAutomaticNode" if is_automatic else "DiscountCodeNode"
            gid = client.normalize_gid(resource, discount_id)
            mutation = (
                MUTATION_DISCOUNT_AUTOMATIC_DELETE if is_automatic else MUTATION_DISCOUNT_DELETE
            )
            op_key = "discountAutomaticDelete" if is_automatic else "discountCodeDelete"

            data = await client.graphql(mutation, {"id": gid})
            err = _check_user_errors(data, op_key)
            if err:
                return _error(err)
            return json.dumps({"deleted": True, "discountId": gid}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))
