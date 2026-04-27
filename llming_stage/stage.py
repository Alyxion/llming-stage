"""FastAPI/Starlette-native stage application helper."""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route, WebSocketRoute

from .dev_reload import DevReloadConfig, mount_dev_reload
from .shell import (
    _ASSETS_ROOT,
    _FONTS_ROOT,
    _LANG_ROOT,
    _STATIC_ROOT,
    _VENDOR_ROOT,
    _llming_com_static_dir,
    mount_assets,
    render_shell,
    ShellConfig,
)

_VIEW_EXTENSIONS = {".vue", ".js", ".html", ".htm"}


@dataclass
class _View:
    route: str
    name: str
    source: Path
    module_url: str


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

        self._mount_routes()
        self._mount_command_router()

    def router(self, prefix: str) -> Any:
        """Create and mount a session-scoped router namespace."""
        from llming_com import SessionRouter

        child = SessionRouter(prefix=prefix)
        self.session_router.include(child)
        return child

    def app_router(self, prefix: str) -> Any:
        """Create and mount an application-scoped router namespace."""
        from llming_com import AppRouter

        child = AppRouter(prefix=prefix)
        self.application_router.include(child)
        return child

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
            existing = self.auth.get_auth_session_id(request)
            if existing and self.registry.get_session(existing):
                session_id = existing
                token = self.auth.sign_auth_token(session_id)
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

            await run_websocket_session(
                websocket,
                session_id,
                self.registry,
                on_connect=on_connect,
                on_message=on_message,
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


class Stage:
    """OOP helper that mounts llming-stage onto an existing app.

    ``Stage(app)`` keeps the host app plainly FastAPI/Starlette-owned while
    ensuring the internal ``/_stage`` routes exist once. Development reload is
    enabled by default.
    """

    def __init__(
        self,
        app: Any,
        *,
        title: str = "llming",
        root: str | Path | None = None,
        asset_prefix: str = "/_stage",
        dev: bool = True,
        dev_reload: bool | None = None,
    ) -> None:
        self.app = app
        self.title = title
        root_path = Path(root).resolve() if root is not None else Path.cwd().resolve()
        self.root = root_path.parent if root_path.is_file() else root_path
        self.asset_prefix = asset_prefix.rstrip("/")
        self.dev = dev if dev_reload is None else dev_reload
        self._views: list[_View] = []
        self._shell_routes_mounted = False

        self._ensure_assets()
        if self.dev:
            self._ensure_dev_reload()
        state = getattr(self.app, "state", None)
        if state is not None:
            setattr(state, "llming_stage_instance", self)

    def view(self, route: str, source: str | Path, *, name: str | None = None) -> "Stage":
        """Register one view and make it available to the SPA router."""

        route = _normalize_route(route)
        source_path = self._resolve_source(source)
        view_name = name or _name_for_route(route, source_path)
        module_url = f"{self.asset_prefix}/app/{view_name}.js"
        view = _View(route=route, name=view_name, source=source_path, module_url=module_url)
        self._views = [v for v in self._views if v.route != route and v.name != view_name]
        self._views.append(view)
        self._insert_before_shell(Route(module_url, self._make_view_handler(view)))
        self._ensure_shell()
        return self

    def discover(self, views_dir: str | Path = "views") -> "Stage":
        """Register all view files under ``views_dir`` by convention."""

        base = self._resolve_source(views_dir)
        if not base.is_dir():
            raise FileNotFoundError(f"view directory not found: {base}")
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix.lower() in _VIEW_EXTENSIONS:
                self.view(_route_for_discovered_view(base, path), path)
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
        """Build a static publish directory for apps without Python backends."""

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
        """Run the app with uvicorn for local development."""

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
        flag = f"llming_stage_assets_mounted_{self.asset_prefix}"
        if state is not None and getattr(state, flag, False):
            return
        mount_assets(self.app, asset_prefix=self.asset_prefix)
        if state is not None:
            setattr(state, flag, True)

    def _ensure_dev_reload(self) -> None:
        state = getattr(self.app, "state", None)
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
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(_STATIC_ROOT, target, dirs_exist_ok=True)
        shutil.copytree(_VENDOR_ROOT, target / "vendor", dirs_exist_ok=True)
        shutil.copytree(_FONTS_ROOT, target / "fonts", dirs_exist_ok=True)
        shutil.copytree(_LANG_ROOT, target / "lang", dirs_exist_ok=True)
        shutil.copytree(_llming_com_static_dir(), target / "llming-com", dirs_exist_ok=True)
        archives = {
            "icons": _ASSETS_ROOT / "phosphor-icons.zip",
            "emoji": _ASSETS_ROOT / "noto-emoji.zip",
            "tabler": _ASSETS_ROOT / "tabler-icons.zip",
        }
        for dirname, archive in archives.items():
            if archive.exists():
                with zipfile.ZipFile(archive) as zf:
                    zf.extractall(target / dirname)
        app_dir = target / "app"
        app_dir.mkdir(exist_ok=True)
        for view in self._views:
            (app_dir / f"{view.name}.js").write_text(
                _render_view_module(view.name, view.source),
                encoding="utf-8",
            )


def _render_view_module(name: str, source: Path) -> str:
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
