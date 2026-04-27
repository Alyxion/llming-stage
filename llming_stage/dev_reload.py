"""Development-only content watcher and browser reload wiring."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from hashlib import blake2b
from pathlib import Path
from typing import Any, Literal

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

ServerReloadMode = Literal["notify", "exit"]
ChangeKind = Literal["created", "modified", "deleted"]
ServerReloadHook = Callable[[tuple["FileChange", ...]], None | Awaitable[None]]

DEFAULT_BROWSER_RELOAD_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".avif",
        ".bmp",
        ".css",
        ".gif",
        ".htm",
        ".html",
        ".ico",
        ".jpeg",
        ".jpg",
        ".js",
        ".json",
        ".md",
        ".mjs",
        ".png",
        ".svg",
        ".txt",
        ".vue",
        ".webp",
        ".woff2",
    }
)
DEFAULT_SERVER_RELOAD_EXTENSIONS: frozenset[str] = frozenset(
    {".ini", ".py", ".pyi", ".toml", ".yaml", ".yml"}
)
DEFAULT_IGNORE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
    }
)


@dataclass(frozen=True)
class FileChange:
    """A file that changed content since the previous watcher scan."""

    path: Path
    kind: ChangeKind


@dataclass
class DevReloadConfig:
    """Configuration for :func:`mount_dev_reload`.

    ``watch_paths`` defaults to the current working directory because a
    llming-stage app is usually mounted into a host FastAPI app. Pass a
    narrower list for larger repos.
    """

    url_prefix: str = "/_stage/dev"
    watch_paths: list[Path | str] = field(default_factory=lambda: [Path.cwd()])
    homepage_path: str = "/"
    poll_interval: float = 0.15
    browser_reload_extensions: frozenset[str] = DEFAULT_BROWSER_RELOAD_EXTENSIONS
    server_reload_extensions: frozenset[str] = DEFAULT_SERVER_RELOAD_EXTENSIONS
    ignore_dirs: frozenset[str] = DEFAULT_IGNORE_DIRS
    server_reload: ServerReloadMode = "notify"
    on_server_reload: ServerReloadHook | None = None


@dataclass(frozen=True)
class _FileState:
    mtime_ns: int
    size: int
    digest: str


class _ContentSnapshot:
    def __init__(self, config: DevReloadConfig) -> None:
        self.config = config
        self._files: dict[Path, _FileState] = {}
        self._primed = False

    def prime(self) -> None:
        self._files = self._scan()
        self._primed = True

    def changes(self) -> tuple[FileChange, ...]:
        if not self._primed:
            self.prime()
            return ()
        previous = self._files
        current = self._scan(previous)
        changes: list[FileChange] = []

        for path, state in current.items():
            old = previous.get(path)
            if old is None:
                changes.append(FileChange(path, "created"))
            elif old.digest != state.digest:
                changes.append(FileChange(path, "modified"))

        for path in previous:
            if path not in current:
                changes.append(FileChange(path, "deleted"))

        self._files = current
        return tuple(sorted(changes, key=lambda c: str(c.path)))

    def _scan(
        self, previous: dict[Path, _FileState] | None = None
    ) -> dict[Path, _FileState]:
        extensions = (
            self.config.browser_reload_extensions | self.config.server_reload_extensions
        )
        current: dict[Path, _FileState] = {}
        for path in _iter_watch_files(
            self.config.watch_paths,
            extensions=extensions,
            ignore_dirs=self.config.ignore_dirs,
        ):
            state = _state_for(path, previous.get(path) if previous else None)
            if state is not None:
                current[path] = state
        return current


class DevReloader:
    """Background watcher plus websocket broadcaster."""

    def __init__(self, config: DevReloadConfig | None = None) -> None:
        self.config = config or DevReloadConfig()
        self._snapshot = _ContentSnapshot(self.config)
        self._clients: set[WebSocket] = set()
        self._task: asyncio.Task[None] | None = None
        self._version = 0

    @property
    def version(self) -> int:
        return self._version

    def routes(self) -> list[Route | WebSocketRoute]:
        prefix = self.config.url_prefix.rstrip("/")
        return [
            Route(f"{prefix}/client.js", self._client_js),
            Route(f"{prefix}/state", self._state),
            WebSocketRoute(f"{prefix}/ws", self._ws),
        ]

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._snapshot.prime()
        self._task = asyncio.create_task(self._watch(), name="llming-stage-dev-reload")

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        for client in tuple(self._clients):
            await _close_client(client)
        self._clients.clear()

    async def scan_once(self) -> tuple[FileChange, ...]:
        """Scan immediately and dispatch reload actions for tests/tools."""

        changes = self._snapshot.changes()
        if changes:
            await self._dispatch(changes)
        return changes

    async def _watch(self) -> None:
        while True:
            await asyncio.sleep(self.config.poll_interval)
            await self.scan_once()

    async def _dispatch(self, changes: tuple[FileChange, ...]) -> None:
        server_changes = tuple(
            c
            for c in changes
            if c.path.suffix.lower() in self.config.server_reload_extensions
        )
        if server_changes:
            await self._handle_server_reload(server_changes)
            return

        self._version += 1
        await self._broadcast(
            {
                "type": "reload",
                "version": self._version,
                "path": self.config.homepage_path,
                "files": [_change_payload(c) for c in changes],
            }
        )

    async def _handle_server_reload(self, changes: tuple[FileChange, ...]) -> None:
        self._version += 1
        if self.config.on_server_reload is not None:
            result = self.config.on_server_reload(changes)
            if inspect.isawaitable(result):
                await result
            return

        await self._broadcast(
            {
                "type": "server-reload",
                "version": self._version,
                "files": [_change_payload(c) for c in changes],
            }
        )
        if self.config.server_reload == "exit":
            os._exit(3)

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        message = json.dumps(payload, separators=(",", ":"))
        for client in tuple(self._clients):
            try:
                await client.send_text(message)
            except Exception:
                stale.append(client)
        for client in stale:
            self._clients.discard(client)

    async def _client_js(self, request: Request) -> Response:
        body = _client_script(
            ws_path=f"{self.config.url_prefix.rstrip('/')}/ws",
            homepage_path=self.config.homepage_path,
        )
        return Response(
            body,
            media_type="application/javascript; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )

    async def _state(self, request: Request) -> Response:
        return JSONResponse(
            {"ok": True, "version": self._version},
            headers={"Cache-Control": "no-store"},
        )

    async def _ws(self, websocket: WebSocket) -> None:
        await self.start()
        await websocket.accept()
        self._clients.add(websocket)
        try:
            await websocket.send_json({"type": "connected", "version": self._version})
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            self._clients.discard(websocket)


def mount_dev_reload(
    app: Any,
    *,
    config: DevReloadConfig | None = None,
    **config_kwargs: Any,
) -> DevReloader:
    """Mount development reload routes and start the watcher with the app.

    The mounted routes are:

    - ``<url_prefix>/client.js``: tiny reconnecting browser client.
    - ``<url_prefix>/ws``: websocket used to trigger browser reloads.
    - ``<url_prefix>/state``: diagnostic endpoint.
    """

    if config is None:
        config = DevReloadConfig(**config_kwargs)
    elif config_kwargs:
        raise TypeError("pass either config= or keyword args, not both")

    reloader = DevReloader(config)
    for route in reloader.routes():
        app.router.routes.append(route)

    state = getattr(app, "state", None)
    if state is not None:
        setattr(state, "llming_stage_dev_reloader", reloader)

    if hasattr(app, "add_event_handler"):
        app.add_event_handler("startup", reloader.start)
        app.add_event_handler("shutdown", reloader.stop)
    return reloader


def dev_reload_head(url_prefix: str = "/_stage/dev") -> str:
    """Return the script tag needed by non-shell pages in development."""

    prefix = url_prefix.rstrip("/")
    return f'<script src="{prefix}/client.js" defer></script>'


def _iter_watch_files(
    roots: Iterable[Path | str],
    *,
    extensions: frozenset[str],
    ignore_dirs: frozenset[str],
) -> Iterable[Path]:
    stack = [Path(root).resolve() for root in roots]
    seen_dirs: set[Path] = set()
    while stack:
        root = stack.pop()
        if root in seen_dirs:
            continue
        seen_dirs.add(root)
        try:
            with os.scandir(root) as entries:
                for entry in entries:
                    name = entry.name
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if name not in ignore_dirs:
                                stack.append(Path(entry.path))
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                    except OSError:
                        continue
                    path = Path(entry.path)
                    if path.suffix.lower() in extensions:
                        yield path
        except (FileNotFoundError, NotADirectoryError, PermissionError):
            continue


def _state_for(path: Path, previous: _FileState | None) -> _FileState | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    if previous and previous.mtime_ns == stat.st_mtime_ns and previous.size == stat.st_size:
        return previous
    try:
        data = path.read_bytes()
    except OSError:
        return None
    digest = blake2b(data, digest_size=16).hexdigest()
    return _FileState(mtime_ns=stat.st_mtime_ns, size=stat.st_size, digest=digest)


def _change_payload(change: FileChange) -> dict[str, str]:
    return {"path": str(change.path), "kind": change.kind}


async def _close_client(client: WebSocket) -> None:
    try:
        await client.close()
    except Exception:
        pass


def _client_script(*, ws_path: str, homepage_path: str) -> str:
    config = json.dumps(
        {"wsPath": ws_path, "homepagePath": homepage_path},
        separators=(",", ":"),
    )
    return f"""(() => {{
  if (window.__llmingStageDevReload) return;
  window.__llmingStageDevReload = true;
  const config = {config};
  const storageKey = "__llmingStageDevReloadLast";
  let retry = 150;
  function fileLabel(files) {{
    if (!Array.isArray(files) || files.length === 0) return "unknown change";
    const names = files.slice(0, 3).map((f) => {{
      const path = String(f.path || "").replace(/\\\\/g, "/");
      return (f.kind || "changed") + " " + (path.split("/").pop() || path);
    }});
    const extra = files.length > 3 ? " +" + (files.length - 3) + " more" : "";
    return names.join(", ") + extra;
  }}
  function logPreviousReload() {{
    let raw = null;
    try {{
      raw = sessionStorage.getItem(storageKey);
      if (raw) sessionStorage.removeItem(storageKey);
    }} catch (_) {{}}
    if (!raw) return;
    try {{
      const info = JSON.parse(raw);
      const ms = performance.now() + performance.timeOrigin - info.at;
      console.info(
        "[llming-stage] reloaded in " + Math.round(ms) + "ms",
        info.label || ""
      );
    }} catch (_) {{}}
  }}
  function wsUrl() {{
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    return proto + "//" + location.host + config.wsPath;
  }}
  function reload(path, msg) {{
    const target = path || config.homepagePath || location.pathname;
    const label = fileLabel(msg && msg.files);
    console.info("[llming-stage] reload requested", label);
    try {{
      sessionStorage.setItem(storageKey, JSON.stringify({{
        at: performance.now() + performance.timeOrigin,
        label,
        version: msg && msg.version,
      }}));
    }} catch (_) {{}}
    if (target && target !== location.pathname) {{
      location.assign(target);
      return;
    }}
    location.reload();
  }}
  function connect() {{
    const socket = new WebSocket(wsUrl());
    socket.onopen = () => {{ retry = 150; }};
    socket.onmessage = (event) => {{
      const msg = JSON.parse(event.data);
      if (msg.type === "reload") reload(msg.path, msg);
      else if (msg.type === "server-reload") console.info("[llming-stage] server reload pending", msg.files || []);
    }};
    socket.onclose = () => {{
      setTimeout(connect, retry);
      retry = Math.min(retry * 1.5, 1500);
    }};
  }}
  logPreviousReload();
  connect();
}})();
"""
