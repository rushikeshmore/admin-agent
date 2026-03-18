"""Order, Draft Order, and Abandoned Checkout MCP tools (17 tools).

Orders: get, list, update, cancel, close, open, capture payment, create refund, mark paid
Draft Orders: get, list, create, complete, send invoice, delete
Abandoned Checkouts: list
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context, FastMCP

from client import ShopifyAdminError
from queries.orders import (
    MUTATION_DRAFT_ORDER_COMPLETE,
    MUTATION_DRAFT_ORDER_CREATE,
    MUTATION_DRAFT_ORDER_DELETE,
    MUTATION_DRAFT_ORDER_INVOICE_SEND,
    MUTATION_ORDER_CANCEL,
    MUTATION_ORDER_CAPTURE,
    MUTATION_ORDER_CLOSE,
    MUTATION_ORDER_MARK_AS_PAID,
    MUTATION_ORDER_OPEN,
    MUTATION_ORDER_UPDATE,
    MUTATION_REFUND_CREATE,
    QUERY_ABANDONED_CHECKOUTS,
    QUERY_DRAFT_ORDER,
    QUERY_DRAFT_ORDERS,
    QUERY_ORDER,
    QUERY_ORDERS,
)
from safety import SafetyTier, register_safety


def register(mcp: FastMCP) -> None:
    """Register all order tools."""
    from server import _check_user_errors, _error, _flatten_edges, _get_client

    # ── Safety registrations ──────────────────────────────────────────────

    register_safety("get_order", SafetyTier.READ)
    register_safety("list_orders", SafetyTier.READ)
    register_safety("update_order", SafetyTier.WRITE)
    register_safety("cancel_order", SafetyTier.DESTRUCTIVE)
    register_safety("close_order", SafetyTier.WRITE)
    register_safety("open_order", SafetyTier.WRITE)
    register_safety("capture_payment", SafetyTier.WRITE)
    register_safety("create_refund", SafetyTier.DESTRUCTIVE)
    register_safety("mark_order_paid", SafetyTier.WRITE)
    register_safety("get_draft_order", SafetyTier.READ)
    register_safety("list_draft_orders", SafetyTier.READ)
    register_safety("create_draft_order", SafetyTier.WRITE)
    register_safety("complete_draft_order", SafetyTier.WRITE)
    register_safety("send_draft_invoice", SafetyTier.WRITE)
    register_safety("delete_draft_order", SafetyTier.DESTRUCTIVE)
    register_safety("list_abandoned_checkouts", SafetyTier.READ)

    # ═════════════════════════════════════════════════════════════════════
    # Order Tools (9)
    # ═════════════════════════════════════════════════════════════════════

    @mcp.tool()
    async def get_order(order_id: str, ctx: Context) -> str:
        """Get full details for a single order.

        Args:
            order_id: Order ID (numeric or GID).

        Returns order with financial/fulfillment status, line items, customer,
        shipping address, transactions, refunds, fulfillments, and risk level.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Order", order_id)
            data = await client.graphql(QUERY_ORDER, {"id": gid})
            order = data.get("order")
            if not order:
                return _error(f"Order not found: {order_id}")
            order["lineItems"] = _flatten_edges(order.get("lineItems", {}))
            return json.dumps(order, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def list_orders(
        ctx: Context,
        query: str = "",
        first: int = 25,
        after: str = "",
        sort_key: str = "CREATED_AT",
        reverse: bool = True,
    ) -> str:
        """List and search orders.

        Args:
            query: Shopify search filter. Examples:
                'financial_status:paid' — paid orders
                'fulfillment_status:unfulfilled' — unfulfilled
                'status:open' — open orders
                'created_at:>2026-01-01' — by date
                'risk_level:high' — high risk
                'tag:vip' — by tag
                'email:customer@example.com' — by customer email
            first: Results per page (max 250, default 25).
            after: Pagination cursor.
            sort_key: CREATED_AT, UPDATED_AT, TOTAL_PRICE, ORDER_NUMBER, CUSTOMER_NAME.
            reverse: True for newest first (default).

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            variables: dict = {
                "first": min(first, 250),
                "sortKey": sort_key,
                "reverse": reverse,
            }
            if query:
                variables["query"] = query
            if after:
                variables["after"] = after

            data = await client.graphql(QUERY_ORDERS, variables)
            orders_conn = data.get("orders", {})
            orders = _flatten_edges(orders_conn)
            for o in orders:
                o["lineItems"] = _flatten_edges(o.get("lineItems", {}))
            page_info = orders_conn.get("pageInfo", {})

            return json.dumps(
                {
                    "orders": orders,
                    "count": len(orders),
                    "hasNextPage": page_info.get("hasNextPage", False),
                    "endCursor": page_info.get("endCursor"),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def update_order(
        order_id: str,
        ctx: Context,
        note: str = "",
        tags: str = "",
        email: str = "",
        phone: str = "",
    ) -> str:
        """Update an order's editable attributes.

        Args:
            order_id: Order ID (numeric or GID).
            note: Internal order note.
            tags: Comma-separated tags (replaces all existing).
            email: Customer email on the order.
            phone: Customer phone on the order.

        Only note, tags, email, and phone can be updated on existing orders.

        [SAFETY: Tier 1 — Write] Show what will change before executing.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Order", order_id)
            order_input: dict = {"id": gid}

            if note:
                order_input["note"] = note
            if tags:
                order_input["tags"] = [t.strip() for t in tags.split(",")]
            if email:
                order_input["email"] = email
            if phone:
                order_input["phone"] = phone

            if len(order_input) == 1:
                return _error("No fields to update.")

            data = await client.graphql(MUTATION_ORDER_UPDATE, {"input": order_input})
            err = _check_user_errors(data, "orderUpdate")
            if err:
                return _error(err)

            return json.dumps(data.get("orderUpdate", {}).get("order", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def cancel_order(
        order_id: str,
        reason: str,
        ctx: Context,
        notify_customer: bool = False,
        refund: bool = True,
        restock: bool = True,
    ) -> str:
        """Cancel an order.

        Args:
            order_id: Order ID (numeric or GID).
            reason: CUSTOMER, DECLINED, FRAUD, INVENTORY, OTHER, STAFF.
            notify_customer: Send cancellation email to customer (default: False).
            refund: Issue a refund (default: True).
            restock: Restock inventory (default: True).

        WARNING: This cannot be easily undone. The order will be marked as cancelled.

        [SAFETY: Tier 2 — Destructive] Requires explicit user confirmation.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Order", order_id)
            data = await client.graphql(
                MUTATION_ORDER_CANCEL,
                {
                    "orderId": gid,
                    "reason": reason.upper(),
                    "notifyCustomer": notify_customer,
                    "refund": refund,
                    "restock": restock,
                },
            )
            errors = data.get("orderCancel", {}).get("orderCancelUserErrors", [])
            if errors:
                msgs = "; ".join(e.get("message", str(e)) for e in errors)
                return _error(msgs)

            return json.dumps({"cancelled": True, "orderId": gid}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def close_order(order_id: str, ctx: Context) -> str:
        """Close/archive an order.

        Args:
            order_id: Order ID (numeric or GID).

        [SAFETY: Tier 1 — Write]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Order", order_id)
            data = await client.graphql(MUTATION_ORDER_CLOSE, {"input": {"id": gid}})
            err = _check_user_errors(data, "orderClose")
            if err:
                return _error(err)
            return json.dumps(data.get("orderClose", {}).get("order", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def open_order(order_id: str, ctx: Context) -> str:
        """Reopen a closed/archived order.

        Args:
            order_id: Order ID (numeric or GID).

        [SAFETY: Tier 1 — Write]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Order", order_id)
            data = await client.graphql(MUTATION_ORDER_OPEN, {"input": {"id": gid}})
            err = _check_user_errors(data, "orderOpen")
            if err:
                return _error(err)
            return json.dumps(data.get("orderOpen", {}).get("order", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def capture_payment(
        order_id: str,
        amount: str,
        ctx: Context,
        currency: str = "USD",
    ) -> str:
        """Capture an authorized payment on an order.

        Args:
            order_id: Order ID (numeric or GID).
            amount: Amount to capture (e.g., '49.99').
            currency: Currency code (default: USD).

        [SAFETY: Tier 1 — Write] Show amount before executing.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Order", order_id)
            data = await client.graphql(
                MUTATION_ORDER_CAPTURE,
                {
                    "input": {
                        "id": gid,
                        "amount": amount,
                        "currency": currency.upper(),
                    }
                },
            )
            err = _check_user_errors(data, "orderCapture")
            if err:
                return _error(err)
            return json.dumps(data.get("orderCapture", {}).get("transaction", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def create_refund(
        order_id: str,
        ctx: Context,
        note: str = "",
        notify_customer: bool = False,
        refund_line_items_json: str = "",
    ) -> str:
        """Create a refund for an order.

        Args:
            order_id: Order ID (numeric or GID).
            note: Reason for the refund.
            notify_customer: Send refund notification email (default: False).
            refund_line_items_json: JSON array of line items to refund. Example:
                '[{"lineItemId": "gid://shopify/LineItem/123", "quantity": 1}]'
                If empty, processes a full refund.

        WARNING: Refunds are permanent and will transfer money back to the customer.

        [SAFETY: Tier 2 — Destructive] Requires explicit user confirmation.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Order", order_id)
            refund_input: dict = {"orderId": gid, "notify": notify_customer}
            if note:
                refund_input["note"] = note
            if refund_line_items_json:
                try:
                    refund_input["refundLineItems"] = json.loads(refund_line_items_json)
                except json.JSONDecodeError as e:
                    return _error(f"Invalid refund_line_items_json: {e}")

            data = await client.graphql(MUTATION_REFUND_CREATE, {"input": refund_input})
            err = _check_user_errors(data, "refundCreate")
            if err:
                return _error(err)
            return json.dumps(data.get("refundCreate", {}).get("refund", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def mark_order_paid(order_id: str, ctx: Context) -> str:
        """Mark an order as paid (for manual payment methods).

        Args:
            order_id: Order ID (numeric or GID).

        [SAFETY: Tier 1 — Write]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Order", order_id)
            data = await client.graphql(MUTATION_ORDER_MARK_AS_PAID, {"input": {"id": gid}})
            err = _check_user_errors(data, "orderMarkAsPaid")
            if err:
                return _error(err)
            return json.dumps(data.get("orderMarkAsPaid", {}).get("order", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    # ═════════════════════════════════════════════════════════════════════
    # Draft Order Tools (6)
    # ═════════════════════════════════════════════════════════════════════

    @mcp.tool()
    async def get_draft_order(draft_order_id: str, ctx: Context) -> str:
        """Get full details for a draft order.

        Args:
            draft_order_id: Draft order ID (numeric or GID).

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("DraftOrder", draft_order_id)
            data = await client.graphql(QUERY_DRAFT_ORDER, {"id": gid})
            draft = data.get("draftOrder")
            if not draft:
                return _error(f"Draft order not found: {draft_order_id}")
            draft["lineItems"] = _flatten_edges(draft.get("lineItems", {}))
            return json.dumps(draft, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def list_draft_orders(
        ctx: Context,
        query: str = "",
        first: int = 25,
        after: str = "",
    ) -> str:
        """List and search draft orders.

        Args:
            query: Shopify search filter (e.g., 'status:open', 'tag:wholesale').
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

            data = await client.graphql(QUERY_DRAFT_ORDERS, variables)
            conn = data.get("draftOrders", {})
            drafts = _flatten_edges(conn)
            page_info = conn.get("pageInfo", {})

            return json.dumps(
                {
                    "draftOrders": drafts,
                    "count": len(drafts),
                    "hasNextPage": page_info.get("hasNextPage", False),
                    "endCursor": page_info.get("endCursor"),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def create_draft_order(
        line_items_json: str,
        ctx: Context,
        email: str = "",
        note: str = "",
        tags: str = "",
        customer_id: str = "",
    ) -> str:
        """Create a new draft order.

        Args:
            line_items_json: JSON array of line items. Example:
                '[{"variantId": "gid://shopify/ProductVariant/123", "quantity": 2}]'
                Or custom items:
                '[{"title": "Custom Item", "quantity": 1,
                  "originalUnitPrice": "50.00"}]'
            email: Customer email for the draft order.
            note: Internal note.
            tags: Comma-separated tags.
            customer_id: Associate with existing customer (numeric or GID).

        [SAFETY: Tier 1 — Write] Show line items before creating.
        """
        try:
            client = _get_client(ctx)
            try:
                line_items = json.loads(line_items_json)
            except json.JSONDecodeError as e:
                return _error(f"Invalid line_items_json: {e}")

            draft_input: dict = {"lineItems": line_items}
            if email:
                draft_input["email"] = email
            if note:
                draft_input["note"] = note
            if tags:
                draft_input["tags"] = [t.strip() for t in tags.split(",")]
            if customer_id:
                draft_input["customerId"] = client.normalize_gid("Customer", customer_id)

            data = await client.graphql(MUTATION_DRAFT_ORDER_CREATE, {"input": draft_input})
            err = _check_user_errors(data, "draftOrderCreate")
            if err:
                return _error(err)
            return json.dumps(data.get("draftOrderCreate", {}).get("draftOrder", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def complete_draft_order(
        draft_order_id: str,
        ctx: Context,
        payment_pending: bool = False,
    ) -> str:
        """Convert a draft order into a real order.

        Args:
            draft_order_id: Draft order ID (numeric or GID).
            payment_pending: If True, creates order with payment pending status.

        [SAFETY: Tier 1 — Write] Confirm before completing.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("DraftOrder", draft_order_id)
            data = await client.graphql(
                MUTATION_DRAFT_ORDER_COMPLETE,
                {"id": gid, "paymentPending": payment_pending},
            )
            err = _check_user_errors(data, "draftOrderComplete")
            if err:
                return _error(err)
            return json.dumps(data.get("draftOrderComplete", {}).get("draftOrder", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def send_draft_invoice(
        draft_order_id: str,
        ctx: Context,
        to: str = "",
        subject: str = "",
        custom_message: str = "",
    ) -> str:
        """Send an invoice email for a draft order.

        Args:
            draft_order_id: Draft order ID (numeric or GID).
            to: Override recipient email (uses draft order email if empty).
            subject: Custom email subject line.
            custom_message: Custom message body.

        [SAFETY: Tier 1 — Write] Sends an email to the customer.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("DraftOrder", draft_order_id)
            variables: dict = {"id": gid}
            email_input: dict = {}
            if to:
                email_input["to"] = to
            if subject:
                email_input["subject"] = subject
            if custom_message:
                email_input["customMessage"] = custom_message
            if email_input:
                variables["email"] = email_input

            data = await client.graphql(MUTATION_DRAFT_ORDER_INVOICE_SEND, variables)
            err = _check_user_errors(data, "draftOrderInvoiceSend")
            if err:
                return _error(err)
            return json.dumps(
                {
                    "sent": True,
                    "draftOrder": data.get("draftOrderInvoiceSend", {}).get("draftOrder", {}),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def delete_draft_order(draft_order_id: str, ctx: Context) -> str:
        """Delete a draft order permanently.

        Args:
            draft_order_id: Draft order ID (numeric or GID).

        WARNING: Cannot be undone. Only draft orders (not converted to orders) can be deleted.

        [SAFETY: Tier 2 — Destructive] Requires explicit user confirmation.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("DraftOrder", draft_order_id)
            data = await client.graphql(MUTATION_DRAFT_ORDER_DELETE, {"input": {"id": gid}})
            err = _check_user_errors(data, "draftOrderDelete")
            if err:
                return _error(err)
            return json.dumps(
                {
                    "deleted": True,
                    "deletedId": data.get("draftOrderDelete", {}).get("deletedId", ""),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    # ═════════════════════════════════════════════════════════════════════
    # Abandoned Checkouts (1)
    # ═════════════════════════════════════════════════════════════════════

    @mcp.tool()
    async def list_abandoned_checkouts(
        ctx: Context,
        query: str = "",
        first: int = 25,
        after: str = "",
    ) -> str:
        """List abandoned checkouts (customers who started checkout but didn't complete).

        Args:
            query: Shopify search filter.
            first: Results per page (max 250, default 25).
            after: Pagination cursor.

        Returns checkouts with customer info, line items, total price, and recovery URL.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            variables: dict = {"first": min(first, 250)}
            if query:
                variables["query"] = query
            if after:
                variables["after"] = after

            data = await client.graphql(QUERY_ABANDONED_CHECKOUTS, variables)
            conn = data.get("abandonedCheckouts", {})
            checkouts = _flatten_edges(conn)
            for c in checkouts:
                c["lineItems"] = _flatten_edges(c.get("lineItems", {}))
            page_info = conn.get("pageInfo", {})

            return json.dumps(
                {
                    "abandonedCheckouts": checkouts,
                    "count": len(checkouts),
                    "hasNextPage": page_info.get("hasNextPage", False),
                    "endCursor": page_info.get("endCursor"),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))
