"""Sample 03 — counter with server-side state.

Two WS handlers: ``counter.inc`` increments the session's counter and
pushes the new value; ``counter.reset`` resets it. State lives on
:class:`SampleSession.state` — so it is per-user, server-held, and
inspectable through the debug API.
"""

from __future__ import annotations

from pathlib import Path

from llming_com import SessionRouter
from pydantic import BaseModel

from samples._common import SampleSession, bootstrap, run

HERE = Path(__file__).resolve().parent

ws = SessionRouter(prefix="counter")


class IncEvent(BaseModel):
    by: int = 1


class CounterAck(BaseModel):
    ok: bool
    value: int


@ws.handler("inc")
async def inc(session: SampleSession, event: IncEvent) -> CounterAck:
    session.state["count"] = int(session.state.get("count", 0)) + event.by
    await session.call("home.setCounter", session.state["count"])
    return CounterAck(ok=True, value=session.state["count"])


@ws.handler("reset")
async def reset(session: SampleSession) -> CounterAck:
    session.state["count"] = 0
    await session.call("home.setCounter", 0)
    return CounterAck(ok=True, value=0)


app, registry, auth = bootstrap(
    app_name="sample03",
    title="Sample 03 — Counter",
    routes=[("/", "home")],
    view_sources={"home": "home.vue"},
    static_dir=HERE,
    ws_router=ws,
)


if __name__ == "__main__":
    run(app, sample_dir=HERE)
