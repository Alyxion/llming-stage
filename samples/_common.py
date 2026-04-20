"""Shared wiring used by samples 02-10.

Keeps each sample's ``main.py`` focused on what it demonstrates, not on
session plumbing. Import as ``from samples._common import bootstrap``.

The shape every sample follows:

    GET  /                    → SPA shell (llming-stage)
    GET  /api/session         → creates a session, sets the auth cookie,
                                returns {sessionId, wsUrl}. View JS
                                fetches this on mount.
    POST /cmd/...             → llming-com HTTP command endpoints.
    WS   /ws/{session_id}     → llming-com WebSocket session.
    GET  /app-static/*        → the sample's own view JS.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable


# Per-process version string appended to every view-module URL. Two
# sample subprocesses started at different times on the same port would
# otherwise collide on browser cache (``/app-static/home.js`` is the
# same URL for every sample), and the second sample would run the
# previous sample's view JS inside the iframe.
_VIEW_VERSION = os.environ.get("STAGE_VIEW_VERSION", str(int(time.time() * 1000)))

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


@dataclass
class SampleSession(BaseSessionEntry):
    """Session entry shared across samples.

    `state` is a scratch dict every sample writes into — counters,
    uploaded filenames, chat history, chart data.
    """

    nickname: str = ""
    state: dict[str, Any] = field(default_factory=dict)


class SampleRegistry(BaseSessionRegistry[SampleSession]):
    pass


class SampleController(BaseController):
    """Dispatches incoming messages to llming-com commands.

    Override ``on_message`` in a subclass if a sample needs custom
    dispatch. The default handles heartbeats and falls through to the
    mounted command registry.
    """


def _with_version(url: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}v={_VIEW_VERSION}"


def _jsonable(value: Any) -> Any:
    """Best-effort conversion of session state into JSON-safe values.

    Sessions may hold things like ``asyncio.Task`` handles that cannot
    be serialised. We replace them with a short descriptor so the
    debug endpoint never 500s on an otherwise healthy session.
    """
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return f"<{type(value).__name__}>"


# ---------------------------------------------------------------------------
# Debug commands — registered once (at module import), mounted by every
# sample that calls bootstrap(). Expose the session's reactive surface to
# AI agents and tests over HTTP.
# ---------------------------------------------------------------------------


@command(
    "debug.state",
    description="Return the session's current state dict.",
    scope=CommandScope.SESSION,
    http_method="GET",
    app="stage-sample",
)
async def _debug_state(entry: SampleSession) -> dict[str, Any]:
    return {
        "nickname": entry.nickname,
        "state": _jsonable(entry.state),
        "controller_ready": entry.controller is not None,
    }


@command(
    "debug.ws_dispatch",
    description="Dispatch a raw WS message through the session's router.",
    scope=CommandScope.SESSION,
    http_method="POST",
    app="stage-sample",
)
async def _debug_ws_dispatch(controller: BaseController, msg: dict) -> dict[str, Any]:
    if controller is None:
        return {"ok": False, "error": "no active controller"}
    await controller.handle_message(msg)
    return {"ok": True, "dispatched": msg.get("type", "")}


def bootstrap(
    *,
    app_name: str,
    title: str,
    routes: list[tuple[str, str]],
    view_modules: dict[str, str],
    static_dir: Path,
    ws_router: WSRouter | None = None,
    preload_views: list[str] | None = None,
    on_connect_extra: Callable[[SampleSession, WebSocket], Awaitable[None]] | None = None,
) -> tuple[FastAPI, SampleRegistry, AuthManager]:
    """Build a FastAPI app wired for a llming-stage + llming-com sample.

    *static_dir* is mounted at ``/app-static`` — every sample's view JS
    lives there. *view_modules* maps logical view names (used in
    *routes*) to their JS URLs under ``/app-static``.

    *ws_router* is the root :class:`WSRouter` whose handlers are dispatched
    for every message this session receives over its WebSocket. Pass
    ``None`` for samples that don't need reactive server-side logic.
    """
    os.environ.setdefault("LLMING_AUTH_SECRET", "dev-secret-please-change")

    app = FastAPI()
    registry = SampleRegistry.get()
    auth = AuthManager(app_name=app_name)

    mount_assets(app)

    app.mount("/app-static", StaticFiles(directory=str(static_dir)), name="app-static")

    @app.get("/api/session")
    async def create_session(request: Request) -> JSONResponse:
        existing = auth.get_auth_session_id(request)
        if existing and registry.get_session(existing):
            session_id = existing
            token = auth.sign_auth_token(session_id)
        else:
            session_id = str(uuid.uuid4())
            entry = SampleSession(user_id=f"user-{session_id[:8]}")
            registry.register(session_id, entry)
            token = auth.sign_auth_token(session_id)
        ws_scheme = "wss" if request.url.scheme == "https" else "ws"
        ws_url = f"{ws_scheme}://{request.url.netloc}/ws/{session_id}"
        resp = JSONResponse({"sessionId": session_id, "wsUrl": ws_url})
        resp.set_cookie(
            f"{app_name}_auth", token, httponly=True, samesite="lax"
        )
        return resp

    @app.websocket("/ws/{session_id}")
    async def ws_endpoint(websocket: WebSocket, session_id: str) -> None:
        async def on_connect(entry: SampleSession, ws: WebSocket) -> None:
            controller = SampleController(session_id)
            controller.set_websocket(ws)
            if ws_router is not None:
                controller.mount_router(ws_router)
            entry.controller = controller
            # Make the session entry reachable from every WSRouter handler
            # via `controller.entry` (conventional access pattern).
            controller.entry = entry  # type: ignore[attr-defined]
            await controller.send({"type": "welcome", "session_id": session_id})
            if on_connect_extra is not None:
                await on_connect_extra(entry, ws)

        async def on_message(entry: SampleSession, msg: dict[str, Any]) -> None:
            if entry.controller is None:
                return
            await entry.controller.handle_message(msg)

        await run_websocket_session(
            websocket,
            session_id,
            registry,
            on_connect=on_connect,
            on_message=on_message,
        )

    # Mount the command router so @command handlers (including the shared
    # debug.state + debug.ws_dispatch defined above) are reachable over HTTP.
    # AI agents — and the e2e test suite — drive WebSocket sessions through
    # /cmd/sessions/{sid}/debug.ws_dispatch without holding the socket.
    app.include_router(build_command_router(registry, prefix="/cmd"))

    versioned = {name: _with_version(url) for name, url in view_modules.items()}
    config = ShellConfig(
        title=title,
        routes=routes,
        view_modules=versioned,
        preload_views=preload_views or [],
    )
    mount_shell(app, config=config)

    return app, registry, auth


def run(
    app: FastAPI,
    *,
    port: int | None = None,
    module: str = "main",
    sample_dir: Path | None = None,
) -> None:
    """Run the sample under uvicorn with file-watch hot reload.

    ``module`` is the Python module name (inside *sample_dir*) that
    exposes ``app``. Caller passes ``__file__`` via *sample_dir* so
    we know which directory uvicorn should watch.

    Reload can be disabled via ``STAGE_RELOAD=0`` — tests do this so
    subprocess teardown is deterministic.
    """
    import uvicorn

    resolved_port = port if port is not None else int(os.environ.get("PORT", "8080"))
    reload = os.environ.get("STAGE_RELOAD", "1") != "0"

    if not reload:
        uvicorn.run(app, host="127.0.0.1", port=resolved_port, log_level="info")
        return

    # Reload needs an import string + an app_dir so uvicorn can re-import.
    if sample_dir is None:
        raise ValueError("sample_dir is required for reload mode")
    uvicorn.run(
        f"{module}:app",
        host="127.0.0.1",
        port=resolved_port,
        reload=True,
        reload_dirs=[str(sample_dir)],
        app_dir=str(sample_dir),
        log_level="info",
    )
