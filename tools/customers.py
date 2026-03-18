"""
Customer MCP tools (10 tools).

Customers: get, list, create, update, set (upsert), delete, merge
Addresses: manage
Marketing: update consent (email + SMS)
Segments: list
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context, FastMCP

from client import ShopifyAdminError
from queries.customers import (
    MUTATION_CUSTOMER_CREATE,
    MUTATION_CUSTOMER_DELETE,
    MUTATION_CUSTOMER_EMAIL_MARKETING,
    MUTATION_CUSTOMER_MERGE,
    MUTATION_CUSTOMER_SMS_MARKETING,
    MUTATION_CUSTOMER_UPDATE,
    QUERY_CUSTOMER,
    QUERY_CUSTOMERS,
    QUERY_SEGMENTS,
)
from safety import SafetyTier, register_safety


def register(mcp: FastMCP) -> None:
    """Register all customer tools."""

    from server import _check_user_errors, _error, _flatten_edges, _get_client

    # ── Safety registrations ──────────────────────────────────────────────

    register_safety("get_customer", SafetyTier.READ)
    register_safety("list_customers", SafetyTier.READ)
    register_safety("create_customer", SafetyTier.WRITE)
    register_safety("update_customer", SafetyTier.WRITE)
    register_safety("set_customer", SafetyTier.WRITE)
    register_safety("delete_customer", SafetyTier.DESTRUCTIVE)
    register_safety("merge_customers", SafetyTier.DESTRUCTIVE)
    register_safety("update_marketing_consent", SafetyTier.WRITE)
    register_safety("list_segments", SafetyTier.READ)

    # ═════════════════════════════════════════════════════════════════════
    # Customer Tools (9)
    # ═════════════════════════════════════════════════════════════════════

    @mcp.tool()
    async def get_customer(customer_id: str, ctx: Context) -> str:
        """Get full details for a single customer.

        Args:
            customer_id: Customer ID (numeric or GID).

        Returns customer with name, email, phone, order count, total spent,
        addresses, recent orders, marketing consent, tax status, and metafields.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Customer", customer_id)
            data = await client.graphql(QUERY_CUSTOMER, {"id": gid})
            customer = data.get("customer")
            if not customer:
                return _error(f"Customer not found: {customer_id}")
            customer["orders"] = _flatten_edges(customer.get("orders", {}))
            customer["metafields"] = _flatten_edges(customer.get("metafields", {}))
            return json.dumps(customer, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def list_customers(
        ctx: Context,
        query: str = "",
        first: int = 25,
        after: str = "",
    ) -> str:
        """List and search customers.

        Args:
            query: Shopify search filter. Examples:
                'email:*@gmail.com' — Gmail customers
                'orders_count:>5' — repeat buyers
                'total_spent:>100' — high value
                'state:enabled' — active accounts
                'tag:vip' — by tag
                'created_at:>2026-01-01'
                'country:US'
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

            data = await client.graphql(QUERY_CUSTOMERS, variables)
            conn = data.get("customers", {})
            customers = _flatten_edges(conn)
            page_info = conn.get("pageInfo", {})

            return json.dumps(
                {
                    "customers": customers,
                    "count": len(customers),
                    "hasNextPage": page_info.get("hasNextPage", False),
                    "endCursor": page_info.get("endCursor"),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def create_customer(
        ctx: Context,
        email: str = "",
        first_name: str = "",
        last_name: str = "",
        phone: str = "",
        note: str = "",
        tags: str = "",
        addresses_json: str = "",
    ) -> str:
        """Create a new customer.

        Args:
            email: Customer email (recommended).
            first_name: First name.
            last_name: Last name.
            phone: Phone number (E.164 format, e.g., '+14155551234').
            note: Internal note about the customer.
            tags: Comma-separated tags.
            addresses_json: JSON array of address objects. Example:
                '[{"address1": "123 Main St", "city": "New York",
                  "province": "NY", "country": "US", "zip": "10001"}]'

        At least email or phone is recommended.

        [SAFETY: Tier 1 — Write] Show customer details before creating.
        """
        try:
            client = _get_client(ctx)
            customer_input: dict = {}
            if email:
                customer_input["email"] = email
            if first_name:
                customer_input["firstName"] = first_name
            if last_name:
                customer_input["lastName"] = last_name
            if phone:
                customer_input["phone"] = phone
            if note:
                customer_input["note"] = note
            if tags:
                customer_input["tags"] = [t.strip() for t in tags.split(",")]
            if addresses_json:
                try:
                    customer_input["addresses"] = json.loads(addresses_json)
                except json.JSONDecodeError as e:
                    return _error(f"Invalid addresses_json: {e}")

            if not customer_input:
                return _error("Provide at least email or phone.")

            data = await client.graphql(MUTATION_CUSTOMER_CREATE, {"input": customer_input})
            err = _check_user_errors(data, "customerCreate")
            if err:
                return _error(err)
            return json.dumps(data.get("customerCreate", {}).get("customer", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def update_customer(
        customer_id: str,
        ctx: Context,
        email: str = "",
        first_name: str = "",
        last_name: str = "",
        phone: str = "",
        note: str = "",
        tags: str = "",
    ) -> str:
        """Update an existing customer's attributes.

        Args:
            customer_id: Customer ID (numeric or GID).
            email: New email.
            first_name: New first name.
            last_name: New last name.
            phone: New phone.
            note: New internal note.
            tags: New comma-separated tags (replaces all existing).

        Only provided fields are updated.

        [SAFETY: Tier 1 — Write] Show what will change before executing.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Customer", customer_id)
            customer_input: dict = {"id": gid}

            if email:
                customer_input["email"] = email
            if first_name:
                customer_input["firstName"] = first_name
            if last_name:
                customer_input["lastName"] = last_name
            if phone:
                customer_input["phone"] = phone
            if note:
                customer_input["note"] = note
            if tags:
                customer_input["tags"] = [t.strip() for t in tags.split(",")]

            if len(customer_input) == 1:
                return _error("No fields to update.")

            data = await client.graphql(MUTATION_CUSTOMER_UPDATE, {"input": customer_input})
            err = _check_user_errors(data, "customerUpdate")
            if err:
                return _error(err)
            return json.dumps(data.get("customerUpdate", {}).get("customer", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def set_customer(
        ctx: Context,
        customer_id: str = "",
        email: str = "",
        first_name: str = "",
        last_name: str = "",
        phone: str = "",
        note: str = "",
        tags: str = "",
    ) -> str:
        """Upsert a customer (create if not exists, update if ID provided).

        Args:
            customer_id: If provided, updates existing. If empty, creates new.
            email: Customer email.
            first_name: First name.
            last_name: Last name.
            phone: Phone number.
            note: Internal note.
            tags: Comma-separated tags.

        [SAFETY: Tier 1 — Write]
        """
        try:
            client = _get_client(ctx)
            customer_input: dict = {}

            if customer_id:
                customer_input["id"] = client.normalize_gid("Customer", customer_id)
            if email:
                customer_input["email"] = email
            if first_name:
                customer_input["firstName"] = first_name
            if last_name:
                customer_input["lastName"] = last_name
            if phone:
                customer_input["phone"] = phone
            if note:
                customer_input["note"] = note
            if tags:
                customer_input["tags"] = [t.strip() for t in tags.split(",")]

            mutation = MUTATION_CUSTOMER_UPDATE if customer_id else MUTATION_CUSTOMER_CREATE
            op_key = "customerUpdate" if customer_id else "customerCreate"

            data = await client.graphql(mutation, {"input": customer_input})
            err = _check_user_errors(data, op_key)
            if err:
                return _error(err)
            return json.dumps(data.get(op_key, {}).get("customer", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def delete_customer(customer_id: str, ctx: Context) -> str:
        """Delete a customer permanently.

        Args:
            customer_id: Customer ID (numeric or GID).

        WARNING: Cannot be undone. Customer data and history will be removed.
        Orders associated with this customer are NOT deleted.

        [SAFETY: Tier 2 — Destructive] Requires explicit user confirmation.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Customer", customer_id)
            data = await client.graphql(MUTATION_CUSTOMER_DELETE, {"input": {"id": gid}})
            err = _check_user_errors(data, "customerDelete")
            if err:
                return _error(err)
            deleted_id = data.get("customerDelete", {}).get("deletedCustomerId", "")
            return json.dumps({"deleted": True, "deletedCustomerId": deleted_id}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def merge_customers(
        keep_customer_id: str,
        merge_customer_id: str,
        ctx: Context,
    ) -> str:
        """Merge two customer records into one.

        Args:
            keep_customer_id: Customer ID to KEEP (this record survives).
            merge_customer_id: Customer ID to MERGE INTO the kept record (this one is removed).

        The kept customer inherits orders, addresses, and data from the merged customer.
        WARNING: The merged customer record will be deleted.

        [SAFETY: Tier 2 — Destructive] Requires explicit user confirmation.
        """
        try:
            client = _get_client(ctx)
            keep_gid = client.normalize_gid("Customer", keep_customer_id)
            merge_gid = client.normalize_gid("Customer", merge_customer_id)
            data = await client.graphql(
                MUTATION_CUSTOMER_MERGE,
                {"customerOneId": keep_gid, "customerTwoId": merge_gid},
            )
            err = _check_user_errors(data, "customerMerge")
            if err:
                return _error(err)
            result_id = data.get("customerMerge", {}).get("resultingCustomerId", "")
            return json.dumps({"merged": True, "resultingCustomerId": result_id}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def update_marketing_consent(
        customer_id: str,
        ctx: Context,
        email_state: str = "",
        sms_state: str = "",
    ) -> str:
        """Update a customer's email and/or SMS marketing consent.

        Args:
            customer_id: Customer ID (numeric or GID).
            email_state: SUBSCRIBED, NOT_SUBSCRIBED, UNSUBSCRIBED, or PENDING.
            sms_state: SUBSCRIBED, NOT_SUBSCRIBED, UNSUBSCRIBED, or PENDING.

        At least one of email_state or sms_state must be provided.

        [SAFETY: Tier 1 — Write] Show consent changes before executing.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Customer", customer_id)
            results: list[str] = []

            if email_state:
                data = await client.graphql(
                    MUTATION_CUSTOMER_EMAIL_MARKETING,
                    {
                        "input": {
                            "customerId": gid,
                            "emailMarketingConsent": {
                                "marketingState": email_state.upper(),
                                "marketingOptInLevel": "SINGLE_OPT_IN",
                            },
                        }
                    },
                )
                err = _check_user_errors(data, "customerEmailMarketingConsentUpdate")
                if err:
                    return _error(f"Email consent failed: {err}")
                results.append(f"Email marketing: {email_state.upper()}")

            if sms_state:
                data = await client.graphql(
                    MUTATION_CUSTOMER_SMS_MARKETING,
                    {
                        "input": {
                            "customerId": gid,
                            "smsMarketingConsent": {
                                "marketingState": sms_state.upper(),
                                "marketingOptInLevel": "SINGLE_OPT_IN",
                            },
                        }
                    },
                )
                err = _check_user_errors(data, "customerSmsMarketingConsentUpdate")
                if err:
                    return _error(f"SMS consent failed: {err}")
                results.append(f"SMS marketing: {sms_state.upper()}")

            if not results:
                return _error("Provide email_state or sms_state.")

            return json.dumps({"updated": True, "changes": results}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    # ═════════════════════════════════════════════════════════════════════
    # Segments (1)
    # ═════════════════════════════════════════════════════════════════════

    @mcp.tool()
    async def list_segments(
        ctx: Context,
        first: int = 25,
        after: str = "",
    ) -> str:
        """List customer segments.

        Args:
            first: Results per page (max 250, default 25).
            after: Pagination cursor.

        Returns segments with name, query filter, and dates.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            variables: dict = {"first": min(first, 250)}
            if after:
                variables["after"] = after

            data = await client.graphql(QUERY_SEGMENTS, variables)
            conn = data.get("segments", {})
            segments = _flatten_edges(conn)
            page_info = conn.get("pageInfo", {})

            return json.dumps(
                {
                    "segments": segments,
                    "count": len(segments),
                    "hasNextPage": page_info.get("hasNextPage", False),
                    "endCursor": page_info.get("endCursor"),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))
