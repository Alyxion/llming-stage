"""FastAPI/Starlette-native stage application helper."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
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
    render_shell,
)

_LIB_VERSION_RE = re.compile(r"\d{4}-\d{2}(-\d+)?")

_VIEW_EXTENSIONS = {".vue", ".js", ".html", ".htm"}


@dataclass
class _View:
    route: str
    name: str
    source: Path | Callable[[], Any]
    module_url: str


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

    def _cancel_removal(self, session_id: str) -> None:
        task = self._removal_tasks.pop(session_id, None)
        if task is not None and not task.done():
            task.cancel()

    def _schedule_removal(self, session_id: str) -> None:
        """Drop *session_id* from the registry after the grace period.

        Cancels any in-flight removal first — repeated disconnects on the
        same session reset the timer rather than stacking.
        """
        self._cancel_removal(session_id)

        async def _drop() -> None:
            try:
                await asyncio.sleep(self.disconnect_grace_seconds)
            except asyncio.CancelledError:
                return
            self.registry.remove(session_id)
            self._removal_tasks.pop(session_id, None)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No loop — synchronous test path. Remove eagerly.
            self.registry.remove(session_id)
            return
        self._removal_tasks[session_id] = loop.create_task(_drop())

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
            # distinct sessions. When the hint is registered we reuse
            # it (tab reload); otherwise we mint a fresh session under
            # that id. The cookie fallback below kicks in only for
            # clients that omit the query string.
            requested = request.query_params.get("session")
            if requested:
                if self.registry.get_session(requested):
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
            )
            return resp

        async def ws_endpoint(websocket: Any) -> None:
            session_id = websocket.path_params["session_id"]

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

            await run_websocket_session(
                websocket,
                session_id,
                self.registry,
                on_connect=on_connect,
                on_message=on_message,
                on_disconnect=on_disconnect,
                # Don't kick the previous WS off when a new one comes in
                # for the same session id (e.g. two tabs that ended up
                # with cloned sessionStorage). llming-com's default
                # supersede behavior + LlmingWebSocket's auto-reconnect
                # creates a churn loop that drops everything. We rely on
                # our own 10s disconnect grace for cleanup instead.
                supersede_existing=False,
            )

        self.stage._insert_before_shell(Route("/api/session", create_session))
        self.stage._insert_before_shell(WebSocketRoute("/ws/{session_id}", ws_endpoint))

    def _mount_command_router(self) -> None:
        if self.command_prefix is None or not hasattr(self.stage.app, "include_router"):
            return
        from llming_com import build_command_router

        self.stage.app.include_router(
            build_command_router(self.registry, prefix=self.command_prefix)
        )
        prefix = self.command_prefix.rstrip("/")

        async def debug_state(request: Request) -> JSONResponse:
            session_id = request.path_params["session_id"]
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
        view = _View(
            route=route,
            name=view_name,
            source=resolved_source,
            module_url=module_url,
        )
        self._views = [v for v in self._views if v.route != route and v.name != view_name]
        self._views.append(view)
        self._insert_before_shell(Route(module_url, self._make_view_handler(view)))
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
            AuthManager,
            BaseController,
            BaseLlmingApp,
            BaseSessionEntry,
            BaseSessionRegistry,
        )

        os.environ.setdefault("LLMING_AUTH_SECRET", "dev-secret-please-change")

        session_type = session_cls or BaseSessionEntry
        session_registry = registry or BaseSessionRegistry.get()
        llming_app = app_context or BaseLlmingApp(session_registry)
        auth = AuthManager(app_name=app_name)
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

    def build(self, out_dir: str | Path) -> Path:
        """Build a static publish directory for apps without Python backends.

        Refuses when the Stage is pinned to a bundle different from the
        installed ``LIB_VERSION``: the build can only snapshot the bytes
        the installed package actually owns. To archive an older bundle
        on a shared host, install that older llming-stage version into a
        venv and run ``llming-stage export-assets --out <dir>``.
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
        self._build_stage_assets(out / self.asset_prefix.lstrip("/"))
        html_doc = self._render_shell(dev_reload=False)
        routes = {v.route for v in self._views} or {"/"}
        for route in routes:
            target = out / "index.html" if route == "/" else out / route.lstrip("/") / "index.html"
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
        state = getattr(self.app, "state", None)
        # Key includes the version segment so two Stage instances with
        # different lib_version pins can coexist on the same app, each
        # mounting its own asset tree.
        flag = (
            f"llming_stage_assets_mounted_{self.asset_prefix}"
            f"_v{self._lib_version_segment}"
        )
        if state is not None and getattr(state, flag, False):
            return
        mount_assets(
            self.app,
            asset_prefix=self.asset_prefix,
            lib_version_segment=self._lib_version_segment,
        )
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

    def _render_shell(self, *, dev_reload: bool) -> str:
        return render_shell(
            ShellConfig(
                title=self.title,
                asset_prefix=self.asset_prefix,
                routes=[(v.route, v.name) for v in self._views],
                view_modules={v.name: v.module_url for v in self._views},
                preload_views=[self._views[0].name] if self._views else [],
                dev_reload=dev_reload,
                dev_reload_prefix=f"{self.asset_prefix}/dev",
                lib_version_segment=self._lib_version_segment,
                lib_version=self._effective_lib_version,
                debug_bridge=is_debug_enabled(),
            )
        )

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
