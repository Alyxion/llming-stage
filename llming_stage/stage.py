"""FastAPI/Starlette-native stage application helper."""

from __future__ import annotations

import asyncio
import base64
import inspect
import json
import os
import re
import secrets
import shutil
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route, WebSocketRoute

from .debug import is_debug_enabled, mount_debug
from .dev_reload import DevReloadConfig, mount_dev_reload
from .shell import (
    ShellConfig,
    export_package_assets,
    mount_assets,
    mount_bundle_builder,
    mount_bundles,
    render_shell,
)

_LIB_VERSION_RE = re.compile(r"\d{4}-(0[1-9]|1[0-2])(-\d+)?")
_PROCESS_AUTH_SECRET = "llming_stage_" + secrets.token_urlsafe(32)

_VIEW_EXTENSIONS = {".vue", ".js", ".html", ".htm"}


def _make_auth_manager(app_name: str) -> Any:
    """Create an AuthManager without ever using a known fallback secret."""

    from llming_com import AuthManager

    secret = os.environ.get("LLMING_AUTH_SECRET") or _PROCESS_AUTH_SECRET
    return AuthManager(secret=secret, app_name=app_name)


@dataclass
class _View:
    route: str
    name: str
    source: Path | Callable[[], Any]
    module_url: str
    debug_source: Path | None = None
    debug_module_url: str | None = None


