"""
Fulfillment, Shipping, and Returns MCP tools (8 tools).

Fulfillment: get orders, create, cancel, update tracking
Fulfillment Orders: hold, release
Returns: create, close
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context, FastMCP

from client import ShopifyAdminError
from queries.fulfillment import (
    MUTATION_FULFILLMENT_CANCEL,
    MUTATION_FULFILLMENT_CREATE,
    MUTATION_FULFILLMENT_ORDER_HOLD,
    MUTATION_FULFILLMENT_ORDER_RELEASE,
    MUTATION_FULFILLMENT_UPDATE_TRACKING,
    MUTATION_RETURN_CLOSE,
    MUTATION_RETURN_CREATE,
    QUERY_DELIVERY_PROFILES,
    QUERY_FULFILLMENT_ORDERS,
)
from safety import SafetyTier, register_safety


def register(mcp: FastMCP) -> None:
    """Register fulfillment tools."""

    from server import _check_user_errors, _error, _flatten_edges, _get_client

    register_safety("get_fulfillment_orders", SafetyTier.READ)
    register_safety("create_fulfillment", SafetyTier.WRITE)
    register_safety("cancel_fulfillment", SafetyTier.DESTRUCTIVE)
    register_safety("update_tracking", SafetyTier.WRITE)
    register_safety("hold_fulfillment_order", SafetyTier.WRITE)
    register_safety("release_fulfillment_order", SafetyTier.WRITE)
    register_safety("create_return", SafetyTier.WRITE)
    register_safety("close_return", SafetyTier.WRITE)

    @mcp.tool()
    async def get_fulfillment_orders(order_id: str, ctx: Context) -> str:
        """Get fulfillment orders for an order (what needs to be shipped).

        Args:
            order_id: Order ID (numeric or GID).

        Returns fulfillment orders with status, assigned location, line items,
        and delivery method. Each fulfillment order represents items to be
        shipped from one location.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Order", order_id)
            data = await client.graphql(QUERY_FULFILLMENT_ORDERS, {"orderId": gid})
            order = data.get("order", {})
            fos = _flatten_edges(order.get("fulfillmentOrders", {}))
            for fo in fos:
                fo["lineItems"] = _flatten_edges(fo.get("lineItems", {}))
            return json.dumps(
                {"orderId": gid, "orderName": order.get("name"), "fulfillmentOrders": fos},
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def create_fulfillment(
        fulfillment_order_id: str,
        ctx: Context,
        tracking_number: str = "",
        tracking_company: str = "",
        tracking_url: str = "",
        notify_customer: bool = True,
    ) -> str:
        """Fulfill items from a fulfillment order (mark as shipped).

        Args:
            fulfillment_order_id: Fulfillment order ID (from get_fulfillment_orders).
            tracking_number: Shipping tracking number.
            tracking_company: Carrier name (e.g., 'UPS', 'FedEx', 'USPS').
            tracking_url: Tracking URL.
            notify_customer: Send shipping notification (default: True).

        [SAFETY: Tier 1 — Write] Show what will be fulfilled before executing.
        """
        try:
            client = _get_client(ctx)
            fo_gid = client.normalize_gid("FulfillmentOrder", fulfillment_order_id)

            fulfillment_input: dict = {
                "lineItemsByFulfillmentOrder": [{"fulfillmentOrderId": fo_gid}],
                "notifyCustomer": notify_customer,
            }
            if tracking_number or tracking_company or tracking_url:
                tracking: dict = {}
                if tracking_number:
                    tracking["number"] = tracking_number
                if tracking_company:
                    tracking["company"] = tracking_company
                if tracking_url:
                    tracking["url"] = tracking_url
                fulfillment_input["trackingInfo"] = tracking

            data = await client.graphql(
                MUTATION_FULFILLMENT_CREATE, {"fulfillment": fulfillment_input}
            )
            err = _check_user_errors(data, "fulfillmentCreateV2")
            if err:
                return _error(err)
            return json.dumps(
                data.get("fulfillmentCreateV2", {}).get("fulfillment", {}), indent=2
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def cancel_fulfillment(fulfillment_id: str, ctx: Context) -> str:
        """Cancel a fulfillment (unmark as shipped).

        Args:
            fulfillment_id: Fulfillment ID (numeric or GID).

        WARNING: Only possible if the shipment hasn't been picked up by the carrier.

        [SAFETY: Tier 2 — Destructive] Requires confirmation.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Fulfillment", fulfillment_id)
            data = await client.graphql(MUTATION_FULFILLMENT_CANCEL, {"id": gid})
            err = _check_user_errors(data, "fulfillmentCancel")
            if err:
                return _error(err)
            return json.dumps(data.get("fulfillmentCancel", {}).get("fulfillment", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def update_tracking(
        fulfillment_id: str,
        ctx: Context,
        tracking_number: str = "",
        tracking_company: str = "",
        tracking_url: str = "",
        notify_customer: bool = False,
    ) -> str:
        """Update tracking information on an existing fulfillment.

        Args:
            fulfillment_id: Fulfillment ID (numeric or GID).
            tracking_number: New tracking number.
            tracking_company: New carrier name.
            tracking_url: New tracking URL.
            notify_customer: Send updated tracking notification (default: False).

        [SAFETY: Tier 1 — Write]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Fulfillment", fulfillment_id)
            tracking_input: dict = {"notifyCustomer": notify_customer}
            if tracking_number:
                tracking_input["number"] = tracking_number
            if tracking_company:
                tracking_input["company"] = tracking_company
            if tracking_url:
                tracking_input["url"] = tracking_url

            data = await client.graphql(
                MUTATION_FULFILLMENT_UPDATE_TRACKING,
                {"fulfillmentId": gid, "trackingInfoInput": tracking_input},
            )
            err = _check_user_errors(data, "fulfillmentTrackingInfoUpdateV2")
            if err:
                return _error(err)
            return json.dumps(
                data.get("fulfillmentTrackingInfoUpdateV2", {}).get("fulfillment", {}),
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def hold_fulfillment_order(
        fulfillment_order_id: str,
        reason: str,
        ctx: Context,
        reason_notes: str = "",
    ) -> str:
        """Place a hold on a fulfillment order (prevent shipping).

        Args:
            fulfillment_order_id: Fulfillment order ID.
            reason: AWAITING_PAYMENT, HIGH_RISK_OF_FRAUD, INCORRECT_ADDRESS,
                INVENTORY_OUT_OF_STOCK, OTHER.
            reason_notes: Additional notes about the hold.

        [SAFETY: Tier 1 — Write]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("FulfillmentOrder", fulfillment_order_id)
            hold_input: dict = {"reason": reason.upper()}
            if reason_notes:
                hold_input["reasonNotes"] = reason_notes

            data = await client.graphql(
                MUTATION_FULFILLMENT_ORDER_HOLD,
                {"id": gid, "fulfillmentHold": hold_input},
            )
            err = _check_user_errors(data, "fulfillmentOrderHold")
            if err:
                return _error(err)
            return json.dumps(
                data.get("fulfillmentOrderHold", {}).get("fulfillmentOrder", {}), indent=2
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def release_fulfillment_order(fulfillment_order_id: str, ctx: Context) -> str:
        """Release a hold on a fulfillment order (allow shipping to proceed).

        Args:
            fulfillment_order_id: Fulfillment order ID.

        [SAFETY: Tier 1 — Write]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("FulfillmentOrder", fulfillment_order_id)
            data = await client.graphql(MUTATION_FULFILLMENT_ORDER_RELEASE, {"id": gid})
            err = _check_user_errors(data, "fulfillmentOrderReleaseHold")
            if err:
                return _error(err)
            return json.dumps(
                data.get("fulfillmentOrderReleaseHold", {}).get("fulfillmentOrder", {}),
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def create_return(
        order_id: str,
        return_line_items_json: str,
        ctx: Context,
        notify_customer: bool = False,
    ) -> str:
        """Create a return for an order.

        Args:
            order_id: Order ID (numeric or GID).
            return_line_items_json: JSON array of return line items. Example:
                '[{"fulfillmentLineItemId": "gid://shopify/FulfillmentLineItem/123",
                  "quantity": 1, "returnReason": "SIZE_TOO_SMALL",
                  "returnReasonNote": "Need a larger size"}]'
                Return reasons: COLOR, DEFECTIVE, NOT_AS_DESCRIBED, OTHER, SIZE_TOO_LARGE,
                SIZE_TOO_SMALL, STYLE, UNWANTED, WRONG_ITEM.
            notify_customer: Send return notification (default: False).

        [SAFETY: Tier 1 — Write] Show return details before creating.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Order", order_id)
            try:
                return_items = json.loads(return_line_items_json)
            except json.JSONDecodeError as e:
                return _error(f"Invalid return_line_items_json: {e}")

            data = await client.graphql(
                MUTATION_RETURN_CREATE,
                {
                    "input": {
                        "orderId": gid,
                        "returnLineItems": return_items,
                        "notifyCustomer": notify_customer,
                    }
                },
            )
            err = _check_user_errors(data, "returnCreate")
            if err:
                return _error(err)
            return json.dumps(data.get("returnCreate", {}).get("return", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def close_return(return_id: str, ctx: Context) -> str:
        """Close a return (mark as resolved).

        Args:
            return_id: Return ID (numeric or GID).

        [SAFETY: Tier 1 — Write]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Return", return_id)
            data = await client.graphql(MUTATION_RETURN_CLOSE, {"id": gid})
            err = _check_user_errors(data, "returnClose")
            if err:
                return _error(err)
            return json.dumps(data.get("returnClose", {}).get("return", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))
