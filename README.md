# AdminAgent

AI-powered Shopify Admin via Claude + MCP. Manage your entire store through conversation.

## What It Does

21 MCP tools that give Claude full control over products, collections, analytics, and bulk operations in your Shopify store.

| Domain | Tools | Examples |
|--------|-------|---------|
| Products | 11 | List, create, update, delete, duplicate, manage variants/options |
| Collections | 6 | List, create, update, delete, add/remove products |
| Analytics | 1 | Run any ShopifyQL query (revenue, orders, sessions, products) |
| Bulk Ops | 3 | Submit bulk queries, check status, cancel |

## Setup

1. **Create a custom app** in your Shopify admin (Settings → Apps → Develop apps)
2. **Grant API scopes:** `read_products`, `write_products`, `read_reports`
3. **Install the app** and copy the Admin API access token

```bash
# Clone and install
cd /path/to/admin-agent
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env: set SHOPIFY_STORE and SHOPIFY_ACCESS_TOKEN

# Register with Claude Code
claude mcp add admin-agent .venv/bin/python server.py
```

## Usage

```
"List all active products"
"Create a product called 'Summer Tee' priced at $29.99"
"Show me revenue by product type for the last 90 days"
"Export all products via bulk query"
```

## Stack

Python 3.12 · FastMCP · Shopify Admin GraphQL API (2026-04) · httpx

## Safety

Every tool is classified by destructiveness:
- **Read** (Tier 0): No confirmation needed
- **Write** (Tier 1): Preview changes before executing
- **Destructive** (Tier 2): Explicit confirmation required
- **Bulk** (Tier 3): Count + preview + confirm

Dangerous operations (payments, domains, checkout, tax) are intentionally excluded.
