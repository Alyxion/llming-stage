"""Sample 10 — capstone dashboard.

Multi-view SPA combining everything the earlier samples demonstrated
in isolation:

- Four views (``/``, ``/metric``, ``/uploads``, ``/chat``) sharing
  **one WebSocket session per user**.
- Three :class:`WSRouter` namespaces (``metric``, ``uploads``,
  ``chat``) composed onto the session's controller via
  ``WSRouter.include(...)``.
- One cookie-authed HTTP endpoint (``/api/upload``) for large file
  transfer — the only HTTP route apart from the shell/assets.
- Plotly and KaTeX lazy-loaded on first use.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import random
import sys
import time
from pathlib import Path

from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from llming_com import BaseController
from llming_com.ws_router import WSRouter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _common import SampleSession, bootstrap, run  # noqa: E402

HERE = Path(__file__).resolve().parent

# ---- metric router -------------------------------------------------------
metric = WSRouter(prefix="metric")


async def _stream_metrics(controller: BaseController) -> None:
    t0 = time.monotonic()
    while True:
        t = time.monotonic() - t0
        value = math.sin(t / 2) + random.gauss(0, 0.1)
        sent = await controller.send(
            {"type": "metric.sample", "t": round(t, 3), "value": round(value, 4)}
        )
        if not sent:
            return
        await asyncio.sleep(0.5)


@metric.handler("start")
async def metric_start(controller: BaseController) -> dict:
    entry: SampleSession = controller.entry  # type: ignore[attr-defined]
    task = entry.state.get("metric_task")
    if task and not task.done():
        return {"ok": True, "already_running": True}
    entry.state["metric_task"] = asyncio.create_task(_stream_metrics(controller))
    return {"ok": True}


@metric.handler("stop")
async def metric_stop(controller: BaseController) -> dict:
    entry: SampleSession = controller.entry  # type: ignore[attr-defined]
    task = entry.state.get("metric_task")
    if task and not task.done():
        task.cancel()
    return {"ok": True}


# ---- uploads router ------------------------------------------------------
uploads = WSRouter(prefix="uploads")


@uploads.handler("list")
async def uploads_list(controller: BaseController) -> dict:
    entry: SampleSession = controller.entry  # type: ignore[attr-defined]
    return {"items": entry.state.get("uploads", [])}


# ---- chat router ---------------------------------------------------------
chat = WSRouter(prefix="chat")

_REPLIES = [
    "Welcome to the capstone. ",
    "This single tab is running four views, ",
    "one WebSocket, and one session. ",
    "Navigate around — everything survives.",
]


@chat.handler("ask")
async def chat_ask(controller: BaseController, text: str = "") -> dict:
    entry: SampleSession = controller.entry  # type: ignore[attr-defined]
    history = entry.state.setdefault("chat", [])
    history.append({"role": "user", "text": text})
    msg_id = len(history)
    await controller.send({"type": "chat.start", "id": msg_id})
    collected = []
    for chunk in _REPLIES:
        await asyncio.sleep(0.25)
        collected.append(chunk)
        await controller.send({"type": "chat.delta", "id": msg_id, "delta": chunk})
    await controller.send({"type": "chat.done", "id": msg_id})
    history.append({"role": "assistant", "text": "".join(collected)})
    return {"ok": True}


@chat.handler("history")
async def chat_history(controller: BaseController) -> dict:
    entry: SampleSession = controller.entry  # type: ignore[attr-defined]
    return {"messages": entry.state.get("chat", [])}


# ---- assemble ------------------------------------------------------------
root = WSRouter()
root.include(metric)
root.include(uploads)
root.include(chat)


app, registry, auth = bootstrap(
    app_name="sample10",
    title="Sample 10 — Capstone dashboard",
    routes=[
        ("/", "home"),
        ("/metric", "metric"),
        ("/uploads", "uploads"),
        ("/chat", "chat"),
    ],
    view_modules={
        "home": "/app-static/home.js",
        "metric": "/app-static/metric.js",
        "uploads": "/app-static/uploads.js",
        "chat": "/app-static/chat.js",
    },
    preload_views=["home"],
    static_dir=HERE / "static",
    ws_router=root,
)


@app.post("/api/upload")
async def upload(request: Request, file: UploadFile) -> JSONResponse:
    session_id = auth.get_auth_session_id(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="missing or invalid session cookie")
    entry = registry.get_session(session_id)
    if entry is None:
        raise HTTPException(status_code=401, detail="session not found")

    controller = entry.controller
    hasher = hashlib.sha256()
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        hasher.update(chunk)
        total += len(chunk)
        if controller is not None:
            await controller.send(
                {"type": "upload.progress", "name": file.filename, "bytes": total}
            )

    digest = hasher.hexdigest()
    record = {"name": file.filename, "bytes": total, "sha256": digest}
    entry.state.setdefault("uploads", []).append(record)
    if controller is not None:
        await controller.send({"type": "upload.done", **record})
    return JSONResponse(record)


if __name__ == "__main__":
    run(app)
