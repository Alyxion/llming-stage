"""Shared support used by reactive samples.

Keeps each sample's ``main.py`` focused on what it demonstrates.
The usual shape is now provided by ``Stage.session(...)``:

    GET  /                    → SPA shell (llming-stage)
    GET  /api/session         → creates a session, sets the auth cookie,
                                returns {sessionId, wsUrl}. View JS
                                fetches this on mount.
    WS   /ws/{session_id}     → llming-com WebSocket session.
    GET  /_stage/app/*.js     → view modules rendered from root-level .vue files.

The compatibility ``bootstrap`` helper remains for lower-level tests and
custom wiring, but public samples should prefer ``Stage.session(...)``.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from llming_com import (
    AuthManager,
    BaseLlmingApp,
    BaseController,
    BaseSessionEntry,
    BaseSessionRegistry,
    CommandScope,
    build_command_router,
    command,
    run_websocket_session,
)
from llming_com.ws_router import AppRouter, SessionRouter

from llming_stage import ShellConfig, Stage, is_debug_enabled, mount_assets, mount_shell

# Per-process version string appended to legacy view-module URLs. New
# samples use root-level .vue files through Stage; this remains for the
# low-level compatibility path.
_VIEW_VERSION = os.environ.get("STAGE_VIEW_VERSION", str(int(time.time() * 1000)))
_PROCESS_AUTH_SECRET = "llming_stage_sample_" + secrets.token_urlsafe(32)


@dataclass
class SampleSession(BaseSessionEntry):
    """Session entry shared across samples.

    `state` is a scratch dict every sample writes into — counters,
    uploaded filenames, chat history, chart data.
    """

    app_type: str = "stage-sample"
    nickname: str = ""
    state: dict[str, Any] = field(default_factory=dict)


class SampleRegistry(BaseSessionRegistry[SampleSession]):
    pass


class SampleController(BaseController):
    """Sample-specific controller hook point; dispatch is provided by llming-com."""


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
# reactive sample. Expose the session's reactive surface to
# AI agents and tests over HTTP.
# ---------------------------------------------------------------------------


if is_debug_enabled():

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
    view_modules: dict[str, str] | None = None,
    static_dir: Path | None = None,
    view_sources: dict[str, str | Path] | None = None,
    ws_router: SessionRouter | None = None,
    app_router: AppRouter | None = None,
    preload_views: list[str] | None = None,
    on_connect_extra: Callable[[SampleSession, WebSocket], Awaitable[None]] | None = None,
    on_disconnect_extra: Callable[[str, SampleSession], Awaitable[None]] | None = None,
) -> tuple[FastAPI, SampleRegistry, AuthManager]:
    """Build a FastAPI app wired for a llming-stage + llming-com sample.

    Prefer *view_sources*: it maps logical view names (used in *routes*)
    to root-relative ``.vue`` / ``.html`` / ``.js`` source files rendered
    by :class:`llming_stage.Stage`.

    *view_modules* + *static_dir* is kept only for compatibility tests
    and lower-level integrations, not for normal samples.

    *ws_router* is the root :class:`SessionRouter` whose handlers are dispatched
    for every message this session receives over its WebSocket. Pass
    ``None`` for samples that don't need reactive server-side logic.
    """
    app = FastAPI()
    registry = SampleRegistry.get()
    llming_app = BaseLlmingApp(registry)
    auth = AuthManager(
        secret=os.environ.get("LLMING_AUTH_SECRET") or _PROCESS_AUTH_SECRET,
        app_name=app_name,
    )
    ws_locks: dict[str, asyncio.Lock] = {}

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
            f"{app_name}_auth",
            token,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
        )
        return resp

    @app.websocket("/ws/{session_id}")
    async def ws_endpoint(websocket: WebSocket, session_id: str) -> None:
        auth_session_id = auth.get_auth_session_id(websocket)
        if auth_session_id != session_id:
            await websocket.close(code=4401, reason="Missing or invalid session cookie")
            return
        lock = ws_locks.setdefault(session_id, asyncio.Lock())
        if lock.locked():
            await websocket.close(code=4409, reason="Session already has a WebSocket")
            return

        async def on_connect(entry: SampleSession, ws: WebSocket) -> None:
            controller = SampleController(session_id)
            controller.set_websocket(ws)
            controller.attach_session(entry)
            controller.attach_app(llming_app)
            if ws_router is not None:
                controller.mount_session_router(ws_router)
            if app_router is not None:
                controller.mount_app_router(app_router)
            await controller.send({"type": "welcome", "session_id": session_id})
            if on_connect_extra is not None:
                await on_connect_extra(entry, ws)

        async def on_message(entry: SampleSession, msg: dict[str, Any]) -> None:
            if entry.controller is None:
                return
            await entry.controller.handle_message(msg)

        async def on_disconnect(sid: str, entry: SampleSession) -> None:
            if on_disconnect_extra is not None:
                await on_disconnect_extra(sid, entry)

        async with lock:
            entry = registry.get_session(session_id)
            if entry is not None and getattr(entry, "websocket", None) is not None:
                await websocket.close(code=4409, reason="Session already has a WebSocket")
                return
            await run_websocket_session(
                websocket,
                session_id,
                registry,
                on_connect=on_connect,
                on_message=on_message,
                on_disconnect=on_disconnect,
                supersede_existing=False,
            )

    # Mount the command router only in explicit debug mode. The shared
    # commands below expose state and raw WS dispatch, so they must never
    # exist in normal sample runs.
    if is_debug_enabled():
        async def command_auth(request: Request) -> SampleSession:
            auth_session_id = auth.get_auth_session_id(request)
            if not auth_session_id:
                raise HTTPException(
                    status_code=401,
                    detail="missing or invalid session cookie",
                )
            path_session_id = request.path_params.get("session_id")
            if (
                path_session_id
                and path_session_id != "current"
                and path_session_id != auth_session_id
            ):
                raise HTTPException(
                    status_code=401,
                    detail="missing or invalid session cookie",
                )
            session = registry.get_session(auth_session_id)
            if session is None:
                raise HTTPException(status_code=401, detail="session not found")
            return session

        app.include_router(
            build_command_router(
                registry,
                prefix="/cmd",
                auth_dependency=command_auth,
            )
        )

    if view_sources is not None:
        root = static_dir if static_dir is not None else Path.cwd()
        stage = Stage(app, root=root, title=title)
        by_name = dict(view_sources)
        for route, view_name in routes:
            stage.add_view(route, by_name[view_name], name=view_name)
    else:
        if view_modules is None or static_dir is None:
            raise ValueError("bootstrap requires view_sources or view_modules + static_dir")
        mount_assets(app)
        app.mount("/app-static", StaticFiles(directory=str(static_dir)), name="app-static")
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

    resolved_port = port if port is not None else int(os.environ.get("PORT", "8765"))
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
