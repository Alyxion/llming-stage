"""Multi-view SPA with a shared session.

Two routes (`/` home, `/timer` countdown). Navigating between them
is a client-side view swap — the same WebSocket stays connected and
the same session entry is reused.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI
from llming_com import BaseSessionEntry
from llming_stage import Stage


@dataclass
class Session(BaseSessionEntry):
    state: dict[str, Any] = field(default_factory=dict)


app = FastAPI()
stage = Stage(app, title="Multi-view")
sessions = stage.session(app_name="multi_view", session_cls=Session)
timer = sessions.add_router("timer")
drawer = sessions.add_router("drawer")


@timer.handler("start")
async def start(session: Session, seconds: int = 5) -> dict:
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
async def cancel(session: Session) -> dict:
    session.cancel_timer("timer_task")
    return {"ok": True}


@drawer.handler("open")
async def open_drawer(session: Session) -> dict:
    await session.call("drawer.open", "Opened by Python on a nested Vue component.")
    return {"ok": True}


@drawer.handler("close")
async def close_drawer(session: Session) -> dict:
    await session.call("drawer.close")
    return {"ok": True}


stage.add_view("/", "home.vue")
stage.add_view("/timer", "timer.vue")

if __name__ == "__main__":
    stage.run()