class VueResponse(Response):
    """Response type for generated Vue views.

    Use ``template``/``script``/``style`` for split inline parts, or the
    corresponding ``*_path`` arguments for files relative to the decorated
    Python module. The positional ``content`` form accepts complete Vue
    source and is kept for small one-piece views.
    """

    media_type = "text/x-vue"

    def __init__(
        self,
        content: str | None = None,
        *,
        template: str | None = None,
        template_path: str | Path | None = None,
        script: str | None = None,
        script_path: str | Path | None = None,
        style: str | None = None,
        style_path: str | Path | None = None,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        parts = [content is not None, template is not None, template_path is not None]
        if sum(parts) != 1:
            raise ValueError(
                "VueResponse requires exactly one of content, template, or template_path"
            )
        if script is not None and script_path is not None:
            raise ValueError("VueResponse accepts script or script_path, not both")
        if style is not None and style_path is not None:
            raise ValueError("VueResponse accepts style or style_path, not both")
        if content is not None and any(
            value is not None for value in (script, script_path, style, style_path)
        ):
            raise ValueError(
                "VueResponse content is a complete Vue source; use template/template_path "
                "when adding script or style separately"
            )
        self.template_path = Path(template_path) if template_path is not None else None
        self.script_path = Path(script_path) if script_path is not None else None
        self.style_path = Path(style_path) if style_path is not None else None
        source = content if content is not None else _compose_vue_source(template, script, style)
        super().__init__(
            content=source,
            status_code=status_code,
            headers=headers,
            media_type=self.media_type,
        )

    def resolve_source(self, base: Path) -> str:
        source = self.body.decode(self.charset or "utf-8").strip()
        if self.template_path is not None:
            template = _read_response_part(self.template_path, base, "template")
            script = (
                _read_response_part(self.script_path, base, "script")
                if self.script_path is not None
                else _extract_block(source, "script") or None
            )
            style = (
                _read_response_part(self.style_path, base, "style")
                if self.style_path is not None
                else _extract_block(source, "style") or None
            )
            return _compose_vue_source(template, script, style)
        if self.script_path is not None or self.style_path is not None:
            template = _extract_block(source, "template") or source
            script = (
                _read_response_part(self.script_path, base, "script")
                if self.script_path is not None
                else _extract_block(source, "script") or None
            )
            style = (
                _read_response_part(self.style_path, base, "style")
                if self.style_path is not None
                else _extract_block(source, "style") or None
            )
            return _compose_vue_source(template, script, style)
        return source


class StageSession:
    """Stage-owned llming-com session wiring.

    Normal apps should ask this object for namespaced routers instead of
    assembling root routers manually.
    """

    def __init__(
        self,
        stage: "Stage",
        *,
        app_name: str,
        session_cls: Any,
        registry: Any,
        app_context: Any,
        auth: Any,
        controller_cls: Any,
        command_prefix: str | None,
    ) -> None:
        from llming_com import AppRouter, SessionRouter

        self.stage = stage
        self.app_name = app_name
        self.session_cls = session_cls
        self.registry = registry
        self.app = app_context
        self.auth = auth
        self.controller_cls = controller_cls
        self.session_router = SessionRouter()
        self.application_router = AppRouter()
        self.command_prefix = command_prefix
        # Grace-period removal: when a WebSocket disconnects we schedule
        # the session for removal after this many seconds. A reconnect
        # (e.g. page reload) within the window cancels the task and
        # keeps the session alive. Longer than a typical reload, shorter
        # than llming-com's 5-minute idle TTL so the runner reflects
        # tab-close almost instantly.
        self.disconnect_grace_seconds = 10.0
        self._removal_tasks: dict[str, Any] = {}
        self._ws_locks: dict[str, asyncio.Lock] = {}

        self._mount_internal_debug_handlers()
        self._mount_routes()
        self._mount_command_router()

    def router(self, prefix: str) -> Any:
        """Create and mount a session-scoped router namespace."""
        return self.add_router(prefix)

    def add_router(self, prefix: str) -> Any:
        """Create and mount a session-scoped router namespace."""
        from llming_com import SessionRouter

        child = SessionRouter(prefix=prefix)
        self.session_router.include(child)
        return child

    def app_router(self, prefix: str) -> Any:
        """Create and mount an application-scoped router namespace."""
        return self.add_app_router(prefix)

    def add_app_router(self, prefix: str) -> Any:
        """Create and mount an application-scoped router namespace."""
        from llming_com import AppRouter

        child = AppRouter(prefix=prefix)
        self.application_router.include(child)
        return child

    def _mount_internal_debug_handlers(self) -> None:
        """Handle browser debug messages on the normal session WebSocket."""

        if not is_debug_enabled():
            return
        from . import debug as debug_mod

        @self.session_router.handler("llming.debug.console")
        async def _stage_debug_console(
            session: Any,
            controller: Any,
            level: str = "log",
            text: str = "",
        ) -> None:
            debug_mod.record_js_console(
                getattr(controller, "session_id", "")
                or getattr(session, "session_id", "")
                or _session_id_for_entry(self.registry, session),
                {"level": level, "text": text},
            )

        @self.session_router.handler("llming.debug.eval_result")
        async def _stage_debug_eval_result(
            session: Any,
            controller: Any,
            id: str = "",
            ok: bool = False,
            result: Any = None,
            error: str = "",
        ) -> None:
            debug_mod.record_js_eval_result(
                getattr(controller, "session_id", "")
                or getattr(session, "session_id", "")
                or _session_id_for_entry(self.registry, session),
                {"id": id, "ok": ok, "result": result, "error": error},
            )

    def _cancel_removal(self, session_id: str) -> None:
        task = self._removal_tasks.pop(session_id, None)
        if task is not None and not task.done():
            task.cancel()

    def _drop_ws_lock(self, session_id: str) -> None:
        lock = self._ws_locks.get(session_id)
        if lock is not None and not lock.locked():
            self._ws_locks.pop(session_id, None)

    def _schedule_removal(self, session_id: str) -> None:
        """Drop *session_id* from the registry after the grace period.

        Cancels any in-flight removal first — repeated disconnects on the
        same session reset the timer rather than stacking. After the
        sleep returns we re-check whether the task is still the one
        tracked under *session_id*: a reconnect that ran
        ``_cancel_removal`` plus another disconnect that scheduled a
        *new* task can otherwise race past a CancelledError-less sleep
        return and remove a still-live session.
        """
        self._cancel_removal(session_id)

        task_ref: dict[str, Any] = {}

        async def _drop() -> None:
            try:
                await asyncio.sleep(self.disconnect_grace_seconds)
            except asyncio.CancelledError:
                return
            # Only proceed if our task is still the registered one for
            # this session_id. If a reconnect cancelled+replaced us,
            # the dict entry will point at a different Task object.
            current = self._removal_tasks.get(session_id)
            if current is not task_ref.get("self"):
                return
            self._removal_tasks.pop(session_id, None)
            self.registry.remove(session_id)
            self._drop_ws_lock(session_id)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No loop — synchronous test path. Remove eagerly.
            self.registry.remove(session_id)
            self._drop_ws_lock(session_id)
            return
        task = loop.create_task(_drop())
        task_ref["self"] = task
        self._removal_tasks[session_id] = task

    async def require_session(self, request: Request) -> Any:
        """FastAPI dependency returning the current cookie-authenticated session."""

        session_id = self.auth.get_auth_session_id(request)
        if not session_id:
            raise HTTPException(status_code=401, detail="missing or invalid session cookie")
        session = self.registry.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=401, detail="session not found")
        return session

    def _mount_routes(self) -> None:
        from llming_com import run_websocket_session

        async def create_session(request: Request) -> JSONResponse:
            # Per-tab session via `?session=<id>`. Clients (loader.js)
            # generate a per-tab id stored in sessionStorage and pass it
            # here so two tabs of the same browser end up with two
            # distinct sessions. When the hint is registered and the
            # signed auth cookie already proves ownership, we reuse it
            # (tab reload); otherwise we mint a fresh server-side id.
            # The cookie fallback below kicks in only for clients that
            # omit the query string.
            requested = request.query_params.get("session")
            if requested:
                existing = self.auth.get_auth_session_id(request)
                if existing == requested and self.registry.get_session(requested):
                    session_id = requested
                else:
                    session_id = str(uuid.uuid4())
                    entry = self.session_cls(user_id=f"user-{session_id[:8]}")
                    self.registry.register(session_id, entry)
            else:
                existing = self.auth.get_auth_session_id(request)
                if existing and self.registry.get_session(existing):
                    session_id = existing
                else:
                    session_id = str(uuid.uuid4())
                    entry = self.session_cls(user_id=f"user-{session_id[:8]}")
                    self.registry.register(session_id, entry)
            token = self.auth.sign_auth_token(session_id)
            ws_scheme = "wss" if request.url.scheme == "https" else "ws"
            ws_url = f"{ws_scheme}://{request.url.netloc}/ws/{session_id}"
            resp = JSONResponse({"sessionId": session_id, "wsUrl": ws_url})
            resp.set_cookie(
                f"{self.app_name}_auth",
                token,
                httponly=True,
                samesite="lax",
                secure=request.url.scheme == "https",
            )
            return resp

        async def ws_endpoint(websocket: Any) -> None:
            session_id = websocket.path_params["session_id"]
            auth_session_id = self.auth.get_auth_session_id(websocket)
            if auth_session_id != session_id:
                await websocket.close(code=4401, reason="Missing or invalid session cookie")
                return
            lock = self._ws_locks.setdefault(session_id, asyncio.Lock())
            if lock.locked():
                await websocket.close(code=4409, reason="Session already has a WebSocket")
                return

            async def on_connect(entry: Any, ws: Any) -> None:
                # A pending disconnect-removal for this session means the
                # tab just reloaded — cancel the timer and reuse the
                # entry as if nothing happened.
                self._cancel_removal(session_id)
                controller = self.controller_cls(session_id)
                controller.set_websocket(ws)
                controller.attach_session(entry)
                controller.attach_app(self.app)
                controller.mount_session_router(self.session_router)
                controller.mount_app_router(self.application_router)
                await controller.send({"type": "welcome", "session_id": session_id})

            async def on_message(entry: Any, msg: dict[str, Any]) -> None:
                if entry.controller is not None:
                    await entry.controller.handle_message(msg)

            async def on_disconnect(sid: str, entry: Any) -> None:
                # Tab closed / network blip → start a short countdown. A
                # reconnect inside the grace window cancels it.
                self._schedule_removal(sid)

            async with lock:
                entry = self.registry.get_session(session_id)
                if entry is not None and getattr(entry, "websocket", None) is not None:
                    await websocket.close(code=4409, reason="Session already has a WebSocket")
                    return
                await run_websocket_session(
                    websocket,
                    session_id,
                    self.registry,
                    on_connect=on_connect,
                    on_message=on_message,
                    on_disconnect=on_disconnect,
                    supersede_existing=False,
                )

        self.stage._insert_before_shell(Route("/api/session", create_session))
        self.stage._insert_before_shell(WebSocketRoute("/ws/{session_id}", ws_endpoint))

    def _mount_command_router(self) -> None:
        if self.command_prefix is None or not hasattr(self.stage.app, "include_router"):
            return
        from llming_com import build_command_router

        async def command_auth(request: Request) -> Any:
            auth_session_id = self.auth.get_auth_session_id(request)
            if not auth_session_id:
                raise HTTPException(status_code=401, detail="missing or invalid session cookie")
            path_session_id = request.path_params.get("session_id")
            if (
                path_session_id
                and path_session_id != "current"
                and path_session_id != auth_session_id
            ):
                raise HTTPException(status_code=401, detail="missing or invalid session cookie")
            session = self.registry.get_session(auth_session_id)
            if session is None:
                raise HTTPException(status_code=401, detail="session not found")
            return session

        self.stage.app.include_router(
            build_command_router(
                self.registry,
                prefix=self.command_prefix,
                auth_dependency=command_auth,
            )
        )
        if not is_debug_enabled():
            return

        prefix = self.command_prefix.rstrip("/")

        async def debug_state(request: Request) -> JSONResponse:
            session_id = request.path_params["session_id"]
            auth_session_id = self.auth.get_auth_session_id(request)
            if auth_session_id != session_id:
                raise HTTPException(status_code=401, detail="missing or invalid session cookie")
            session = self.registry.get_session(session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="session not found")
            return JSONResponse(
                {
                    "state": _jsonable(getattr(session, "state", {})),
                    "controller_ready": getattr(session, "controller", None) is not None,
                }
            )

        async def debug_ws_dispatch(request: Request) -> JSONResponse:
            session_id = request.path_params["session_id"]
            auth_session_id = self.auth.get_auth_session_id(request)
            if auth_session_id != session_id:
                raise HTTPException(status_code=401, detail="missing or invalid session cookie")
            session = self.registry.get_session(session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="session not found")
            controller = getattr(session, "controller", None)
            if controller is None:
                return JSONResponse({"ok": False, "error": "no active controller"})
            body = await request.json()
            msg = body.get("msg", body)
            await controller.handle_message(msg)
            return JSONResponse({"ok": True, "dispatched": msg.get("type", "")})

        self.stage._insert_before_shell(
            Route(f"{prefix}/sessions/{{session_id}}/debug.state", debug_state)
        )
        self.stage._insert_before_shell(
            Route(
                f"{prefix}/sessions/{{session_id}}/debug.ws_dispatch",
                debug_ws_dispatch,
                methods=["POST"],
            )
        )


