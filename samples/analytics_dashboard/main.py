"""Analytics dashboard with server-owned data.

Every browser tab opens its own session against ``/api/session``. The
server generates the dashboard payload (KPIs, revenue/orders trend,
product mix, radar/heat/scatter/candlestick series) per-session and
ships it over the WebSocket. Filter changes round-trip the same way:
the client sends ``dashboard.set_filters``, the server folds the change
into the session's filter state and pushes the refreshed payload back.

A second per-session task pushes simulated CPU/memory readings every
two seconds, so the System Health gauges genuinely come from the
server. Inspect any of this live from the runner's Sessions tab.
"""

from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI
from llming_com import BaseSessionEntry
from llming_stage import Stage
from pydantic import BaseModel


@dataclass
class Session(BaseSessionEntry):
    state: dict[str, Any] = field(default_factory=dict)


REGIONS = ["North", "South", "East", "West", "Central"]
PRODUCTS = ["Laptops", "Phones", "Tablets", "Watches", "Headphones"]
DATE_RANGES = ["Last 7 days", "Last 30 days", "Last 3 months", "Last 12 months", "Year to date"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
PRODUCT_COLORS = {
    "Laptops": "#3b82f6",
    "Phones": "#10b981",
    "Tablets": "#f59e0b",
    "Watches": "#ef4444",
    "Headphones": "#8b5cf6",
}


def _default_filters() -> dict[str, Any]:
    return {
        "regions": list(REGIONS),
        "products": list(PRODUCTS),
        "date_range": "Last 12 months",
        "search": "",
        "show_comparison": False,
    }


def _labels(date_range: str) -> list[str]:
    if date_range == "Last 7 days":
        return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    if date_range == "Last 30 days":
        return [f"Day {i + 1}" for i in range(30)]
    if date_range == "Last 3 months":
        return [f"Week {i + 1}" for i in range(12)]
    return list(MONTHS)


def _scale(filters: dict[str, Any]) -> float:
    rs = max(len(filters.get("regions") or []), 1)
    ps = max(len(filters.get("products") or []), 1)
    return (rs / len(REGIONS)) * (ps / len(PRODUCTS))


def _dataset(filters: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    """Synthesize the dashboard payload from server-held filter state."""
    scale = _scale(filters)
    labels = _labels(filters.get("date_range", "Last 12 months"))
    revenue = [
        int((9000 + math.sin(i * 0.8) * 2200 + rng.random() * 1800) * scale)
        for i in range(len(labels))
    ]
    orders = [
        int(120 + math.cos(i * 0.7) * 35 + rng.random() * 40)
        for i in range(len(labels))
    ]
    revenue_ly = [int(v * 0.86) for v in revenue] if filters.get("show_comparison") else None
    search = (filters.get("search") or "").lower()
    selected = [
        p for p in PRODUCTS
        if p in (filters.get("products") or [])
        and (not search or search in p.lower())
    ]
    products = {p: int((9000 + i * 3100) * scale) for i, p in enumerate(selected)}
    regions = filters.get("regions") or []
    radar = [
        {"name": r, "value": [70 + i * 4, 44 + i * 8, 62, 80 - i * 5, 55 + i * 6]}
        for i, r in enumerate(regions[:3])
    ]
    heat = [[h, d, rng.randint(0, 100)] for d in range(7) for h in range(24)]
    scatter = {
        "Enterprise": [[70 + rng.uniform(-12, 12), 70 + rng.uniform(-12, 12)] for _ in range(36)],
        "SMB":        [[50 + rng.uniform(-12, 12), 45 + rng.uniform(-12, 12)] for _ in range(36)],
        "Consumer":   [[30 + rng.uniform(-12, 12), 60 + rng.uniform(-12, 12)] for _ in range(36)],
    }
    price = 100.0
    candle = []
    for _ in range(30):
        close = price + rng.uniform(-5, 5)
        candle.append([round(price, 2), round(close, 2),
                       round(min(price, close) - rng.uniform(0, 2), 2),
                       round(max(price, close) + rng.uniform(0, 2), 2)])
        price = close
    return {
        "kpis": {
            "revenue": int(124500 * scale),
            "orders": int(1847 * scale),
            "customers": int(892 * scale),
            "conversion": 3.24,
        },
        "labels": labels,
        "revenue": revenue,
        "revenue_ly": revenue_ly,
        "orders": orders,
        "products": products,
        "product_colors": PRODUCT_COLORS,
        "radar": radar,
        "heat": heat,
        "scatter": scatter,
        "candle": candle,
    }


def _options() -> dict[str, Any]:
    return {
        "regions": list(REGIONS),
        "products": list(PRODUCTS),
        "date_ranges": list(DATE_RANGES),
    }


def _session_rng(session: Session) -> random.Random:
    rng = session.state.get("_rng")
    if rng is None:
        # Per-session seed so charts redrawn after a filter change keep
        # their visual identity instead of jumping randomly. Different
        # tabs (different session ids) see different shapes.
        rng = random.Random(hash(getattr(session, "session_id", id(session))) & 0xFFFFFFFF)
        session.state["_rng"] = rng
    return rng


app = FastAPI()
stage = Stage(app, title="Analytics Dashboard")
sessions = stage.session(app_name="dashboard", session_cls=Session)
dashboard = sessions.add_router("dashboard")


class FilterChange(BaseModel):
    regions: list[str] | None = None
    products: list[str] | None = None
    date_range: str | None = None
    search: str | None = None
    show_comparison: bool | None = None


@dashboard.handler("subscribe")
async def subscribe(session: Session) -> None:
    """Push the initial dataset and start the metrics ticker.

    The client calls this exactly once on mount. The server is the
    source of truth: filter options, current filter selection, and the
    dataset all come over the WebSocket.
    """
    filters = session.state.setdefault("filters", _default_filters())
    await session.call(
        "home.applyInitial",
        _options(),
        filters,
        _dataset(filters, _session_rng(session)),
    )
    # Kick the metrics pusher if not already running for this session.
    existing = session.state.get("_metrics_task")
    if existing is None or existing.done():
        session.state["_metrics_task"] = asyncio.create_task(_metrics_ticker(session))


@dashboard.handler("set_filters")
async def set_filters(session: Session, change: FilterChange) -> None:
    """Fold a filter change into the session and push the refreshed data."""
    filters = session.state.setdefault("filters", _default_filters())
    payload = change.model_dump(exclude_none=True)
    filters.update(payload)
    await session.call(
        "home.applyDataset", filters, _dataset(filters, _session_rng(session))
    )


async def _metrics_ticker(session: Session) -> None:
    """Push CPU/memory readings every 2 seconds for the System Health card.

    Self-terminates as soon as ``session.call`` fails (the WebSocket is
    gone) — no separate cancellation needed in the happy path.
    """
    cpu = session.state.get("_cpu", 45.0)
    mem = session.state.get("_mem", 62.0)
    try:
        while True:
            cpu = max(10.0, min(95.0, cpu + random.uniform(-5, 5)))
            mem = max(20.0, min(90.0, mem + random.uniform(-3, 3)))
            session.state["_cpu"] = cpu
            session.state["_mem"] = mem
            try:
                await session.call("home.applyMetrics", {"cpu": round(cpu, 1), "memory": round(mem, 1)})
            except Exception:
                return  # controller / WS gone — bail cleanly
            await asyncio.sleep(2.0)
    except asyncio.CancelledError:
        return


stage.add_view("/", "home.vue")


if __name__ == "__main__":
    stage.run()
