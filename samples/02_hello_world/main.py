"""Sample 02 — hello_world.

Minimum viable llming-com integration, inline in one file:

- One frontend → backend call:  ``hello.say`` replies with a greeting.
- One backend → frontend push:  a per-session timer task emits
  ``tick`` messages every second while the socket is open.

**Note on timers.** llming-com does not (today) ship a unified
per-session scheduler — only TTL cleanup and heartbeat ack. The
idiomatic pattern, shown here, is to ``asyncio.create_task(...)``
in the WebSocket ``on_connect`` hook and cancel it from
``on_disconnect``.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from llming_com import (
    AuthManager,
    BaseController,
    BaseSessionEntry,
    BaseSessionRegistry,
    CommandScope,
    build_command_router,
    command,
    run_websocket_session,
)
from llming_com.ws_router import WSRouter

from llming_stage import ShellConfig, mount_assets, mount_shell

HERE = Path(__file__).resolve().parent
os.environ.setdefault("LLMING_AUTH_SECRET", "dev-secret-please-change")


@dataclass
class Session(BaseSessionEntry):
    tick_task: Any = field(default=None, repr=False)


class Registry(BaseSessionRegistry[Session]):
    pass


# --- the ONE command the client can call ---------------------------------
ws = WSRouter(prefix="hello")


@ws.handler("say")
async def say(controller: BaseController, name: str = "world") -> dict:
    await controller.send({"type": "hello.reply", "text": f"Hello, {name}!"})
    return {"ok": True}


# --- debug-control surface ------------------------------------------------
# AI agents and tests can drive the session over HTTP without holding the
# WebSocket by invoking these @command endpoints on /cmd/sessions/{sid}/…
@command("debug.state", scope=CommandScope.SESSION, http_method="GET", app="hello")
async def _state(entry: Session) -> dict:
    return {
        "controller_ready": entry.controller is not None,
        "tick_task_done": entry.tick_task is None or entry.tick_task.done(),
    }


@command("debug.ws_dispatch", scope=CommandScope.SESSION, http_method="POST", app="hello")
async def _ws_dispatch(controller: BaseController, msg: dict) -> dict:
    if controller is None:
        return {"ok": False, "error": "no active controller"}
    await controller.handle_message(msg)
    return {"ok": True, "dispatched": msg.get("type", "")}


# --- app wiring -----------------------------------------------------------
app = FastAPI()
registry = Registry.get()
auth = AuthManager(app_name="hello")

mount_assets(app)
app.mount("/app-static", StaticFiles(directory=str(HERE / "static")), name="app-static")


@app.get("/api/session")
async def new_session(request: Request) -> JSONResponse:
    sid = auth.get_auth_session_id(request)
    if not sid or not registry.get_session(sid):
        sid = str(uuid.uuid4())
        registry.register(sid, Session(user_id=f"user-{sid[:8]}"))
    token = auth.sign_auth_token(sid)
    scheme = "wss" if request.url.scheme == "https" else "ws"
    resp = JSONResponse({"sessionId": sid, "wsUrl": f"{scheme}://{request.url.netloc}/ws/{sid}"})
    resp.set_cookie("hello_auth", token, httponly=True, samesite="lax")
    return resp


async def tick_loop(controller: BaseController) -> None:
    """Per-session timer — BE → FE push every second."""
    n = 0
    while True:
        sent = await controller.send({"type": "tick", "n": n})
        if not sent:
            return  # socket closed
        n += 1
        await asyncio.sleep(1)


@app.websocket("/ws/{session_id}")
async def ws_endpoint(websocket: WebSocket, session_id: str) -> None:
    async def on_connect(entry: Session, socket: WebSocket) -> None:
        controller = BaseController(session_id)
        controller.set_websocket(socket)
        controller.mount_router(ws)
        controller.entry = entry  # type: ignore[attr-defined]
        entry.controller = controller
        entry.tick_task = asyncio.create_task(tick_loop(controller))

    async def on_message(entry: Session, msg: dict) -> None:
        if entry.controller is not None:
            await entry.controller.handle_message(msg)

    async def on_disconnect(sid: str, entry: Session) -> None:
        if entry.tick_task is not None:
            entry.tick_task.cancel()

    await run_websocket_session(
        websocket, session_id, registry,
        on_connect=on_connect, on_message=on_message, on_disconnect=on_disconnect,
    )


# Mount the command router — this exposes the @command handlers as HTTP
# routes under /cmd and, for any that were registered with an MCP tag,
# as MCP tools for AI agents.
app.include_router(build_command_router(registry, prefix="/cmd"))


mount_shell(
    app,
    config=ShellConfig(
        title="Sample 02 — Hello world",
        routes=[("/", "home")],
        view_modules={"home": "/app-static/home.js"},
        preload_views=["home"],
    ),
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8080")))