def _jsonable(value: Any) -> Any:
    """Best-effort conversion of session state into JSON-safe values."""

    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return f"<{type(value).__name__}>"


def _session_id_for_entry(registry: Any, entry: Any) -> str:
    """Best-effort reverse lookup for registries whose entries lack an id field."""

    for attr in ("items", "_sessions", "sessions"):
        candidate = getattr(registry, attr, None)
        try:
            items = candidate() if callable(candidate) else candidate.items()
        except Exception:
            continue
        for session_id, candidate_entry in items:
            if candidate_entry is entry:
                return str(session_id)
    return ""


def _create_fastapi_app(*, title: str, kwargs: dict[str, Any]) -> Any:
    try:
        from fastapi import FastAPI
    except ImportError as exc:
        raise RuntimeError(
            "Stage() without an app requires FastAPI. Pass an existing ASGI app "
            "or install fastapi."
        ) from exc
    signature = inspect.signature(FastAPI)
    invalid = sorted(k for k in kwargs if k not in signature.parameters)
    if invalid:
        names = ", ".join(invalid)
        raise TypeError(f"unknown FastAPI keyword argument(s): {names}")
    fastapi_kwargs = dict(kwargs)
    fastapi_kwargs.setdefault("title", title)
    return FastAPI(**fastapi_kwargs)


