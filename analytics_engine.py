"""
Pure computation functions for analytics.

No API calls — only math. Input data, output metrics.
Modeled on partner-agent's analytics.py pattern.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation


def _to_decimal(val: str | float | int) -> Decimal:
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _parse_date(date_str: str) -> date | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return None


def _money(amount_set: dict) -> Decimal:
    """Extract money amount from Shopify MoneyV2/MoneyBag."""
    shop = amount_set.get("shopMoney", amount_set)
    return _to_decimal(shop.get("amount", "0"))


# ─── Product Performance ─────────────────────────────────────────────────────


def rank_products(orders: list[dict], metric: str = "revenue") -> list[dict]:
    """Rank products by revenue, units, or order count from order line items."""
    product_stats: dict[str, dict] = {}

    for order in orders:
        for li in order.get("lineItems", []):
            product_id = (li.get("product") or {}).get("id", "unknown")
            title = li.get("title", "Unknown")
            qty = li.get("quantity", 0)
            price = _money(li.get("discountedUnitPriceSet", li.get("originalUnitPriceSet", {})))
            revenue = price * qty

            if product_id not in product_stats:
                product_stats[product_id] = {
                    "productId": product_id,
                    "title": title,
                    "revenue": Decimal("0"),
                    "units": 0,
                    "orders": 0,
                }
            product_stats[product_id]["revenue"] += revenue
            product_stats[product_id]["units"] += qty
            product_stats[product_id]["orders"] += 1

    products = list(product_stats.values())
    sort_key = metric if metric in ("revenue", "units", "orders") else "revenue"
    products.sort(key=lambda p: p[sort_key], reverse=True)

    for p in products:
        p["revenue"] = str(p["revenue"].quantize(Decimal("0.01")))
    return products


# ─── Customer Analytics ───────────────────────────────────────────────────────


def compute_rfm(customers: list[dict], today: date | None = None) -> list[dict]:
    """Compute RFM (Recency, Frequency, Monetary) segments."""
    if today is None:
        today = date.today()

    scored = []
    for c in customers:
        orders = c.get("orders", [])
        if not orders:
            continue

        dates = [_parse_date(o.get("createdAt", "")) for o in orders]
        dates = [d for d in dates if d]
        if not dates:
            continue

        recency_days = (today - max(dates)).days
        frequency = len(orders)
        monetary = _to_decimal((c.get("amountSpent") or {}).get("amount", "0"))

        scored.append({
            "customerId": c.get("id"),
            "name": c.get("displayName", ""),
            "email": c.get("email", ""),
            "recency_days": recency_days,
            "frequency": frequency,
            "monetary": str(monetary.quantize(Decimal("0.01"))),
        })

    return scored


def compute_cohort_retention(
    customers: list[dict], orders: list[dict], months: int = 6
) -> dict:
    """Compute cohort retention by first-order month."""
    customer_first_order: dict[str, date] = {}
    customer_orders: dict[str, list[date]] = defaultdict(list)

    for order in orders:
        cid = (order.get("customer") or {}).get("id")
        if not cid:
            continue
        d = _parse_date(order.get("createdAt", ""))
        if not d:
            continue
        customer_orders[cid].append(d)
        if cid not in customer_first_order or d < customer_first_order[cid]:
            customer_first_order[cid] = d

    cohorts: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))

    for cid, first_date in customer_first_order.items():
        cohort_key = first_date.strftime("%Y-%m")
        cohorts[cohort_key][0] += 1
        for order_date in customer_orders[cid]:
            month_diff = (order_date.year - first_date.year) * 12 + (order_date.month - first_date.month)
            if 0 < month_diff <= months:
                cohorts[cohort_key][month_diff] += 1

    result = {}
    for cohort_key in sorted(cohorts.keys()):
        base = cohorts[cohort_key][0]
        result[cohort_key] = {
            "customers": base,
            "retention": {
                f"month_{i}": round(cohorts[cohort_key].get(i, 0) / base * 100, 1) if base > 0 else 0
                for i in range(1, months + 1)
            },
        }
    return result


def compute_repeat_rate(orders: list[dict]) -> dict:
    """Compute repeat purchase rate from orders."""
    customer_orders: dict[str, int] = defaultdict(int)
    for order in orders:
        cid = (order.get("customer") or {}).get("id")
        if cid:
            customer_orders[cid] += 1

    total = len(customer_orders)
    repeat = sum(1 for c in customer_orders.values() if c > 1)
    return {
        "total_customers": total,
        "repeat_customers": repeat,
        "repeat_rate": round(repeat / total * 100, 1) if total > 0 else 0,
        "one_time_customers": total - repeat,
    }


# ─── Inventory Analytics ─────────────────────────────────────────────────────


def compute_inventory_turnover(
    products: list[dict], orders: list[dict], days: int = 90
) -> list[dict]:
    """Compute inventory turnover rate per product."""
    units_sold: dict[str, int] = defaultdict(int)
    for order in orders:
        for li in order.get("lineItems", []):
            pid = (li.get("product") or {}).get("id")
            if pid:
                units_sold[pid] += li.get("quantity", 0)

    results = []
    for p in products:
        pid = p.get("id")
        current_inventory = p.get("totalInventory", 0)
        sold = units_sold.get(pid, 0)
        daily_velocity = sold / days if days > 0 else 0
        days_of_supply = round(current_inventory / daily_velocity, 1) if daily_velocity > 0 else float("inf")

        results.append({
            "productId": pid,
            "title": p.get("title", ""),
            "currentInventory": current_inventory,
            "unitsSold": sold,
            "dailyVelocity": round(daily_velocity, 2),
            "daysOfSupply": days_of_supply if days_of_supply != float("inf") else "∞",
            "turnoverRate": round(sold / max(current_inventory, 1), 2),
        })

    results.sort(key=lambda x: x["unitsSold"], reverse=True)
    return results


# ─── Order Pattern Analytics ──────────────────────────────────────────────────


def compute_order_patterns(orders: list[dict]) -> dict:
    """Analyze order patterns by hour and day of week."""
    hourly: dict[int, int] = defaultdict(int)
    daily: dict[str, int] = defaultdict(int)
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    for order in orders:
        d = _parse_date(order.get("createdAt", ""))
        if d:
            try:
                dt = datetime.fromisoformat(order["createdAt"].replace("Z", "+00:00"))
                hourly[dt.hour] += 1
                daily[day_names[dt.weekday()]] += 1
            except (ValueError, KeyError):
                pass

    peak_hour = max(hourly, key=hourly.get) if hourly else 0
    peak_day = max(daily, key=daily.get) if daily else "Unknown"

    return {
        "totalOrders": len(orders),
        "peakHour": f"{peak_hour}:00",
        "peakDay": peak_day,
        "hourlyDistribution": {f"{h}:00": hourly.get(h, 0) for h in range(24)},
        "dailyDistribution": {d: daily.get(d, 0) for d in day_names},
    }


# ─── Discount Analytics ──────────────────────────────────────────────────────


def compute_discount_roi(orders: list[dict]) -> dict:
    """Analyze discount code effectiveness."""
    with_discount: list[dict] = []
    without_discount: list[dict] = []

    for order in orders:
        total = _money(order.get("totalPriceSet", {}))
        if order.get("discountCode"):
            with_discount.append({"total": total, "code": order["discountCode"]})
        else:
            without_discount.append({"total": total})

    aov_with = (
        sum(o["total"] for o in with_discount) / len(with_discount)
        if with_discount
        else Decimal("0")
    )
    aov_without = (
        sum(o["total"] for o in without_discount) / len(without_discount)
        if without_discount
        else Decimal("0")
    )

    code_usage: dict[str, dict] = defaultdict(lambda: {"count": 0, "revenue": Decimal("0")})
    for o in with_discount:
        code_usage[o["code"]]["count"] += 1
        code_usage[o["code"]]["revenue"] += o["total"]

    top_codes = sorted(code_usage.items(), key=lambda x: x[1]["revenue"], reverse=True)[:10]

    return {
        "ordersWithDiscount": len(with_discount),
        "ordersWithoutDiscount": len(without_discount),
        "aovWithDiscount": str(aov_with.quantize(Decimal("0.01"))),
        "aovWithoutDiscount": str(aov_without.quantize(Decimal("0.01"))),
        "topCodes": [
            {"code": code, "uses": data["count"], "revenue": str(data["revenue"].quantize(Decimal("0.01")))}
            for code, data in top_codes
        ],
    }
