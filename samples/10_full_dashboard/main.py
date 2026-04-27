"""Sample 10 — capstone dashboard.

Multi-view SPA combining everything the earlier samples demonstrated
in isolation:

- Four views (``/``, ``/metric``, ``/uploads``, ``/chat``) sharing
  **one WebSocket session per user**.
- Three :class:`SessionRouter` namespaces (``metric``, ``uploads``,
  ``chat``) composed onto the session's controller via
  ``SessionRouter.include(...)``.
- One :class:`AppRouter` namespace (``admin``) for app-scoped broadcast.
- One cookie-authed HTTP endpoint (``/api/upload``) for large file
  transfer — the only HTTP route apart from the shell/assets.
- Plotly and KaTeX lazy-loaded on first use.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import random
import time
from pathlib import Path

from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from llming_com import AppRouter, BaseLlmingApp, SessionRouter

from samples._common import SampleSession, bootstrap, run

HERE = Path(__file__).resolve().parent

# ---- metric router -------------------------------------------------------
metric = SessionRouter(prefix="metric")


async def _stream_metrics(session: SampleSession) -> None:
    t0 = time.monotonic()

    async def sample() -> bool:
        t = time.monotonic() - t0
        value = math.sin(t / 2) + random.gauss(0, 0.1)
        return await session.call(
            "metric.addMetricSample", round(t, 3), round(value, 4)
        )

    session.start_timer("metric_task", 0.5, sample)


@metric.handler("start")
async def metric_start(session: SampleSession) -> dict:
    task = session.state.get("metric_task")
    if task and not task.done():
        return {"ok": True, "already_running": True}
    await _stream_metrics(session)
    return {"ok": True}


@metric.handler("stop")
async def metric_stop(session: SampleSession) -> dict:
    session.cancel_timer("metric_task")
    return {"ok": True}


# ---- uploads router ------------------------------------------------------
uploads = SessionRouter(prefix="uploads")


@uploads.handler("list")
async def uploads_list(session: SampleSession) -> dict:
    await session.call("uploads.setUploads", session.state.get("uploads", []))
    return {"ok": True}


# ---- chat router ---------------------------------------------------------
chat = SessionRouter(prefix="chat")

_REPLIES = [
    "Welcome to the capstone. ",
    "This single tab is running four views, ",
    "one WebSocket, and one session. ",
    "Navigate around — everything survives.",
]


@chat.handler("ask")
async def chat_ask(session: SampleSession, text: str = "") -> dict:
    history = session.state.setdefault("chat", [])
    history.append({"role": "user", "text": text})
    msg_id = len(history)
    await session.call("chat.startReply", msg_id)
    collected = []
    for chunk in _REPLIES:
        await asyncio.sleep(0.25)
        collected.append(chunk)
        await session.call("chat.appendReply", msg_id, chunk)
    await session.call("chat.finishReply", msg_id)
    history.append({"role": "assistant", "text": "".join(collected)})
    return {"ok": True}


@chat.handler("history")
async def chat_history(session: SampleSession) -> dict:
    await session.call("chat.setHistory", session.state.get("chat", []))
    return {"ok": True}


# ---- assemble ------------------------------------------------------------
root = SessionRouter()
root.include(metric)
root.include(uploads)
root.include(chat)


# ---- app router ---------------------------------------------------------
admin = AppRouter(prefix="admin")


@admin.handler("broadcast")
async def admin_broadcast(
    app: BaseLlmingApp[SampleSession],
    message: str = "Broadcast from the app router",
) -> dict:
    sent = await app.broadcast("home.setBroadcast", message)
    return {"ok": True, "sent": sent}


app, registry, auth = bootstrap(
    app_name="sample10",
    title="Sample 10 — Capstone dashboard",
    routes=[
        ("/", "home"),
        ("/metric", "metric"),
        ("/uploads", "uploads"),
        ("/chat", "chat"),
    ],
    view_sources={
        "home": "home.vue",
        "metric": "metric.vue",
        "uploads": "uploads.vue",
        "chat": "chat.vue",
    },
    static_dir=HERE,
    ws_router=root,
    app_router=admin,
)


@app.post("/api/upload")
async def upload(request: Request, file: UploadFile) -> JSONResponse:
    session_id = auth.get_auth_session_id(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="missing or invalid session cookie")
    entry = registry.get_session(session_id)
    if entry is None:
        raise HTTPException(status_code=401, detail="session not found")

    hasher = hashlib.sha256()
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        hasher.update(chunk)
        total += len(chunk)
        await entry.call("uploads.setProgress", file.filename, total)

    digest = hasher.hexdigest()
    record = {"name": file.filename, "bytes": total, "sha256": digest}
    entry.state.setdefault("uploads", []).append(record)
    await entry.call("uploads.finishUpload", record)
    return JSONResponse(record)


if __name__ == "__main__":
    run(app, sample_dir=HERE)
