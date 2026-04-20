"""Sample 03 — counter with server-side state.

Two WS handlers: ``counter.inc`` increments the session's counter and
pushes the new value; ``counter.reset`` resets it. State lives on
:class:`SampleSession.state` — so it is per-user, server-held, and
inspectable through the debug API.
"""

from __future__ import annotations

import sys
from pathlib import Path

from llming_com import BaseController
from llming_com.ws_router import WSRouter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _common import SampleSession, bootstrap, run  # noqa: E402

HERE = Path(__file__).resolve().parent

ws = WSRouter(prefix="counter")


@ws.handler("inc")
async def inc(controller: BaseController, by: int = 1) -> dict:
    entry: SampleSession = controller.entry  # type: ignore[attr-defined]
    entry.state["count"] = int(entry.state.get("count", 0)) + int(by)
    await controller.send({"type": "counter.update", "value": entry.state["count"]})
    return {"ok": True}


@ws.handler("reset")
async def reset(controller: BaseController) -> dict:
    entry: SampleSession = controller.entry  # type: ignore[attr-defined]
    entry.state["count"] = 0
    await controller.send({"type": "counter.update", "value": 0})
    return {"ok": True}


app, registry, auth = bootstrap(
    app_name="sample03",
    title="Sample 03 — Counter",
    routes=[("/", "home")],
    view_modules={"home": "/app-static/home.js"},
    preload_views=["home"],
    static_dir=HERE / "static",
    ws_router=ws,
)


if __name__ == "__main__":
    run(app, sample_dir=HERE)
