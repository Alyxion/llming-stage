"""Sample 04 — multi-view SPA with a shared session.

Two routes (`/` home, `/timer` countdown). Navigating between them
is a client-side view swap — the same WebSocket stays connected and
the same session entry is reused.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from llming_com import BaseController
from llming_com.ws_router import WSRouter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _common import SampleSession, bootstrap, run  # noqa: E402

HERE = Path(__file__).resolve().parent

ws = WSRouter(prefix="timer")


@ws.handler("start")
async def start(controller: BaseController, seconds: int = 5) -> dict:
    """Kick off a server-driven countdown. Ticks are pushed, one per second."""
    entry: SampleSession = controller.entry  # type: ignore[attr-defined]
    task = entry.state.get("timer_task")
    if task and not task.done():
        task.cancel()

    async def run_timer() -> None:
        remaining = int(seconds)
        while remaining >= 0:
            sent = await controller.send({"type": "timer.tick", "remaining": remaining})
            if not sent:
                return
            remaining -= 1
            await asyncio.sleep(1)
        await controller.send({"type": "timer.done"})

    entry.state["timer_task"] = asyncio.create_task(run_timer())
    return {"ok": True}


@ws.handler("cancel")
async def cancel(controller: BaseController) -> dict:
    entry: SampleSession = controller.entry  # type: ignore[attr-defined]
    task = entry.state.get("timer_task")
    if task and not task.done():
        task.cancel()
    return {"ok": True}


app, registry, auth = bootstrap(
    app_name="sample04",
    title="Sample 04 — Multi-view",
    routes=[("/", "home"), ("/timer", "timer")],
    view_modules={
        "home": "/app-static/home.js",
        "timer": "/app-static/timer.js",
    },
    preload_views=["home"],
    static_dir=HERE / "static",
    ws_router=ws,
)


if __name__ == "__main__":
    run(app)
