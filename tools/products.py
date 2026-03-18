"""Product & Collection MCP tools (17 tools).

Products: get, list, create, update, delete, set (upsert), duplicate
Variants: create, update, delete, manage options
Collections: get, list, create, update, delete, manage products
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context, FastMCP

from client import ShopifyAdminError
from queries.products import (
    MUTATION_COLLECTION_ADD_PRODUCTS,
    MUTATION_COLLECTION_CREATE,
    MUTATION_COLLECTION_DELETE,
    MUTATION_COLLECTION_REMOVE_PRODUCTS,
    MUTATION_COLLECTION_UPDATE,
    MUTATION_PRODUCT_CREATE,
    MUTATION_PRODUCT_DELETE,
    MUTATION_PRODUCT_DUPLICATE,
    MUTATION_PRODUCT_UPDATE,
    MUTATION_VARIANTS_BULK_CREATE,
    MUTATION_VARIANTS_BULK_DELETE,
    MUTATION_VARIANTS_BULK_UPDATE,
    QUERY_COLLECTION,
    QUERY_COLLECTIONS,
    QUERY_PRODUCT,
    QUERY_PRODUCTS,
)
from safety import SafetyTier, register_safety


def register(mcp: FastMCP) -> None:
    """Register all product and collection tools."""
    # Import server helpers inside register to avoid circular imports
    from server import _check_user_errors, _error, _flatten_edges, _get_client

    # ── Safety registrations ──────────────────────────────────────────────

    register_safety("get_product", SafetyTier.READ)
    register_safety("list_products", SafetyTier.READ)
    register_safety("create_product", SafetyTier.WRITE)
    register_safety("update_product", SafetyTier.WRITE)
    register_safety("delete_product", SafetyTier.DESTRUCTIVE)
    register_safety("set_product", SafetyTier.WRITE)
    register_safety("duplicate_product", SafetyTier.WRITE)
    register_safety("create_variants", SafetyTier.WRITE)
    register_safety("update_variants", SafetyTier.WRITE)
    register_safety("delete_variants", SafetyTier.DESTRUCTIVE)
    register_safety("manage_product_options", SafetyTier.WRITE)
    register_safety("get_collection", SafetyTier.READ)
    register_safety("list_collections", SafetyTier.READ)
    register_safety("create_collection", SafetyTier.WRITE)
    register_safety("update_collection", SafetyTier.WRITE)
    register_safety("delete_collection", SafetyTier.DESTRUCTIVE)
    register_safety("manage_collection_products", SafetyTier.WRITE)

    # ═════════════════════════════════════════════════════════════════════
    # Product Tools (11)
    # ═════════════════════════════════════════════════════════════════════

    @mcp.tool()
    async def get_product(product_id: str, ctx: Context) -> str:
        """Get full details for a single product.

        Args:
            product_id: Product ID (numeric like '123' or GID like 'gid://shopify/Product/123').

        Returns product with title, description, status, variants (prices, SKUs),
        images, options, tags, vendor, inventory count, and SEO fields.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Product", product_id)
            data = await client.graphql(QUERY_PRODUCT, {"id": gid})
            product = data.get("product")
            if not product:
                return _error(f"Product not found: {product_id}")
            product["variants"] = _flatten_edges(product.get("variants", {}))
            product["images"] = _flatten_edges(product.get("images", {}))
            return json.dumps(product, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def list_products(
        ctx: Context,
        query: str = "",
        first: int = 25,
        after: str = "",
    ) -> str:
        """List and search products.

        Args:
            query: Shopify search syntax filter. Examples:
                'status:active' — only active products
                'title:*shirt*' — title contains "shirt"
                'vendor:Nike' — by vendor
                'product_type:Shoes' — by type
                'inventory_total:>0' — in stock
                'created_at:>2026-01-01' — created after date
                Combine: 'status:active vendor:Nike'
            first: Number of products per page (max 250, default 25).
            after: Pagination cursor from a previous response.

        Returns list of products with basic info and first 3 variants.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            variables: dict = {"first": min(first, 250)}
            if query:
                variables["query"] = query
            if after:
                variables["after"] = after

            data = await client.graphql(QUERY_PRODUCTS, variables)
            products_conn = data.get("products", {})
            products = _flatten_edges(products_conn)
            for p in products:
                p["variants"] = _flatten_edges(p.get("variants", {}))

            page_info = products_conn.get("pageInfo", {})
            return json.dumps(
                {
                    "products": products,
                    "count": len(products),
                    "hasNextPage": page_info.get("hasNextPage", False),
                    "endCursor": page_info.get("endCursor"),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def create_product(
        title: str,
        ctx: Context,
        description_html: str = "",
        product_type: str = "",
        vendor: str = "",
        tags: str = "",
        status: str = "DRAFT",
        variants_json: str = "",
    ) -> str:
        """Create a new product.

        Args:
            title: Product title (required).
            description_html: Product description (HTML allowed).
            product_type: Product type (e.g., 'T-Shirt', 'Shoes').
            vendor: Vendor/brand name.
            tags: Comma-separated tags (e.g., 'sale, summer, new').
            status: ACTIVE, DRAFT, or ARCHIVED (default: DRAFT).
            variants_json: Optional JSON array of variant objects. Example:
                '[{"price": "29.99", "sku": "TSHIRT-L", "options": ["Large"]}]'

        Returns the created product with ID, handle, and variants.

        [SAFETY: Tier 1 — Write] Show what will be created before executing.
        """
        try:
            client = _get_client(ctx)
            product_input: dict = {"title": title, "status": status.upper()}
            if description_html:
                product_input["descriptionHtml"] = description_html
            if product_type:
                product_input["productType"] = product_type
            if vendor:
                product_input["vendor"] = vendor
            if tags:
                product_input["tags"] = [t.strip() for t in tags.split(",")]
            if variants_json:
                try:
                    product_input["variants"] = json.loads(variants_json)
                except json.JSONDecodeError as e:
                    return _error(f"Invalid variants_json: {e}")

            data = await client.graphql(MUTATION_PRODUCT_CREATE, {"input": product_input})
            err = _check_user_errors(data, "productCreate")
            if err:
                return _error(err)

            product = data.get("productCreate", {}).get("product", {})
            product["variants"] = _flatten_edges(product.get("variants", {}))
            return json.dumps(product, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def update_product(
        product_id: str,
        ctx: Context,
        title: str = "",
        description_html: str = "",
        product_type: str = "",
        vendor: str = "",
        tags: str = "",
        status: str = "",
    ) -> str:
        """Update an existing product's attributes.

        Args:
            product_id: Product ID (numeric or GID).
            title: New title (leave empty to keep current).
            description_html: New description.
            product_type: New product type.
            vendor: New vendor.
            tags: New comma-separated tags (replaces all existing tags).
            status: ACTIVE, DRAFT, or ARCHIVED.

        Only provided fields are updated. Empty strings are ignored.
        Returns the updated product.

        [SAFETY: Tier 1 — Write] Show what will change before executing.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Product", product_id)
            product_input: dict = {"id": gid}

            if title:
                product_input["title"] = title
            if description_html:
                product_input["descriptionHtml"] = description_html
            if product_type:
                product_input["productType"] = product_type
            if vendor:
                product_input["vendor"] = vendor
            if tags:
                product_input["tags"] = [t.strip() for t in tags.split(",")]
            if status:
                product_input["status"] = status.upper()

            if len(product_input) == 1:
                return _error("No fields to update. Provide at least one field.")

            data = await client.graphql(MUTATION_PRODUCT_UPDATE, {"input": product_input})
            err = _check_user_errors(data, "productUpdate")
            if err:
                return _error(err)

            product = data.get("productUpdate", {}).get("product", {})
            product["variants"] = _flatten_edges(product.get("variants", {}))
            return json.dumps(product, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def delete_product(product_id: str, ctx: Context) -> str:
        """Delete a product permanently.

        Args:
            product_id: Product ID (numeric or GID).

        WARNING: This cannot be undone. The product and all its variants
        will be permanently removed.

        [SAFETY: Tier 2 — Destructive] Requires explicit user confirmation.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Product", product_id)
            data = await client.graphql(MUTATION_PRODUCT_DELETE, {"input": {"id": gid}})
            err = _check_user_errors(data, "productDelete")
            if err:
                return _error(err)

            deleted_id = data.get("productDelete", {}).get("deletedProductId", "")
            return json.dumps({"deleted": True, "deletedProductId": deleted_id}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def set_product(
        title: str,
        ctx: Context,
        product_id: str = "",
        description_html: str = "",
        product_type: str = "",
        vendor: str = "",
        tags: str = "",
        status: str = "ACTIVE",
        variants_json: str = "",
    ) -> str:
        """Upsert a product (create if not exists, update if exists).

        Args:
            title: Product title (required).
            product_id: If provided, updates existing product. If empty, creates new.
            description_html: Product description.
            product_type: Product type.
            vendor: Vendor name.
            tags: Comma-separated tags.
            status: ACTIVE, DRAFT, or ARCHIVED.
            variants_json: JSON array of variant objects.

        Useful for syncing products from external systems.

        [SAFETY: Tier 1 — Write] Show what will change before executing.
        """
        try:
            client = _get_client(ctx)
            product_input: dict = {"title": title, "status": status.upper()}

            if product_id:
                product_input["id"] = client.normalize_gid("Product", product_id)
            if description_html:
                product_input["descriptionHtml"] = description_html
            if product_type:
                product_input["productType"] = product_type
            if vendor:
                product_input["vendor"] = vendor
            if tags:
                product_input["tags"] = [t.strip() for t in tags.split(",")]
            if variants_json:
                try:
                    product_input["variants"] = json.loads(variants_json)
                except json.JSONDecodeError as e:
                    return _error(f"Invalid variants_json: {e}")

            mutation = MUTATION_PRODUCT_UPDATE if product_id else MUTATION_PRODUCT_CREATE
            op_key = "productUpdate" if product_id else "productCreate"

            data = await client.graphql(mutation, {"input": product_input})
            err = _check_user_errors(data, op_key)
            if err:
                return _error(err)

            product = data.get(op_key, {}).get("product", {})
            product["variants"] = _flatten_edges(product.get("variants", {}))
            return json.dumps(product, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def duplicate_product(
        product_id: str,
        new_title: str,
        ctx: Context,
    ) -> str:
        """Duplicate an existing product with a new title.

        Args:
            product_id: Product ID to duplicate (numeric or GID).
            new_title: Title for the duplicated product.

        Creates a copy with the same variants, images, and attributes.

        [SAFETY: Tier 1 — Write] Show what will be created before executing.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Product", product_id)
            data = await client.graphql(
                MUTATION_PRODUCT_DUPLICATE,
                {"productId": gid, "newTitle": new_title},
            )
            err = _check_user_errors(data, "productDuplicate")
            if err:
                return _error(err)

            product = data.get("productDuplicate", {}).get("newProduct", {})
            return json.dumps(product, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    # ═════════════════════════════════════════════════════════════════════
    # Variant Tools (4)
    # ═════════════════════════════════════════════════════════════════════

    @mcp.tool()
    async def create_variants(
        product_id: str,
        variants_json: str,
        ctx: Context,
    ) -> str:
        """Create new variants for an existing product.

        Args:
            product_id: Product ID (numeric or GID).
            variants_json: JSON array of variant objects. Example:
                '[{"price": "29.99", "sku": "TSHIRT-L",
                  "optionValues": [{"optionName": "Size", "name": "Large"}]}]'

        [SAFETY: Tier 1 — Write] Show variants to be created before executing.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Product", product_id)
            try:
                variants = json.loads(variants_json)
            except json.JSONDecodeError as e:
                return _error(f"Invalid variants_json: {e}")

            data = await client.graphql(
                MUTATION_VARIANTS_BULK_CREATE,
                {"productId": gid, "variants": variants},
            )
            err = _check_user_errors(data, "productVariantsBulkCreate")
            if err:
                return _error(err)

            created = data.get("productVariantsBulkCreate", {}).get("productVariants", [])
            return json.dumps({"variants": created, "count": len(created)}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def update_variants(
        product_id: str,
        variants_json: str,
        ctx: Context,
    ) -> str:
        """Update existing variants for a product.

        Args:
            product_id: Product ID (numeric or GID).
            variants_json: JSON array of variant objects with 'id' field. Example:
                '[{"id": "gid://shopify/ProductVariant/456", "price": "34.99"}]'

        Each variant object must include its 'id'. Only provided fields are updated.

        [SAFETY: Tier 1 — Write] Show changes before executing.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Product", product_id)
            try:
                variants = json.loads(variants_json)
            except json.JSONDecodeError as e:
                return _error(f"Invalid variants_json: {e}")

            data = await client.graphql(
                MUTATION_VARIANTS_BULK_UPDATE,
                {"productId": gid, "variants": variants},
            )
            err = _check_user_errors(data, "productVariantsBulkUpdate")
            if err:
                return _error(err)

            updated = data.get("productVariantsBulkUpdate", {}).get("productVariants", [])
            return json.dumps({"variants": updated, "count": len(updated)}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def delete_variants(
        product_id: str,
        variant_ids: str,
        ctx: Context,
    ) -> str:
        """Delete variants from a product.

        Args:
            product_id: Product ID (numeric or GID).
            variant_ids: Comma-separated variant IDs to delete.
                Example: '456,789' or 'gid://shopify/ProductVariant/456,gid://shopify/ProductVariant/789'

        WARNING: This cannot be undone.

        [SAFETY: Tier 2 — Destructive] Requires explicit user confirmation.
        """
        try:
            client = _get_client(ctx)
            product_gid = client.normalize_gid("Product", product_id)
            ids = [
                client.normalize_gid("ProductVariant", vid.strip())
                for vid in variant_ids.split(",")
                if vid.strip()
            ]
            if not ids:
                return _error("No variant IDs provided")

            data = await client.graphql(
                MUTATION_VARIANTS_BULK_DELETE,
                {"productId": product_gid, "variantsIds": ids},
            )
            err = _check_user_errors(data, "productVariantsBulkDelete")
            if err:
                return _error(err)

            return json.dumps({"deleted": True, "count": len(ids)}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def manage_product_options(
        product_id: str,
        options_json: str,
        ctx: Context,
    ) -> str:
        """View or update a product's options (Size, Color, Material, etc.).

        Args:
            product_id: Product ID (numeric or GID).
            options_json: JSON array of option objects. Example:
                '[{"name": "Size", "values": ["Small", "Medium", "Large"]},
                  {"name": "Color", "values": ["Red", "Blue"]}]'

        Note: Changing options may affect existing variants. Use with care.
        This updates options via productUpdate mutation.

        [SAFETY: Tier 1 — Write] Show changes before executing.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Product", product_id)
            try:
                options = json.loads(options_json)
            except json.JSONDecodeError as e:
                return _error(f"Invalid options_json: {e}")

            data = await client.graphql(
                MUTATION_PRODUCT_UPDATE,
                {"input": {"id": gid, "options": options}},
            )
            err = _check_user_errors(data, "productUpdate")
            if err:
                return _error(err)

            product = data.get("productUpdate", {}).get("product", {})
            return json.dumps(product, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    # ═════════════════════════════════════════════════════════════════════
    # Collection Tools (6)
    # ═════════════════════════════════════════════════════════════════════

    @mcp.tool()
    async def get_collection(collection_id: str, ctx: Context) -> str:
        """Get full details for a single collection.

        Args:
            collection_id: Collection ID (numeric or GID).

        Returns collection with title, description, sort order, rules (if smart),
        product count, first 20 products, SEO fields, and image.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Collection", collection_id)
            data = await client.graphql(QUERY_COLLECTION, {"id": gid})
            collection = data.get("collection")
            if not collection:
                return _error(f"Collection not found: {collection_id}")
            collection["products"] = _flatten_edges(collection.get("products", {}))
            return json.dumps(collection, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def list_collections(
        ctx: Context,
        query: str = "",
        first: int = 25,
        after: str = "",
    ) -> str:
        """List and search collections.

        Args:
            query: Shopify search filter. Examples:
                'title:*summer*' — title contains "summer"
                'collection_type:smart' — smart collections only
                'updated_at:>2026-01-01'
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

            data = await client.graphql(QUERY_COLLECTIONS, variables)
            coll_conn = data.get("collections", {})
            collections = _flatten_edges(coll_conn)
            page_info = coll_conn.get("pageInfo", {})

            return json.dumps(
                {
                    "collections": collections,
                    "count": len(collections),
                    "hasNextPage": page_info.get("hasNextPage", False),
                    "endCursor": page_info.get("endCursor"),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def create_collection(
        title: str,
        ctx: Context,
        description_html: str = "",
        rules_json: str = "",
        product_ids: str = "",
        sort_order: str = "",
    ) -> str:
        """Create a new collection.

        Args:
            title: Collection title (required).
            description_html: Collection description (HTML allowed).
            rules_json: For SMART collections — JSON array of rule objects. Example:
                '[{"column": "TAG", "relation": "EQUALS", "condition": "sale"}]'
                Columns: TAG, TITLE, TYPE, VENDOR, PRICE, WEIGHT, VARIANT_TITLE, etc.
                Relations: EQUALS, NOT_EQUALS, GREATER_THAN, LESS_THAN, STARTS_WITH, etc.
            product_ids: For MANUAL collections — comma-separated product IDs to add.
            sort_order: ALPHA_ASC, ALPHA_DESC, BEST_SELLING, CREATED, CREATED_DESC,
                MANUAL, PRICE_ASC, PRICE_DESC.

        Provide rules_json for smart collections OR product_ids for manual.

        [SAFETY: Tier 1 — Write] Show what will be created before executing.
        """
        try:
            client = _get_client(ctx)
            coll_input: dict = {"title": title}
            if description_html:
                coll_input["descriptionHtml"] = description_html
            if sort_order:
                coll_input["sortOrder"] = sort_order.upper()

            if rules_json:
                try:
                    rules = json.loads(rules_json)
                    coll_input["ruleSet"] = {
                        "appliedDisjunctively": False,
                        "rules": rules,
                    }
                except json.JSONDecodeError as e:
                    return _error(f"Invalid rules_json: {e}")
            elif product_ids:
                coll_input["products"] = [
                    client.normalize_gid("Product", pid.strip())
                    for pid in product_ids.split(",")
                    if pid.strip()
                ]

            data = await client.graphql(MUTATION_COLLECTION_CREATE, {"input": coll_input})
            err = _check_user_errors(data, "collectionCreate")
            if err:
                return _error(err)

            collection = data.get("collectionCreate", {}).get("collection", {})
            return json.dumps(collection, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def update_collection(
        collection_id: str,
        ctx: Context,
        title: str = "",
        description_html: str = "",
        sort_order: str = "",
        rules_json: str = "",
    ) -> str:
        """Update an existing collection.

        Args:
            collection_id: Collection ID (numeric or GID).
            title: New title (leave empty to keep current).
            description_html: New description.
            sort_order: New sort order.
            rules_json: New rules for smart collections.

        Only provided fields are updated.

        [SAFETY: Tier 1 — Write] Show what will change before executing.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Collection", collection_id)
            coll_input: dict = {"id": gid}

            if title:
                coll_input["title"] = title
            if description_html:
                coll_input["descriptionHtml"] = description_html
            if sort_order:
                coll_input["sortOrder"] = sort_order.upper()
            if rules_json:
                try:
                    rules = json.loads(rules_json)
                    coll_input["ruleSet"] = {
                        "appliedDisjunctively": False,
                        "rules": rules,
                    }
                except json.JSONDecodeError as e:
                    return _error(f"Invalid rules_json: {e}")

            if len(coll_input) == 1:
                return _error("No fields to update. Provide at least one field.")

            data = await client.graphql(MUTATION_COLLECTION_UPDATE, {"input": coll_input})
            err = _check_user_errors(data, "collectionUpdate")
            if err:
                return _error(err)

            collection = data.get("collectionUpdate", {}).get("collection", {})
            return json.dumps(collection, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def delete_collection(collection_id: str, ctx: Context) -> str:
        """Delete a collection permanently.

        Args:
            collection_id: Collection ID (numeric or GID).

        WARNING: This cannot be undone. Products in the collection are NOT deleted.

        [SAFETY: Tier 2 — Destructive] Requires explicit user confirmation.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Collection", collection_id)
            data = await client.graphql(MUTATION_COLLECTION_DELETE, {"input": {"id": gid}})
            err = _check_user_errors(data, "collectionDelete")
            if err:
                return _error(err)

            deleted_id = data.get("collectionDelete", {}).get("deletedCollectionId", "")
            return json.dumps({"deleted": True, "deletedCollectionId": deleted_id}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def manage_collection_products(
        collection_id: str,
        ctx: Context,
        add_product_ids: str = "",
        remove_product_ids: str = "",
    ) -> str:
        """Add or remove products from a manual collection.

        Args:
            collection_id: Collection ID (numeric or GID).
            add_product_ids: Comma-separated product IDs to add.
            remove_product_ids: Comma-separated product IDs to remove.

        Provide add_product_ids, remove_product_ids, or both.
        Does not work on smart collections (they're rule-based).

        [SAFETY: Tier 1 — Write] Show what will change before executing.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Collection", collection_id)
            results: list[str] = []

            if add_product_ids:
                ids = [
                    client.normalize_gid("Product", pid.strip())
                    for pid in add_product_ids.split(",")
                    if pid.strip()
                ]
                data = await client.graphql(
                    MUTATION_COLLECTION_ADD_PRODUCTS,
                    {"id": gid, "productIds": ids},
                )
                err = _check_user_errors(data, "collectionAddProducts")
                if err:
                    return _error(f"Add failed: {err}")
                results.append(f"Added {len(ids)} products")

            if remove_product_ids:
                ids = [
                    client.normalize_gid("Product", pid.strip())
                    for pid in remove_product_ids.split(",")
                    if pid.strip()
                ]
                data = await client.graphql(
                    MUTATION_COLLECTION_REMOVE_PRODUCTS,
                    {"id": gid, "productIds": ids},
                )
                err = _check_user_errors(data, "collectionRemoveProducts")
                if err:
                    return _error(f"Remove failed: {err}")
                results.append(f"Removed {len(ids)} products")

            if not results:
                return _error("Provide add_product_ids or remove_product_ids")

            return json.dumps({"success": True, "actions": results}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))
