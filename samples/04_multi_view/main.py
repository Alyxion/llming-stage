"""Sample 04 — multi-view SPA with a shared session.

Two routes (`/` home, `/timer` countdown). Navigating between them
is a client-side view swap — the same WebSocket stays connected and
the same session entry is reused.
"""

from __future__ import annotations

from pathlib import Path

from llming_com import SessionRouter

from samples._common import SampleSession, bootstrap, run

HERE = Path(__file__).resolve().parent

timer = SessionRouter(prefix="timer")
drawer = SessionRouter(prefix="drawer")
ws = SessionRouter()
ws.include(timer)
ws.include(drawer)


@timer.handler("start")
async def start(session: SampleSession, seconds: int = 5) -> dict:
    """Kick off a server-driven countdown. Ticks are pushed, one per second."""
    remaining = int(seconds)

    async def tick() -> bool:
        nonlocal remaining
        if remaining < 0:
            await session.call("timer.finishTimer")
            return False
        sent = await session.call("timer.setTimer", remaining)
        remaining -= 1
        return sent

    session.start_timer("timer_task", 1, tick)
    return {"ok": True}


@timer.handler("cancel")
async def cancel(session: SampleSession) -> dict:
    session.cancel_timer("timer_task")
    return {"ok": True}


@drawer.handler("open")
async def open_drawer(session: SampleSession) -> dict:
    await session.call("drawer.open", "Opened by Python on a nested Vue component.")
    return {"ok": True}


@drawer.handler("close")
async def close_drawer(session: SampleSession) -> dict:
    await session.call("drawer.close")
    return {"ok": True}


app, registry, auth = bootstrap(
    app_name="sample04",
    title="Sample 04 — Multi-view",
    routes=[("/", "home"), ("/timer", "timer")],
    view_sources={"home": "home.vue", "timer": "timer.vue"},
    static_dir=HERE,
    ws_router=ws,
)


if __name__ == "__main__":
    run(app, sample_dir=HERE)
