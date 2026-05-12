"""Streaming chat response.

Demonstrates a long-running server-side task that pushes tokens one
at a time over the WebSocket. No buffering, no polling — the client
sees each chunk as it is generated.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI
from llming_com import BaseSessionEntry
from llming_stage import Stage


@dataclass
class Session(BaseSessionEntry):
    state: dict[str, Any] = field(default_factory=dict)


app = FastAPI()
stage = Stage(app, title="Streaming chat")
sessions = stage.session(app_name="chat_stream", session_cls=Session)
chat = sessions.add_router("chat")

_CANNED_REPLIES = [
    "llming-stage gives you the ",
    "frontend shell; llming-com ",
    "gives you the wire. Put them ",
    "together and you have a live, ",
    "AI-debuggable web app.",
]


@chat.handler("ask")
async def ask(session: Session, text: str = "") -> dict:
    """Stream a reply chunk-by-chunk."""
    history = session.state.setdefault("chat", [])
    history.append({"role": "user", "text": text})

    msg_id = len(history)
    await session.call("home.startReply", msg_id)
    collected = []
    for chunk in _CANNED_REPLIES:
        await asyncio.sleep(0.3)
        collected.append(chunk)
        await session.call("home.appendReply", msg_id, chunk)
    await session.call("home.finishReply", msg_id)
    history.append({"role": "assistant", "text": "".join(collected)})
    return {"ok": True}


@chat.handler("history")
async def history(session: Session) -> dict:
    await session.call("home.setHistory", session.state.get("chat", []))
    return {"ok": True}


stage.add_view("/", "home.vue")

if __name__ == "__main__":
    stage.run()
