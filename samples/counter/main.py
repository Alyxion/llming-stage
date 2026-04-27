"""Counter with server-side state.

Two WS handlers: ``counter.inc`` increments the session's counter and
pushes the new value; ``counter.reset`` resets it. State lives on
:class:`SampleSession.state` — so it is per-user, server-held, and
inspectable through the debug API.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel
from llming_stage import Stage

from samples._common import SampleSession, run

HERE = Path(__file__).resolve().parent

app = FastAPI()
stage = Stage(app, root=HERE, title="Counter")
sessions = stage.session(app_name="counter", session_cls=SampleSession)
counter = sessions.router("counter")


class IncEvent(BaseModel):
    by: int = 1


class CounterAck(BaseModel):
    ok: bool
    value: int


@counter.handler("inc")
async def inc(session: SampleSession, event: IncEvent) -> CounterAck:
    session.state["count"] = int(session.state.get("count", 0)) + event.by
    await session.call("home.setCounter", session.state["count"])
    return CounterAck(ok=True, value=session.state["count"])


@counter.handler("reset")
async def reset(session: SampleSession) -> CounterAck:
    session.state["count"] = 0
    await session.call("home.setCounter", 0)
    return CounterAck(ok=True, value=0)


stage.view("/", "home.vue")


if __name__ == "__main__":
    run(app, sample_dir=HERE)
