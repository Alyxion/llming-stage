"""Capstone dashboard.

Multi-view SPA combining everything the earlier samples demonstrated
in isolation:

- Four views (``/``, ``/metric``, ``/uploads``, ``/chat``) sharing
  **one WebSocket session per user**.
- Three Stage-owned session router namespaces (``metric``, ``uploads``,
  ``chat``).
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

from fastapi import Depends, FastAPI, UploadFile
from fastapi.responses import JSONResponse
from llming_com import BaseLlmingApp
from llming_stage import Stage

from samples._common import SampleSession, run

HERE = Path(__file__).resolve().parent

app = FastAPI()
stage = Stage(app, root=HERE, title="Capstone dashboard")
sessions = stage.session(app_name="capstone", session_cls=SampleSession)

# ---- metric router -------------------------------------------------------
metric = sessions.router("metric")


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
uploads = sessions.router("uploads")


@uploads.handler("list")
async def uploads_list(session: SampleSession) -> dict:
    await session.call("uploads.setUploads", session.state.get("uploads", []))
    return {"ok": True}


# ---- chat router ---------------------------------------------------------
chat = sessions.router("chat")

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


# ---- app router ---------------------------------------------------------
admin = sessions.app_router("admin")


@admin.handler("broadcast")
async def admin_broadcast(
    app: BaseLlmingApp[SampleSession],
    message: str = "Broadcast from the app router",
) -> dict:
    sent = await app.broadcast("home.setBroadcast", message)
    return {"ok": True, "sent": sent}


@app.post("/api/upload")
async def upload(
    file: UploadFile,
    session: SampleSession = Depends(sessions.require_session),
) -> JSONResponse:
    hasher = hashlib.sha256()
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        hasher.update(chunk)
        total += len(chunk)
        await session.call("uploads.setProgress", file.filename, total)

    digest = hasher.hexdigest()
    record = {"name": file.filename, "bytes": total, "sha256": digest}
    session.state.setdefault("uploads", []).append(record)
    await session.call("uploads.finishUpload", record)
    return JSONResponse(record)


stage.view("/", "home.vue")
stage.view("/metric", "metric.vue")
stage.view("/uploads", "uploads.vue")
stage.view("/chat", "chat.vue")


if __name__ == "__main__":
    run(app, sample_dir=HERE)
