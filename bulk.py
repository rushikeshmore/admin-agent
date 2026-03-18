"""
Bulk operations manager for Shopify Admin API.

Submit async queries, poll for completion, download and parse JSONL results.
"""

from __future__ import annotations

import asyncio
import json

import httpx

from client import ShopifyAdminClient, ShopifyAdminError

MUTATION_BULK_RUN = """
mutation BulkOperationRunQuery($query: String!) {
  bulkOperationRunQuery(query: $query) {
    bulkOperation {
      id
      status
      url
    }
    userErrors {
      field
      message
    }
  }
}
"""

QUERY_BULK_STATUS = """
query BulkOperationStatus($id: ID!) {
  node(id: $id) {
    ... on BulkOperation {
      id
      status
      errorCode
      objectCount
      fileSize
      url
      createdAt
      completedAt
    }
  }
}
"""

MUTATION_BULK_CANCEL = """
mutation BulkOperationCancel($id: ID!) {
  bulkOperationCancel(id: $id) {
    bulkOperation {
      id
      status
    }
    userErrors {
      field
      message
    }
  }
}
"""


class BulkOperationManager:
    """Manages Shopify Admin bulk operations (async query execution)."""

    def __init__(self, client: ShopifyAdminClient):
        self._client = client

    async def submit(self, query: str) -> dict:
        """Submit a bulk query for async execution.

        Args:
            query: GraphQL query to run in bulk (no variables, no pagination args).

        Returns dict with id, status, url.
        Raises ShopifyAdminError if userErrors present.
        """
        data = await self._client.graphql(MUTATION_BULK_RUN, {"query": query})
        result = data.get("bulkOperationRunQuery", {})

        user_errors = result.get("userErrors", [])
        if user_errors:
            msgs = "; ".join(e["message"] for e in user_errors)
            raise ShopifyAdminError(200, f"Bulk operation failed: {msgs}")

        return result.get("bulkOperation", {})

    async def poll_status(self, bulk_op_id: str) -> dict:
        """Check status of a bulk operation.

        Returns dict with id, status, objectCount, fileSize, url.
        """
        data = await self._client.graphql(QUERY_BULK_STATUS, {"id": bulk_op_id})
        node = data.get("node", {})
        if not node:
            raise ShopifyAdminError(404, f"Bulk operation not found: {bulk_op_id}")
        return node

    async def cancel(self, bulk_op_id: str) -> dict:
        """Cancel a running bulk operation."""
        data = await self._client.graphql(MUTATION_BULK_CANCEL, {"id": bulk_op_id})
        result = data.get("bulkOperationCancel", {})

        user_errors = result.get("userErrors", [])
        if user_errors:
            msgs = "; ".join(e["message"] for e in user_errors)
            raise ShopifyAdminError(200, f"Cancel failed: {msgs}")

        return result.get("bulkOperation", {})

    async def download_and_parse(self, url: str) -> list[dict]:
        """Download JSONL from bulk op URL and parse into list of dicts.

        Handles __parentId: child records reference their parent.
        Returns flat list of all records.
        """
        async with httpx.AsyncClient(timeout=120.0) as http:
            resp = await http.get(url)
            resp.raise_for_status()

        records: list[dict] = []
        for line in resp.text.strip().split("\n"):
            if line.strip():
                records.append(json.loads(line))
        return records

    async def run_and_wait(
        self,
        query: str,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> list[dict]:
        """Submit, poll until done, download and parse.

        Convenience method for synchronous-feeling bulk operations.
        """
        op = await self.submit(query)
        op_id = op.get("id", "")
        if not op_id:
            raise ShopifyAdminError(200, "Bulk operation returned no ID")

        elapsed = 0.0
        while elapsed < timeout:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            status = await self.poll_status(op_id)
            state = status.get("status", "")

            if state == "COMPLETED":
                url = status.get("url", "")
                if not url:
                    return []
                return await self.download_and_parse(url)
            elif state in ("FAILED", "CANCELED"):
                error = status.get("errorCode", "UNKNOWN")
                raise ShopifyAdminError(200, f"Bulk operation {state}: {error}")

        raise ShopifyAdminError(408, f"Bulk operation timed out after {timeout}s")
