"""Multi-view SPA with a shared session.

Two routes (`/` home, `/timer` countdown). Navigating between them
is a client-side view swap — the same WebSocket stays connected and
the same session entry is reused.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from llming_stage import Stage

from samples._common import SampleSession, run

HERE = Path(__file__).resolve().parent

app = FastAPI()
stage = Stage(app, root=HERE, title="Multi-view")
sessions = stage.session(app_name="multi_view", session_cls=SampleSession)
timer = sessions.router("timer")
drawer = sessions.router("drawer")


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


stage.view("/", "home.vue")
stage.view("/timer", "timer.vue")


if __name__ == "__main__":
    run(app, sample_dir=HERE)
