"""Store, Themes, Files, Publications, and Payments (read-only) MCP tools (10 tools)."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context, FastMCP

from client import ShopifyAdminError
from queries.store import (
    MUTATION_PUBLISH_RESOURCE,
    MUTATION_UNPUBLISH_RESOURCE,
    QUERY_FILES,
    QUERY_PAYOUTS,
    QUERY_PUBLICATIONS,
    QUERY_SHOP,
    QUERY_THEMES,
)
from safety import SafetyTier, register_safety


def register(mcp: FastMCP) -> None:
    """Register store, theme, file, publication, and payment tools."""
    from server import _check_user_errors, _error, _flatten_edges, _get_client

    register_safety("get_shop", SafetyTier.READ)
    register_safety("list_themes", SafetyTier.READ)
    register_safety("list_files", SafetyTier.READ)
    register_safety("list_publications", SafetyTier.READ)
    register_safety("publish_resource", SafetyTier.WRITE)
    register_safety("unpublish_resource", SafetyTier.WRITE)
    register_safety("list_payouts", SafetyTier.READ_ONLY)

    @mcp.tool()
    async def get_shop(ctx: Context) -> str:
        """Get store information (name, domain, plan, currency, address, timezone).

        Returns store name, email, myshopify domain, primary domain, plan details,
        currency, timezone, billing address, and creation date.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            data = await client.graphql(QUERY_SHOP)
            shop = data.get("shop")
            if not shop:
                return _error("Could not retrieve shop information")
            return json.dumps(shop, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def list_themes(ctx: Context, first: int = 25) -> str:
        """List all themes (shows which is published/main).

        Args:
            first: Results per page (default 25).

        Returns themes with name, role (MAIN = published, UNPUBLISHED, DEMO).

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            data = await client.graphql(QUERY_THEMES, {"first": min(first, 250)})
            themes = _flatten_edges(data.get("themes", {}))
            return json.dumps({"themes": themes, "count": len(themes)}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def list_files(
        ctx: Context,
        query: str = "",
        first: int = 25,
        after: str = "",
    ) -> str:
        """List and search files/media in the store.

        Args:
            query: Search filter (e.g., 'media_type:IMAGE', 'filename:*logo*').
            first: Results per page (default 25).
            after: Pagination cursor.

        Returns images, videos, and generic files with URLs and metadata.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            variables: dict = {"first": min(first, 250)}
            if query:
                variables["query"] = query
            if after:
                variables["after"] = after
            data = await client.graphql(QUERY_FILES, variables)
            conn = data.get("files", {})
            files = _flatten_edges(conn)
            page_info = conn.get("pageInfo", {})
            return json.dumps(
                {
                    "files": files,
                    "count": len(files),
                    "hasNextPage": page_info.get("hasNextPage", False),
                    "endCursor": page_info.get("endCursor"),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def list_publications(ctx: Context, first: int = 25) -> str:
        """List sales channels/publications (Online Store, Shop, POS, etc.).

        Args:
            first: Results per page (default 25).

        Returns publication names and their associated apps.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            data = await client.graphql(QUERY_PUBLICATIONS, {"first": min(first, 250)})
            pubs = _flatten_edges(data.get("publications", {}))
            return json.dumps({"publications": pubs, "count": len(pubs)}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def publish_resource(
        resource_id: str,
        publication_id: str,
        ctx: Context,
    ) -> str:
        """Publish a resource (product, collection, page) to a sales channel.

        Args:
            resource_id: Resource GID (e.g., 'gid://shopify/Product/123').
            publication_id: Publication/channel GID (from list_publications).

        [SAFETY: Tier 1 — Write]
        """
        try:
            client = _get_client(ctx)
            data = await client.graphql(
                MUTATION_PUBLISH_RESOURCE,
                {"id": resource_id, "input": [{"publicationId": publication_id}]},
            )
            err = _check_user_errors(data, "publishablePublish")
            if err:
                return _error(err)
            return json.dumps({"published": True, "resourceId": resource_id}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def unpublish_resource(
        resource_id: str,
        publication_id: str,
        ctx: Context,
    ) -> str:
        """Unpublish a resource from a sales channel.

        Args:
            resource_id: Resource GID.
            publication_id: Publication/channel GID.

        [SAFETY: Tier 1 — Write]
        """
        try:
            client = _get_client(ctx)
            data = await client.graphql(
                MUTATION_UNPUBLISH_RESOURCE,
                {"id": resource_id, "input": [{"publicationId": publication_id}]},
            )
            err = _check_user_errors(data, "publishableUnpublish")
            if err:
                return _error(err)
            return json.dumps({"unpublished": True, "resourceId": resource_id}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def list_payouts(ctx: Context, first: int = 25, after: str = "") -> str:
        """List Shopify Payments payouts (READ-ONLY).

        Args:
            first: Results per page (default 25).
            after: Pagination cursor.

        Returns payout status, net/gross/fee amounts, dates, and transaction type.
        Requires read_shopify_payments_payouts scope.

        [SAFETY: Read-Only — No modifications possible]
        """
        try:
            client = _get_client(ctx)
            variables: dict = {"first": min(first, 250)}
            if after:
                variables["after"] = after
            data = await client.graphql(QUERY_PAYOUTS, variables)
            account = data.get("shopifyPaymentsAccount", {})
            conn = account.get("payouts", {})
            payouts = _flatten_edges(conn)
            page_info = conn.get("pageInfo", {})
            return json.dumps(
                {
                    "payouts": payouts,
                    "count": len(payouts),
                    "hasNextPage": page_info.get("hasNextPage", False),
                    "endCursor": page_info.get("endCursor"),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))
