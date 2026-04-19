"""Sample 08 — lazy Plotly + server-pushed data stream.

A WSRouter handler starts a background task that emits
``metric.sample`` events at 2 Hz. The client lazy-loads Plotly on
mount and extends the line chart with each push.
"""

from __future__ import annotations

import asyncio
import math
import random
import sys
import time
from pathlib import Path

from llming_com import BaseController
from llming_com.ws_router import WSRouter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _common import SampleSession, bootstrap, run  # noqa: E402

HERE = Path(__file__).resolve().parent

ws = WSRouter(prefix="metric")


async def _stream_metrics(controller: BaseController) -> None:
    t0 = time.monotonic()
    while True:
        t = time.monotonic() - t0
        value = math.sin(t / 2) + random.gauss(0, 0.1)
        sent = await controller.send(
            {"type": "metric.sample", "t": round(t, 3), "value": round(value, 4)}
        )
        if not sent:
            return
        await asyncio.sleep(0.5)


@ws.handler("start")
async def start(controller: BaseController) -> dict:
    entry: SampleSession = controller.entry  # type: ignore[attr-defined]
    task = entry.state.get("metric_task")
    if task and not task.done():
        return {"ok": True, "already_running": True}
    entry.state["metric_task"] = asyncio.create_task(_stream_metrics(controller))
    return {"ok": True}


@ws.handler("stop")
async def stop(controller: BaseController) -> dict:
    entry: SampleSession = controller.entry  # type: ignore[attr-defined]
    task = entry.state.get("metric_task")
    if task and not task.done():
        task.cancel()
    return {"ok": True}


app, registry, auth = bootstrap(
    app_name="sample08",
    title="Sample 08 — Plotly dashboard",
    routes=[("/", "dashboard")],
    view_modules={"dashboard": "/app-static/dashboard.js"},
    preload_views=["dashboard"],
    static_dir=HERE / "static",
    ws_router=ws,
)


if __name__ == "__main__":
    run(app)
