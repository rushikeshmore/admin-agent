"""Metafield & Metaobject MCP tools (8 tools).

Metafields: get (on any resource), set, delete, list definitions
Metaobjects: get, list, create, update, delete
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context, FastMCP

from client import ShopifyAdminError
from queries.metafields import (
    MUTATION_METAFIELDS_DELETE,
    MUTATION_METAFIELDS_SET,
    MUTATION_METAOBJECT_CREATE,
    MUTATION_METAOBJECT_DELETE,
    QUERY_METAFIELD_DEFINITIONS,
    QUERY_METAFIELDS,
    QUERY_METAOBJECT,
    QUERY_METAOBJECTS,
)
from safety import SafetyTier, register_safety


def register(mcp: FastMCP) -> None:
    """Register metafield and metaobject tools."""
    from server import _check_user_errors, _error, _flatten_edges, _get_client

    register_safety("get_metafields", SafetyTier.READ)
    register_safety("set_metafields", SafetyTier.WRITE)
    register_safety("delete_metafield", SafetyTier.DESTRUCTIVE)
    register_safety("list_metafield_definitions", SafetyTier.READ)
    register_safety("get_metaobject", SafetyTier.READ)
    register_safety("list_metaobjects", SafetyTier.READ)
    register_safety("create_metaobject", SafetyTier.WRITE)
    register_safety("delete_metaobject", SafetyTier.DESTRUCTIVE)

    @mcp.tool()
    async def get_metafields(
        owner_id: str,
        ctx: Context,
        namespace: str = "",
        first: int = 50,
    ) -> str:
        """Get metafields for any resource (product, order, customer, etc.).

        Args:
            owner_id: Resource GID (e.g., 'gid://shopify/Product/123').
            namespace: Filter by namespace (optional).
            first: Results per page (default 50).

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            variables: dict = {"ownerId": owner_id, "first": min(first, 250)}
            if namespace:
                variables["namespace"] = namespace
            data = await client.graphql(QUERY_METAFIELDS, variables)
            node = data.get("node", {})
            metafields = _flatten_edges(node.get("metafields", {}))
            return json.dumps({"metafields": metafields, "count": len(metafields)}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def set_metafields(metafields_json: str, ctx: Context) -> str:
        """Create or update metafields on any resource.

        Args:
            metafields_json: JSON array of metafield objects. Example:
                '[{"ownerId": "gid://shopify/Product/123",
                  "namespace": "custom", "key": "color", "type": "single_line_text_field",
                  "value": "Blue"}]'

                Types: single_line_text_field, multi_line_text_field, number_integer,
                number_decimal, boolean, json, date, url, color, weight, dimension, etc.

        WARNING: If updating a product via productSet and you omit existing metafields,
        they will be SILENTLY DELETED. Always include all existing metafields.

        [SAFETY: Tier 1 — Write] Show metafields before setting.
        """
        try:
            client = _get_client(ctx)
            try:
                metafields = json.loads(metafields_json)
            except json.JSONDecodeError as e:
                return _error(f"Invalid metafields_json: {e}")

            data = await client.graphql(MUTATION_METAFIELDS_SET, {"metafields": metafields})
            err = _check_user_errors(data, "metafieldsSet")
            if err:
                return _error(err)
            result = data.get("metafieldsSet", {}).get("metafields", [])
            return json.dumps({"metafields": result, "count": len(result)}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def delete_metafield(metafield_id: str, ctx: Context) -> str:
        """Delete a metafield.

        Args:
            metafield_id: Metafield GID (e.g., 'gid://shopify/Metafield/123').

        WARNING: Cannot be undone. The metafield type also cannot be changed after deletion
        if you recreate it with the same namespace/key — you must use the same type.

        [SAFETY: Tier 2 — Destructive] Requires confirmation.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Metafield", metafield_id)
            data = await client.graphql(MUTATION_METAFIELDS_DELETE, {"input": {"id": gid}})
            err = _check_user_errors(data, "metafieldDelete")
            if err:
                return _error(err)
            return json.dumps(
                {
                    "deleted": True,
                    "deletedId": data.get("metafieldDelete", {}).get("deletedId", ""),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def list_metafield_definitions(
        owner_type: str,
        ctx: Context,
        first: int = 50,
    ) -> str:
        """List metafield definitions for a resource type.

        Args:
            owner_type: PRODUCT, PRODUCTVARIANT, COLLECTION, CUSTOMER, ORDER,
                SHOP, ARTICLE, BLOG, PAGE, etc.
            first: Results per page (default 50).

        Shows all defined metafield schemas (namespace, key, type, validations).

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            data = await client.graphql(
                QUERY_METAFIELD_DEFINITIONS,
                {"ownerType": owner_type.upper(), "first": min(first, 250)},
            )
            defs = _flatten_edges(data.get("metafieldDefinitions", {}))
            return json.dumps({"definitions": defs, "count": len(defs)}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def get_metaobject(metaobject_id: str, ctx: Context) -> str:
        """Get a metaobject entry.

        Args:
            metaobject_id: Metaobject GID.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Metaobject", metaobject_id)
            data = await client.graphql(QUERY_METAOBJECT, {"id": gid})
            obj = data.get("metaobject")
            if not obj:
                return _error(f"Metaobject not found: {metaobject_id}")
            return json.dumps(obj, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def list_metaobjects(
        metaobject_type: str,
        ctx: Context,
        first: int = 25,
        after: str = "",
    ) -> str:
        """List metaobject entries of a given type.

        Args:
            metaobject_type: The metaobject type handle (e.g., 'lookbook', 'faq').
            first: Results per page (default 25).
            after: Pagination cursor.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            variables: dict = {"type": metaobject_type, "first": min(first, 250)}
            if after:
                variables["after"] = after
            data = await client.graphql(QUERY_METAOBJECTS, variables)
            conn = data.get("metaobjects", {})
            objects = _flatten_edges(conn)
            page_info = conn.get("pageInfo", {})
            return json.dumps(
                {
                    "metaobjects": objects,
                    "count": len(objects),
                    "hasNextPage": page_info.get("hasNextPage", False),
                    "endCursor": page_info.get("endCursor"),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def create_metaobject(
        metaobject_type: str,
        handle: str,
        fields_json: str,
        ctx: Context,
    ) -> str:
        """Create a metaobject entry.

        Args:
            metaobject_type: Type handle (e.g., 'lookbook').
            handle: Unique handle for this entry.
            fields_json: JSON array of field objects. Example:
                '[{"key": "title", "value": "Summer Lookbook"},
                  {"key": "image", "value": "gid://shopify/MediaImage/123"}]'

        [SAFETY: Tier 1 — Write]
        """
        try:
            client = _get_client(ctx)
            try:
                fields = json.loads(fields_json)
            except json.JSONDecodeError as e:
                return _error(f"Invalid fields_json: {e}")

            data = await client.graphql(
                MUTATION_METAOBJECT_CREATE,
                {"metaobject": {"type": metaobject_type, "handle": handle, "fields": fields}},
            )
            err = _check_user_errors(data, "metaobjectCreate")
            if err:
                return _error(err)
            return json.dumps(data.get("metaobjectCreate", {}).get("metaobject", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def delete_metaobject(metaobject_id: str, ctx: Context) -> str:
        """Delete a metaobject entry.

        Args:
            metaobject_id: Metaobject GID.

        WARNING: Cannot be undone.

        [SAFETY: Tier 2 — Destructive] Requires confirmation.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Metaobject", metaobject_id)
            data = await client.graphql(MUTATION_METAOBJECT_DELETE, {"id": gid})
            err = _check_user_errors(data, "metaobjectDelete")
            if err:
                return _error(err)
            return json.dumps(
                {
                    "deleted": True,
                    "deletedId": data.get("metaobjectDelete", {}).get("deletedId", ""),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))