class Stage:
    """OOP helper that mounts llming-stage onto an existing app.

    ``Stage(app)`` keeps the host app plainly FastAPI/Starlette-owned while
    ensuring the internal ``/_stage`` routes exist once. Development reload is
    enabled by default.
    """

    def __init__(
        self,
        app: Any | None = None,
        *,
        title: str = "llming",
        root: str | Path | None = None,
        asset_prefix: str = "/_stage",
        asset_fallbacks: list[str] | None = None,
        dev: bool = True,
        dev_reload: bool | None = None,
        lib_version: str | None = None,
        **fastapi_kwargs: Any,
    ) -> None:
        # Late import keeps ``llming_stage.__init__`` free of circular refs.
        from . import LIB_VERSION

        if app is None:
            app = _create_fastapi_app(title=title, kwargs=fastapi_kwargs)
        elif fastapi_kwargs:
            names = ", ".join(sorted(fastapi_kwargs))
            raise TypeError(f"FastAPI keyword arguments require Stage() without app: {names}")
        self.app = app
        self.title = title
        if root is None:
            caller = inspect.stack()[1].filename
            root_path = Path(caller).resolve().parent
        else:
            root_path = Path(root).resolve()
        self.root = root_path.parent if root_path.is_file() else root_path
        self.asset_prefix = asset_prefix.rstrip("/")
        self.asset_fallbacks = list(asset_fallbacks or [])
        self.dev = dev if dev_reload is None else dev_reload

        if lib_version is not None and not _LIB_VERSION_RE.fullmatch(lib_version):
            raise ValueError(
                "lib_version must be calendar format 'YYYY-MM' or 'YYYY-MM-NN', "
                f"got {lib_version!r}"
            )
        self.lib_version = lib_version
        # Pre-resolved: empty when no rewrite needed (app pinned the current
        # bundle, or didn't pin at all). Non-empty triggers /v<seg>/ URLs.
        self._lib_version_segment = (
            "" if (lib_version is None or lib_version == LIB_VERSION) else lib_version
        )
        # The bundle the page actually loads — stamped into the HTML for
        # debug / self-reporting via window.__stageLibVersion.
        self._effective_lib_version = (
            self._lib_version_segment or LIB_VERSION
        )

        self._views: list[_View] = []
        self._shell_routes_mounted = False

        self._ensure_assets()
        if self.dev:
            self._ensure_dev_reload()
        if is_debug_enabled():
            # mount_debug is idempotent per app+asset_prefix.
            mount_debug(self.app, asset_prefix=self.asset_prefix)
        state = getattr(self.app, "state", None)
        if state is not None:
            setattr(state, "llming_stage_instance", self)

    def add_view(
        self,
        route: str,
        source: str | Path,
        *,
        name: str | None = None,
    ) -> "Stage":
        """Register one view and make it available to the SPA router.

        The source filename is explicit by design: decorators and active
        registration should stay visually distinct.
        """

        self._register_view(route, source, name=name)
        return self

    def mount_bundles(
        self,
        directory: str | Path = "data",
        *,
        prefix: str = "/bundles",
    ) -> "Stage":
        """Serve a data-bundle directory with ETag-revalidated routes.

        ``directory`` is resolved relative to the Stage root (like view
        sources), so a sample only needs ``stage.mount_bundles("data")``.
        Files are served by :func:`llming_stage.mount_bundles` — whole
        ``.zip`` / ``.json`` / ``.bin`` blobs the client downloads once,
        caches by content hash, and reads locally for offline use.
        """
        resolved = self._resolve_source(directory)
        route = _normalize_route(prefix)
        mount_bundles(self.app, resolved, prefix=route)
        return self

    def serve_bundle(
        self,
        name: str,
        source: str | Path,
        *,
        prefix: str = "/bundles",
    ) -> "Stage":
        """Zip *source* on demand and serve it at ``{prefix}/{name}.zip``.

        The directory is re-zipped automatically whenever its contents
        change (mtime/size signature) — no build step, no watcher. The
        client downloads ``{name}.zip`` once, caches it by content hash, and
        unzips it in the browser. ``source`` is resolved relative to the
        Stage root, so a sample only needs
        ``stage.serve_bundle("media", "assets")``.
        """
        resolved = self._resolve_source(source)
        url = f"{prefix.rstrip('/')}/{name}.zip"
        mount_bundle_builder(self.app, resolved, url=url)
        return self

    def view(
        self,
        route: str,
        *,
        name: str | None = None,
    ) -> Callable[[Callable[[], Response]], Callable[[], Response]]:
        """Decorator for registering a generated view.

        The decorated function must return a response object. Use
        ``VueResponse`` for generated Vue views or ``HTMLResponse`` for
        static generated HTML. Returning ``None`` is invalid because a view
        route must produce page content.
        """

        def decorator(func: Callable[[], Response]) -> Callable[[], Response]:
            self._register_view(route, func, name=name)
            return func

        return decorator

    def _register_view(
        self,
        route: str,
        source: str | Path | Callable[[], Any],
        *,
        name: str | None = None,
    ) -> None:
        route = _normalize_route(route)
        if callable(source):
            resolved_source = source
            fallback = Path(getattr(source, "__name__", "view"))
        else:
            resolved_source = self._resolve_source(source)
            fallback = resolved_source
        view_name = name or _name_for_route(route, fallback)
        module_url = f"{self.asset_prefix}/app/{view_name}.js"
        debug_source = _debug_source_for_view(resolved_source, view_name)
        debug_module_url = (
            f"{self.asset_prefix}/app/{view_name}.debug.js"
            if debug_source is not None
            else None
        )
        view = _View(
            route=route,
            name=view_name,
            source=resolved_source,
            module_url=module_url,
            debug_source=debug_source,
            debug_module_url=debug_module_url,
        )
        self._views = [v for v in self._views if v.route != route and v.name != view_name]
        self._views.append(view)
        self._insert_before_shell(Route(module_url, self._make_view_handler(view)))
        if debug_source is not None and debug_module_url is not None:
            self._insert_before_shell(
                Route(debug_module_url, self._make_debug_view_handler(view))
            )
        self._ensure_shell()

    def discover(self, views_dir: str | Path = "views") -> "Stage":
        """Register all view files under ``views_dir`` by convention."""

        base = self._resolve_source(views_dir)
        if not base.is_dir():
            raise FileNotFoundError(f"view directory not found: {base}")
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix.lower() in _VIEW_EXTENSIONS:
                self.add_view(_route_for_discovered_view(base, path), path)
        return self

    def session(
        self,
        *,
        app_name: str = "stage",
        session_cls: Any | None = None,
        registry: Any | None = None,
        app_context: Any | None = None,
        controller_cls: Any | None = None,
        command_prefix: str | None = "/cmd",
    ) -> StageSession:
        """Mount a default llming-com session endpoint.

        This is intentionally FastAPI-native: the host app remains the app,
        while Stage adds the conventional ``/api/session`` and ``/ws/{id}``
        routes needed by ``this.$stage.connect()``.
        """
        from llming_com import (
            BaseController,
            BaseLlmingApp,
            BaseSessionEntry,
            BaseSessionRegistry,
        )

        session_type = session_cls or BaseSessionEntry
        session_registry = registry or BaseSessionRegistry.get()
        llming_app = app_context or BaseLlmingApp(session_registry)
        auth = _make_auth_manager(app_name)
        stage_session = StageSession(
            self,
            app_name=app_name,
            session_cls=session_type,
            registry=session_registry,
            app_context=llming_app,
            auth=auth,
            controller_cls=controller_cls or BaseController,
            command_prefix=command_prefix,
        )
        state = getattr(self.app, "state", None)
        if state is not None:
            setattr(state, "llming_stage_registry", session_registry)
            setattr(state, "llming_stage_app", llming_app)
            setattr(state, "llming_stage_auth", auth)
            setattr(state, "llming_stage_session", stage_session)
        return stage_session

    def build(
        self,
        out_dir: str | Path,
        *,
        asset_prefix: str | None = None,
        asset_fallbacks: list[str] | None = None,
        inline: bool = False,
        inline_max_bytes: int | None = None,
    ) -> Path:
        """Build a static publish directory for apps without Python backends.

        Refuses when the Stage is pinned to a bundle different from the
        installed ``LIB_VERSION``: the build can only snapshot the bytes
        the installed package actually owns. To archive an older bundle
        on a shared host, install that older llming-stage version into a
        venv and run ``llming-stage export-assets --out <dir>``.

        Layout knobs (default reproduces the historical ``/_stage`` output):

        * ``asset_prefix`` — where the shell looks for its bundle, *relative
          to each emitted ``index.html``*. A **relative** value (``"_stage"``,
          ``"."``) makes the artifact relocatable: it is depth-adjusted per
          route so a page at ``/reports/`` still finds the bundle, and
          loader.js self-locates lazy assets from its own URL. An
          **absolute** value (``"/_stage"``) stays origin-rooted as before.
        * ``asset_fallbacks`` — extra bases tried when a *lazy* asset 404s
          from the primary, so one artifact works far (shared host) or near
          (bundled).
        * ``inline`` — emit a single self-contained ``index.html`` with every
          JS/CSS library folded in (critical libs as ``<script>`` / ``<style>``,
          lazy libs + view modules as ``data-stage-lib`` blocks resolved to
          blob URLs at load time). ``inline_max_bytes`` caps which lazy files
          are folded in; larger ones are skipped and noted in an HTML comment.
        """

        if self._lib_version_segment:
            raise RuntimeError(
                f"Stage.build() cannot snapshot a pinned older bundle "
                f"(lib_version={self.lib_version!r}); only the installed "
                f"bundle can be built. Install that version separately and "
                f"use `llming-stage export-assets` to archive it."
            )
        out = Path(out_dir).resolve()
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)

        eff_prefix = self.asset_prefix if asset_prefix is None else asset_prefix
        eff_fallbacks = (
            self.asset_fallbacks if asset_fallbacks is None else list(asset_fallbacks)
        )
        asset_dir = _build_asset_dir_name(eff_prefix)
        asset_root = out / asset_dir if asset_dir else out
        self._build_stage_assets(asset_root)

        if inline:
            # Single-file delivery: base is irrelevant because inlined
            # payloads resolve with zero network, so render with a neutral
            # '.' prefix, fold everything in, then drop the now-unused tree.
            html = self._render_shell(
                dev_reload=False, asset_prefix=".", asset_fallbacks=[], current_route="/"
            )
            html = _inline_assets(html, asset_root, max_bytes=inline_max_bytes)
            (out / "index.html").write_text(html, encoding="utf-8")
            shutil.rmtree(asset_root, ignore_errors=True)
            return out

        routes = {v.route for v in self._views} or {"/"}
        for route in routes:
            target = out / "index.html" if route == "/" else out / route.lstrip("/") / "index.html"
            depth = 0 if route == "/" else len([s for s in route.strip("/").split("/") if s])
            html_doc = self._render_shell(
                dev_reload=False,
                asset_prefix=_depth_adjust_prefix(eff_prefix, depth),
                asset_fallbacks=[_depth_adjust_prefix(p, depth) for p in eff_fallbacks],
                current_route=route,
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(html_doc, encoding="utf-8")
        static_dir = self.root / "static"
        if static_dir.is_dir():
            shutil.copytree(static_dir, out / "static", dirs_exist_ok=True)
        return out

    def run(
        self,
        *,
        host: str = "127.0.0.1",
        port: int | None = None,
        reload: bool | None = None,
        app_import: str = "main:app",
    ) -> None:
        """Run the app with uvicorn using the same defaults samples show.

        This is intentionally a thin local-development convenience, not a
        separate server abstraction. For production, custom workers, TLS,
        logging, or process management, call uvicorn or another ASGI server
        directly.
        """

        import uvicorn

        selected_port = port or int(os.environ.get("PORT", "8765"))
        selected_reload = (
            os.environ.get("STAGE_RELOAD", "1") != "0" if reload is None else reload
        )
        if selected_reload:
            uvicorn.run(
                app_import,
                host=host,
                port=selected_port,
                reload=True,
                reload_dirs=[str(self.root)],
                app_dir=str(self.root),
            )
        else:
            uvicorn.run(self.app, host=host, port=selected_port)

    def _ensure_assets(self) -> None:
        if self._lib_version_segment:
            # A pinned older bundle must be served by an archived shared
            # asset tree. Mounting the currently-installed bytes under an
            # old /v<LIB_VERSION>/ path would silently defeat the pin.
            return
        state = getattr(self.app, "state", None)
        flag = f"llming_stage_assets_mounted_{self.asset_prefix}"
        if state is not None and getattr(state, flag, False):
            return
        mount_assets(self.app, asset_prefix=self.asset_prefix)
        if state is not None:
            setattr(state, flag, True)

    def _ensure_dev_reload(self) -> None:
        state = getattr(self.app, "state", None)
        # Dev-reload always mounts at the unversioned prefix — it's a local
        # maintenance feature, not an asset. Flag intentionally NOT keyed by
        # lib_version so a second versioned Stage on the same app won't try
        # to re-mount it.
        flag = f"llming_stage_dev_mounted_{self.asset_prefix}"
        if state is not None and getattr(state, flag, False):
            return
        mount_dev_reload(
            self.app,
            config=DevReloadConfig(
                url_prefix=f"{self.asset_prefix}/dev",
                watch_paths=[self.root],
                homepage_path="/",
            ),
        )
        if state is not None:
            setattr(state, flag, True)

    def _ensure_shell(self) -> None:
        if self._shell_routes_mounted:
            return

        async def shell_handler(request: Request) -> Response:
            return HTMLResponse(self._render_shell(dev_reload=self.dev))

        self.app.router.routes.append(Route("/", shell_handler))
        self.app.router.routes.append(Route("/{path:path}", shell_handler))
        self._shell_routes_mounted = True

    def _render_shell(
        self,
        *,
        dev_reload: bool,
        asset_prefix: str | None = None,
        asset_fallbacks: list[str] | None = None,
        current_route: str = "",
    ) -> str:
        return render_shell(
            ShellConfig(
                title=self.title,
                asset_prefix=self.asset_prefix if asset_prefix is None else asset_prefix,
                asset_fallbacks=(
                    self.asset_fallbacks if asset_fallbacks is None else asset_fallbacks
                ),
                current_route=current_route,
                routes=[(v.route, v.name) for v in self._views],
                # Register view modules as paths RELATIVE to the asset base
                # (strip the canonical prefix the route was built with), so the
                # shell resolves them via self-location / fallback like every
                # other lazy asset — independent of the render-time prefix.
                view_modules={
                    v.name: (
                        {
                            "js": self._rebase_module_url(v.module_url),
                            "debug": self._rebase_module_url(v.debug_module_url),
                        }
                        if v.debug_module_url
                        else self._rebase_module_url(v.module_url)
                    )
                    for v in self._views
                },
                preload_views=[self._views[0].name] if self._views else [],
                dev_reload=dev_reload,
                dev_reload_prefix=f"{self.asset_prefix}/dev",
                lib_version_segment=self._lib_version_segment,
                lib_version=self._effective_lib_version,
                debug_bridge=is_debug_enabled(),
                debug_enabled=is_debug_enabled(),
                debug_parent_origin=os.environ.get(
                    "LLMING_STAGE_DEBUG_PARENT_ORIGIN", ""
                ).strip(),
            )
        )

    def _rebase_module_url(self, url: str | None) -> str:
        """Strip the canonical asset prefix so a view module registers as a
        base-relative path (``app/home.js``), letting loader.js re-anchor it."""
        if not url:
            return url or ""
        head = self.asset_prefix.rstrip("/") + "/"
        return url[len(head):] if url.startswith(head) else url

    def _insert_before_shell(self, route: Route) -> None:
        routes = self.app.router.routes
        for index, existing in enumerate(routes):
            if getattr(existing, "path", None) == "/{path:path}":
                routes.insert(index, route)
                return
        routes.append(route)

    def _make_view_handler(self, view: _View):
        async def handler(request: Request) -> Response:
            js = _render_view_module(view.name, view.source)
            return Response(
                js,
                media_type="application/javascript; charset=utf-8",
                headers={"Cache-Control": "no-store" if self.dev else "public, max-age=31536000"},
            )

        return handler

    def _make_debug_view_handler(self, view: _View):
        async def handler(request: Request) -> Response:
            if not is_debug_enabled() or view.debug_source is None:
                raise HTTPException(status_code=404, detail="debug actions not enabled")
            return Response(
                view.debug_source.read_text(encoding="utf-8"),
                media_type="application/javascript; charset=utf-8",
                headers={"Cache-Control": "no-store"},
            )

        return handler

    def _resolve_source(self, source: str | Path) -> Path:
        path = Path(source)
        if not path.is_absolute():
            path = self.root / path
        return path.resolve()

    def _build_stage_assets(self, target: Path) -> None:
        export_package_assets(target, write_manifest=False)
        app_dir = target / "app"
        app_dir.mkdir(exist_ok=True)
        for view in self._views:
            (app_dir / f"{view.name}.js").write_text(
                _render_view_module(view.name, view.source),
                encoding="utf-8",
            )


def _is_absolute_prefix(prefix: str) -> bool:
    """True for origin-rooted ('/...') or full-URL ('https://...') prefixes."""
    return prefix.startswith("/") or "://" in prefix


def _build_asset_dir_name(prefix: str) -> str:
    """Directory under the build root that physically holds the bundle.

    Relative ``../`` segments (a serve-time / shared-host concept) collapse —
    a static build always writes the bundle inside the output tree. ``"."``
    means "next to the shell" (returns "").
    """
    p = prefix.strip()
    if _is_absolute_prefix(p):
        return p.lstrip("/").rstrip("/")
    parts = [seg for seg in p.split("/") if seg not in ("", ".", "..")]
    return "/".join(parts)


def _depth_adjust_prefix(prefix: str, depth: int) -> str:
    """Rewrite a RELATIVE prefix so it still resolves from a route ``depth``
    levels below the build root. Absolute prefixes are origin-rooted and
    returned unchanged.
    """
    if _is_absolute_prefix(prefix):
        return prefix
    p = prefix.strip()
    p = p[2:] if p.startswith("./") else ("" if p == "." else p)
    combined = ("../" * depth) + p
    return combined.rstrip("/") or "."


def _inline_assets(html: str, asset_root: Path, *, max_bytes: int | None = None) -> str:
    """Fold a rendered shell into a single self-contained document.

    Critical ``<script src="./…">`` / ``<link href="./….css">`` become inline
    ``<script>`` / ``<style>``; every lazy vendor lib and view module becomes a
    ``<script type="text/plain" data-stage-lib="…">`` block that loader.js
    resolves to a blob URL on demand. Files over ``max_bytes`` are skipped and
    recorded in an HTML comment (no silent truncation).
    """

    def _read(rel: str) -> str | None:
        f = asset_root / rel
        return f.read_text(encoding="utf-8") if f.is_file() else None

    def _script_sub(m: "re.Match[str]") -> str:
        rel = m.group(1)
        content = _read(rel)
        if content is None:
            return m.group(0)
        # Escape any literal '</script>' (only ever inside string literals in
        # minified bundles) so it can't terminate the inline script early.
        return f"<script>\n{content.replace('</script>', '<\\/script>')}\n</script>"

    def _link_sub(m: "re.Match[str]") -> str:
        rel = m.group(1)
        content = _read(rel)
        if content is None:
            return m.group(0)
        return f"<style>\n{content.replace('</style>', '<\\/style>')}\n</style>"

    html = re.sub(
        r'<script src="\./([^"?]+\.js)(?:\?[^"]*)?"></script>', _script_sub, html
    )
    html = re.sub(
        r'<link rel="stylesheet" href="\./([^"?]+\.css)(?:\?[^"]*)?">', _link_sub, html
    )

    blocks: list[str] = []
    skipped: list[tuple[str, int]] = []
    for sub in ("vendor", "app"):
        directory = asset_root / sub
        if not directory.is_dir():
            continue
        for f in sorted(directory.rglob("*")):
            if not f.is_file() or f.suffix not in (".js", ".css", ".mjs"):
                continue
            rel = f"{sub}/{f.relative_to(directory).as_posix()}"
            size = f.stat().st_size
            if max_bytes is not None and size > max_bytes:
                skipped.append((rel, size))
                continue
            # base64 so the payload can never contain '</script>' and embeds
            # safely; loader.js decodes it to a Blob URL on demand.
            payload = base64.b64encode(f.read_bytes()).decode("ascii")
            blocks.append(
                f'<script type="text/plain" data-stage-lib="{rel}">{payload}</script>'
            )
    tail = "\n".join(blocks)
    if skipped:
        tail += "".join(
            f"\n<!-- inline-skipped {rel} ({size} bytes) -->" for rel, size in skipped
        )
    return html.replace("</body>", f"{tail}\n</body>", 1)


def _render_view_module(name: str, source: Path | Callable[[], Any]) -> str:
    if callable(source):
        return _render_generated_view(name, source)
    if not source.is_file():
        raise FileNotFoundError(f"view source not found: {source}")
    suffix = source.suffix.lower()
    text = source.read_text(encoding="utf-8")
    if suffix == ".vue":
        return _render_vue(name, source, text)
    if suffix in {".html", ".htm"}:
        return _render_html(name, text)
    if suffix == ".js":
        return text
    raise ValueError(f"unsupported view extension: {source.suffix}")


def _debug_source_for_view(source: Path | Callable[[], Any], view_name: str) -> Path | None:
    if not is_debug_enabled():
        return None
    if isinstance(source, Path):
        return _debug_source_for(source)
    func_file = inspect.getsourcefile(source)
    if not func_file:
        return None
    candidate = Path(func_file).resolve().parent / f"{view_name}.debug.js"
    return candidate if candidate.is_file() else None


def _debug_source_for(source: Path) -> Path | None:
    if not source.is_file():
        return None
    candidate = source.with_name(f"{source.stem}.debug.js")
    return candidate if candidate.is_file() else None


def _render_generated_view(name: str, func: Callable[[], Any]) -> str:
    result = func()
    if result is None:
        raise ValueError(
            f"stage view function {func.__name__!r} returned None; "
            "return a VueResponse or HTMLResponse"
        )
    if not isinstance(result, Response):
        raise TypeError(
            f"stage view function {func.__name__!r} returned "
            f"{type(result).__name__}; expected a Starlette Response"
        )
    body = getattr(result, "body", b"")
    if not isinstance(body, bytes):
        raise TypeError(
            f"stage view function {func.__name__!r} returned "
            f"{type(result).__name__} without a concrete response body"
        )
    charset = getattr(result, "charset", "utf-8") or "utf-8"
    text = body.decode(charset).strip()
    media_type = (getattr(result, "media_type", None) or "").split(";", 1)[0]
    if media_type in {"text/x-vue", "application/vnd.llming-stage.vue"}:
        if isinstance(result, VueResponse):
            func_file = inspect.getsourcefile(func)
            base = Path(func_file).resolve().parent if func_file else Path.cwd()
            text = result.resolve_source(base)
        return _render_vue(name, Path(f"{name}.vue"), _normalize_vue_response(text))
    if media_type and media_type != "text/html":
        raise TypeError(
            f"stage view function {func.__name__!r} returned media type "
            f"{media_type!r}; expected text/html"
        )
    return _render_html(name, text)


def _compose_vue_source(
    template: str | None,
    script: str | None,
    style: str | None,
) -> str:
    blocks = [f"<template>\n{(template or '').strip()}\n</template>"]
    if script is not None:
        blocks.append(f"<script>\n{script.strip()}\n</script>")
    if style is not None:
        blocks.append(f"<style>\n{style.strip()}\n</style>")
    return "\n".join(blocks)


def _read_response_part(path: Path, base: Path, label: str) -> str:
    resolved = path if path.is_absolute() else base / path
    if not resolved.is_file():
        raise FileNotFoundError(f"VueResponse {label} file not found: {resolved}")
    return resolved.read_text(encoding="utf-8")


def _normalize_vue_response(source: str) -> str:
    if re.search(r"</?(template|script|style)(\s|>)", source, flags=re.IGNORECASE):
        return source
    return f"<template>\n{source}\n</template>"


def _render_vue(name: str, source_path: Path, source: str) -> str:
    template = _extract_block(source, "template") or "<div></div>"
    style = _extract_block(source, "style") or ""
    script = _extract_block(source, "script") or "export default {}"
    script_expr = _script_to_object_expr(script, source_path.parent, {source_path.resolve()})
    style_id = f"stage-view-style-{_slug(name)}"
    return f"""(() => {{
  const component = Object.assign({script_expr}, {{ template: {json.dumps(template)} }});
  if (!component.stageId) component.stageId = {json.dumps(name)};
  const styleText = {json.dumps(style)};
  function ensureStyle() {{
    if (!styleText || document.getElementById({json.dumps(style_id)})) return;
    const style = document.createElement('style');
    style.id = {json.dumps(style_id)};
    style.textContent = styleText;
    document.head.appendChild(style);
  }}
  window.__stageViews = window.__stageViews || {{}};
  window.__stageViews[{json.dumps(name)}] = {{
    mount(target, params) {{
      ensureStyle();
      const host = document.createElement('div');
      target.appendChild(host);
      const app = Vue.createApp(component, {{ params }});
      const stageDark = document.body.classList.contains('body--dark');
      if (window.Quasar) {{
        app.use(Quasar);
        if (Quasar.Dark) Quasar.Dark.set(stageDark);
      }}
      app.config.globalProperties.$stage = window.__stage;
      app.mixin({{
        mounted() {{
          const target =
            this.$options.stageId ||
            this.$attrs.stageId ||
            this.$attrs['stage-id'] ||
            this.$options.name;
          if (!target) return;
          this.__stageUnregister = window.__stage.registerComponent(target, this);
        }},
        unmounted() {{
          if (this.__stageUnregister) this.__stageUnregister();
        }}
      }});
      app.mount(host);
      return {{ unmount() {{ app.unmount(); target.innerHTML = ''; }} }};
    }}
  }};
}})();
"""


def _vue_component_expr(source_path: Path, seen: set[Path]) -> str:
    resolved = source_path.resolve()
    if resolved in seen:
        raise ValueError(f"circular Vue import: {source_path}")
    source = resolved.read_text(encoding="utf-8")
    template = _extract_block(source, "template") or "<div></div>"
    script = _extract_block(source, "script") or "export default {}"
    script_expr = _script_to_object_expr(script, resolved.parent, seen | {resolved})
    return f"Object.assign({script_expr}, {{ template: {json.dumps(template)} }})"


def _render_html(name: str, source: str) -> str:
    return f"""(() => {{
  window.__stageViews = window.__stageViews || {{}};
  window.__stageViews[{json.dumps(name)}] = {{
    mount(target) {{
      target.innerHTML = {json.dumps(source)};
      return {{ unmount() {{ target.innerHTML = ''; }} }};
    }}
  }};
}})();
"""


def _extract_block(source: str, tag: str) -> str:
    match = re.search(
        rf"<{tag}(?:\s[^>]*)?>(.*?)</{tag}>",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def _script_to_object_expr(script: str, base_dir: Path, seen: set[Path]) -> str:
    text = script.strip()
    imports: list[str] = []

    def replace_import(match: re.Match[str]) -> str:
        local_name = match.group(1)
        rel_path = match.group(2)
        child = (base_dir / rel_path).resolve()
        if child.suffix.lower() != ".vue":
            raise ValueError(f"only relative .vue imports are supported: {rel_path}")
        imports.append(f"const {local_name} = {_vue_component_expr(child, seen)};")
        return ""

    text = re.sub(
        r'^\s*import\s+([A-Za-z_$][\w$]*)\s+from\s+[\'"](\.[^\'"]+\.vue)[\'"]\s*;?\s*$',
        replace_import,
        text,
        flags=re.MULTILINE,
    ).strip()
    export_match = re.search(r"\bexport\s+default\s+", text)
    if export_match and export_match.start() > 0:
        prefix = text[: export_match.start()].rstrip()
        expr = text[export_match.end() :].strip().rstrip(";")
        import_text = "\n".join(imports)
        return f"(() => {{\n{import_text}\n{prefix}\nreturn {expr};\n}})()"
    text = re.sub(r"^export\s+default\s+", "", text)
    text = text.rstrip()
    if text.endswith(";"):
        text = text[:-1]
    if not text:
        return "{}"
    if imports:
        return f"(() => {{\n{chr(10).join(imports)}\nreturn {text};\n}})()"
    return text


def _route_for_discovered_view(base: Path, path: Path) -> str:
    rel = path.relative_to(base).with_suffix("")
    parts = list(rel.parts)
    if parts in (["home"], ["index"]):
        return "/"
    if parts and parts[-1] == "index":
        parts = parts[:-1]
    if parts and parts[-1] == "home":
        parts = parts[:-1] or ["home"]
    route_parts = [_route_segment(part) for part in parts]
    return "/" + "/".join(route_parts)


def _route_segment(part: str) -> str:
    if part.startswith("[") and part.endswith("]") and len(part) > 2:
        return ":" + part[1:-1]
    return part


def _normalize_route(route: str) -> str:
    if not route.startswith("/"):
        route = "/" + route
    return route.rstrip("/") or "/"


def _name_for_route(route: str, source: Path) -> str:
    if route == "/":
        return "home"
    return _slug(route.strip("/")) or _slug(source.stem)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "-", value).strip("-")
    return slug or "view"
