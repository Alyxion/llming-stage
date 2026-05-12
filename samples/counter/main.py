"""Counter with server-side state.

Two WS handlers: ``counter.inc`` increments the session's counter and
pushes the new value; ``counter.reset`` resets it. State lives on
``Session.state`` — so it is per-user, server-held, and
inspectable through the debug API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI
from llming_com import BaseSessionEntry
from llming_stage import Stage
from pydantic import BaseModel


@dataclass
class Session(BaseSessionEntry):
    state: dict[str, Any] = field(default_factory=dict)


app = FastAPI()
stage = Stage(app, title="Counter")
sessions = stage.session(app_name="counter", session_cls=Session)
counter = sessions.add_router("counter")


class IncEvent(BaseModel):
    by: int = 1


class CounterAck(BaseModel):
    ok: bool
    value: int


@counter.handler("inc")
async def inc(session: Session, event: IncEvent) -> CounterAck:
    session.state["count"] = int(session.state.get("count", 0)) + event.by
    await session.call("home.setCounter", session.state["count"])
    return CounterAck(ok=True, value=session.state["count"])


@counter.handler("reset")
async def reset(session: Session) -> CounterAck:
    session.state["count"] = 0
    await session.call("home.setCounter", 0)
    return CounterAck(ok=True, value=0)


stage.add_view("/", "home.vue")

if __name__ == "__main__":
    stage.run()
