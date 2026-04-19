"""Sample 06 — streaming chat response.

Demonstrates a long-running server-side task that pushes tokens one
at a time over the WebSocket. No buffering, no polling — the client
sees each chunk as it is generated.
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

ws = WSRouter(prefix="chat")

_CANNED_REPLIES = [
    "llming-stage gives you the ",
    "frontend shell; llming-com ",
    "gives you the wire. Put them ",
    "together and you have a live, ",
    "AI-debuggable web app.",
]


@ws.handler("ask")
async def ask(controller: BaseController, text: str = "") -> dict:
    """Stream a reply chunk-by-chunk."""
    entry: SampleSession = controller.entry  # type: ignore[attr-defined]
    history = entry.state.setdefault("chat", [])
    history.append({"role": "user", "text": text})

    msg_id = len(history)
    await controller.send({"type": "chat.start", "id": msg_id})
    collected = []
    for chunk in _CANNED_REPLIES:
        await asyncio.sleep(0.3)
        collected.append(chunk)
        await controller.send({"type": "chat.delta", "id": msg_id, "delta": chunk})
    await controller.send({"type": "chat.done", "id": msg_id})
    history.append({"role": "assistant", "text": "".join(collected)})
    return {"ok": True}


@ws.handler("history")
async def history(controller: BaseController) -> dict:
    entry: SampleSession = controller.entry  # type: ignore[attr-defined]
    return {"messages": entry.state.get("chat", [])}


app, registry, auth = bootstrap(
    app_name="sample06",
    title="Sample 06 — Streaming chat",
    routes=[("/", "home")],
    view_modules={"home": "/app-static/home.js"},
    preload_views=["home"],
    static_dir=HERE / "static",
    ws_router=ws,
)


if __name__ == "__main__":
    run(app)
