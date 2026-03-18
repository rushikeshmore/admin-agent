"""Content MCP tools (8 tools).

Pages: get, list, create, update, delete
Blogs: list
Articles: list
Redirects: list, create, delete
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context, FastMCP

from client import ShopifyAdminError
from queries.content import (
    MUTATION_PAGE_CREATE,
    MUTATION_PAGE_DELETE,
    MUTATION_PAGE_UPDATE,
    MUTATION_REDIRECT_CREATE,
    MUTATION_REDIRECT_DELETE,
    QUERY_ARTICLES,
    QUERY_BLOGS,
    QUERY_PAGE,
    QUERY_PAGES,
    QUERY_REDIRECTS,
)
from safety import SafetyTier, register_safety


def register(mcp: FastMCP) -> None:
    """Register content tools."""
    from server import _check_user_errors, _error, _flatten_edges, _get_client

    register_safety("get_page", SafetyTier.READ)
    register_safety("list_pages", SafetyTier.READ)
    register_safety("create_page", SafetyTier.WRITE)
    register_safety("update_page", SafetyTier.WRITE)
    register_safety("delete_page", SafetyTier.DESTRUCTIVE)
    register_safety("list_blogs", SafetyTier.READ)
    register_safety("list_articles", SafetyTier.READ)
    register_safety("manage_redirects", SafetyTier.WRITE)

    @mcp.tool()
    async def get_page(page_id: str, ctx: Context) -> str:
        """Get full details for a page.

        Args:
            page_id: Page ID (numeric or GID).

        Returns page title, body (HTML), handle, publish status, and template.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Page", page_id)
            data = await client.graphql(QUERY_PAGE, {"id": gid})
            page = data.get("page")
            if not page:
                return _error(f"Page not found: {page_id}")
            return json.dumps(page, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def list_pages(ctx: Context, first: int = 25, after: str = "") -> str:
        """List all pages.

        Args:
            first: Results per page (max 250, default 25).
            after: Pagination cursor.

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            variables: dict = {"first": min(first, 250)}
            if after:
                variables["after"] = after
            data = await client.graphql(QUERY_PAGES, variables)
            conn = data.get("pages", {})
            pages = _flatten_edges(conn)
            page_info = conn.get("pageInfo", {})
            return json.dumps(
                {
                    "pages": pages,
                    "count": len(pages),
                    "hasNextPage": page_info.get("hasNextPage", False),
                    "endCursor": page_info.get("endCursor"),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def create_page(
        title: str,
        ctx: Context,
        body: str = "",
        is_published: bool = False,
        template_suffix: str = "",
    ) -> str:
        """Create a new page (About Us, Contact, FAQ, etc.).

        Args:
            title: Page title.
            body: Page content (HTML).
            is_published: Publish immediately (default: False = draft).
            template_suffix: Custom template (e.g., 'contact' uses page.contact.liquid).

        [SAFETY: Tier 1 — Write]
        """
        try:
            client = _get_client(ctx)
            page_input: dict = {"title": title, "isPublished": is_published}
            if body:
                page_input["body"] = body
            if template_suffix:
                page_input["templateSuffix"] = template_suffix

            data = await client.graphql(MUTATION_PAGE_CREATE, {"page": page_input})
            err = _check_user_errors(data, "pageCreate")
            if err:
                return _error(err)
            return json.dumps(data.get("pageCreate", {}).get("page", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def update_page(
        page_id: str,
        ctx: Context,
        title: str = "",
        body: str = "",
        is_published: bool | None = None,
    ) -> str:
        """Update an existing page.

        Args:
            page_id: Page ID (numeric or GID).
            title: New title.
            body: New body content (HTML).
            is_published: True to publish, False to unpublish.

        [SAFETY: Tier 1 — Write]
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Page", page_id)
            page_input: dict = {}
            if title:
                page_input["title"] = title
            if body:
                page_input["body"] = body
            if is_published is not None:
                page_input["isPublished"] = is_published

            if not page_input:
                return _error("No fields to update.")

            data = await client.graphql(MUTATION_PAGE_UPDATE, {"id": gid, "page": page_input})
            err = _check_user_errors(data, "pageUpdate")
            if err:
                return _error(err)
            return json.dumps(data.get("pageUpdate", {}).get("page", {}), indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def delete_page(page_id: str, ctx: Context) -> str:
        """Delete a page permanently.

        Args:
            page_id: Page ID (numeric or GID).

        WARNING: Cannot be undone.

        [SAFETY: Tier 2 — Destructive] Requires explicit user confirmation.
        """
        try:
            client = _get_client(ctx)
            gid = client.normalize_gid("Page", page_id)
            data = await client.graphql(MUTATION_PAGE_DELETE, {"id": gid})
            err = _check_user_errors(data, "pageDelete")
            if err:
                return _error(err)
            return json.dumps(
                {
                    "deleted": True,
                    "deletedPageId": data.get("pageDelete", {}).get("deletedPageId", ""),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def list_blogs(ctx: Context, first: int = 25) -> str:
        """List all blogs.

        Args:
            first: Results per page (default 25).

        [SAFETY: Tier 0 — Read]
        """
        try:
            client = _get_client(ctx)
            data = await client.graphql(QUERY_BLOGS, {"first": min(first, 250)})
            blogs = _flatten_edges(data.get("blogs", {}))
            return json.dumps({"blogs": blogs, "count": len(blogs)}, indent=2)
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def list_articles(
        ctx: Context,
        query: str = "",
        first: int = 25,
        after: str = "",
    ) -> str:
        """List and search blog articles.

        Args:
            query: Shopify search filter (e.g., 'tag:announcement', 'blog_id:123').
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
            data = await client.graphql(QUERY_ARTICLES, variables)
            conn = data.get("articles", {})
            articles = _flatten_edges(conn)
            page_info = conn.get("pageInfo", {})
            return json.dumps(
                {
                    "articles": articles,
                    "count": len(articles),
                    "hasNextPage": page_info.get("hasNextPage", False),
                    "endCursor": page_info.get("endCursor"),
                },
                indent=2,
            )
        except ShopifyAdminError as e:
            return _error(str(e))

    @mcp.tool()
    async def manage_redirects(
        ctx: Context,
        action: str = "list",
        path: str = "",
        target: str = "",
        redirect_ids: str = "",
        first: int = 25,
        after: str = "",
    ) -> str:
        """Manage URL redirects (list, create, or delete).

        Args:
            action: 'list' (default), 'create', or 'delete'.
            path: For create — the old URL path (e.g., '/old-page').
            target: For create — the new URL path (e.g., '/new-page').
            redirect_ids: For delete — comma-separated redirect IDs.
            first: For list — results per page.
            after: For list — pagination cursor.

        [SAFETY: Tier 1 — Write] (for create/delete actions)
        """
        try:
            client = _get_client(ctx)

            if action == "create":
                if not path or not target:
                    return _error("Provide both 'path' and 'target' for redirect creation.")
                data = await client.graphql(
                    MUTATION_REDIRECT_CREATE,
                    {"urlRedirect": {"path": path, "target": target}},
                )
                err = _check_user_errors(data, "urlRedirectCreate")
                if err:
                    return _error(err)
                return json.dumps(
                    data.get("urlRedirectCreate", {}).get("urlRedirect", {}), indent=2
                )

            elif action == "delete":
                if not redirect_ids:
                    return _error("Provide 'redirect_ids' to delete.")
                ids = [
                    client.normalize_gid("UrlRedirect", rid.strip())
                    for rid in redirect_ids.split(",")
                    if rid.strip()
                ]
                data = await client.graphql(MUTATION_REDIRECT_DELETE, {"ids": ids})
                err = _check_user_errors(data, "urlRedirectBulkDeleteByIds")
                if err:
                    return _error(err)
                count = data.get("urlRedirectBulkDeleteByIds", {}).get("deletedCount", 0)
                return json.dumps({"deleted": True, "deletedCount": count}, indent=2)

            else:  # list
                variables: dict = {"first": min(first, 250)}
                if after:
                    variables["after"] = after
                data = await client.graphql(QUERY_REDIRECTS, variables)
                conn = data.get("urlRedirects", {})
                redirects = _flatten_edges(conn)
                page_info = conn.get("pageInfo", {})
                return json.dumps(
                    {
                        "redirects": redirects,
                        "count": len(redirects),
                        "hasNextPage": page_info.get("hasNextPage", False),
                        "endCursor": page_info.get("endCursor"),
                    },
                    indent=2,
                )
        except ShopifyAdminError as e:
            return _error(str(e))
