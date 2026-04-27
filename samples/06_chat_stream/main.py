"""Sample 06 — streaming chat response.

Demonstrates a long-running server-side task that pushes tokens one
at a time over the WebSocket. No buffering, no polling — the client
sees each chunk as it is generated.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from llming_com import SessionRouter

from samples._common import SampleSession, bootstrap, run

HERE = Path(__file__).resolve().parent

ws = SessionRouter(prefix="chat")

_CANNED_REPLIES = [
    "llming-stage gives you the ",
    "frontend shell; llming-com ",
    "gives you the wire. Put them ",
    "together and you have a live, ",
    "AI-debuggable web app.",
]


@ws.handler("ask")
async def ask(session: SampleSession, text: str = "") -> dict:
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


@ws.handler("history")
async def history(session: SampleSession) -> dict:
    await session.call("home.setHistory", session.state.get("chat", []))
    return {"ok": True}


app, registry, auth = bootstrap(
    app_name="sample06",
    title="Sample 06 — Streaming chat",
    routes=[("/", "home")],
    view_sources={"home": "home.vue"},
    static_dir=HERE,
    ws_router=ws,
)


if __name__ == "__main__":
    run(app, sample_dir=HERE)
