# AdminAgent — Shopify Admin MCP Server

## What This Is
MCP server giving Claude full control over a Shopify store via the Admin GraphQL API.
Sprint 1: 21 tools (products, collections, ShopifyQL analytics, bulk operations).

## Architecture
```
server.py          → FastMCP entry point, lifespan, helpers
auth.py            → TokenManager (OAuth 24h + legacy shpat_ dual mode)
client.py          → ShopifyAdminClient (GraphQL, cost-based rate limiting, pagination)
bulk.py            → BulkOperationManager (async submit/poll/download)
safety.py          → SafetyTier enum + registry
tools/products.py  → 17 product/collection tools
tools/analytics.py → 1 ShopifyQL tool
tools/bulk_ops.py  → 3 bulk operation tools
queries/*.py       → GraphQL query/mutation strings
```

## 21 MCP Tools (Sprint 1)

**Products (11):** get_product, list_products, create_product, update_product, delete_product, set_product, duplicate_product, create_variants, update_variants, delete_variants, manage_product_options

**Collections (6):** get_collection, list_collections, create_collection, update_collection, delete_collection, manage_collection_products

**Analytics (1):** run_shopifyql

**Bulk Ops (3):** run_bulk_query, check_bulk_operation, cancel_bulk_operation

## API Details
- **Endpoint:** `https://{store}.myshopify.com/admin/api/2026-04/graphql.json`
- **Auth:** OAuth client credentials (24h token, auto-refresh) OR legacy shpat_ token
- **Rate limit:** Cost-based (100 pts/sec Standard, 200 Advanced, 1000 Plus). Single query max 1000 pts.
- **Pagination:** Relay cursors (pageInfo.endCursor)

## Key Constraints
- All IDs must be GID format (gid://shopify/Product/123). Tools accept numeric IDs and normalize.
- Mutations return userErrors on HTTP 200. Always check userErrors array.
- productUpdate requires id INSIDE ProductInput.
- Bulk operations: max 1 running at a time. Results available as JSONL for 7 days.
- read_all_orders scope needed for order data beyond 60 days (requires Shopify approval).
- Inventory adjustments need idempotency keys in API 2026-04.

## Safety Tiers
- EXCLUDED: payments, domains, checkout, tax, store plan, staff permissions (never built)
- READ-ONLY: payouts, disputes, policies
- Tier 0 (Read): get, list, search, analytics
- Tier 1 (Write): create, update
- Tier 2 (Destructive): delete, cancel
- Tier 3 (Bulk): bulk operations

## Stack
Python 3.12, FastMCP, httpx, python-dotenv. 100% GraphQL, API version 2026-04.

## Setup
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Fill in SHOPIFY_STORE + auth credentials
claude mcp add admin-agent .venv/bin/python server.py
```
