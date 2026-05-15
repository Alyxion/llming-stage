"""Opt-in process-introspection API.

Activate by setting ``LLMING_STAGE_DEBUG=1`` in the environment **before**
importing/launching the app. When enabled, ``Stage`` mounts a WebSocket
endpoint at ``<asset_prefix>/debug/ws`` that responds to JSON queries
about the running process (CPU/memory, threads, loaded modules, recent
stdout/stderr, …).

**Disabled by default.** **Never enabled implicitly.** When enabled,
the endpoint binds to whichever interface the host app binds to — pair
with a token (``LLMING_STAGE_DEBUG_TOKEN``) when binding non-loopback.

**Produces no log output of its own.** stdout/stderr are passively
captured into a bounded ring buffer; the original streams still receive
every byte unchanged. Queries return data, never side-effects.

Protocol — JSON request/response on a single WebSocket:

```json
// → request
{"id": 1, "q": "metrics"}

// ← response
{"id": 1, "ok": true, "data": {"cpu_percent": 1.2, "rss_bytes": 145000000, ...}}
```

Queries: ``info``, ``metrics``, ``threads``, ``modules``, ``stack``,
``stdout_tail``, ``stderr_tail``. See ``_HANDLERS`` for the full set.
"""

from __future__ import annotations

import collections
import os
import sys
import threading
import time
import traceback
from typing import Any

from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

_ENV_FLAG = "LLMING_STAGE_DEBUG"
_ENV_TOKEN = "LLMING_STAGE_DEBUG_TOKEN"

_BUFFER_LINES = 1000
_DEFAULT_TAIL = 200

_FALSY = {"", "0", "false", "no", "off"}


def is_debug_enabled() -> bool:
    """Return ``True`` when ``LLMING_STAGE_DEBUG`` is set to a truthy value.

    Truthy means: any non-empty string other than the obvious falsy
    spellings (``0``, ``false``, ``no``, ``off``, case-insensitive).
    """
    value = os.environ.get(_ENV_FLAG, "").strip().lower()
    return value not in _FALSY


# ---------------------------------------------------------------------------
# Silent stdout/stderr capture
# ---------------------------------------------------------------------------


class _RingBuffer:
    """Thread-safe line-oriented ring buffer."""

    def __init__(self, maxlen: int) -> None:
        self._buf: collections.deque[str] = collections.deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._partial = ""

    def write(self, text: str) -> None:
        if not text:
            return
        with self._lock:
            text = self._partial + text
            lines = text.splitlines(keepends=True)
            # `splitlines(keepends=True)` only places a newline-less line
            # at the very end of the result, so partial-line handling is
            # limited to the final element.
            for line in lines[:-1]:
                self._buf.append(line.rstrip("\r\n"))
            if lines:
                last = lines[-1]
                if last.endswith(("\n", "\r")):
                    self._buf.append(last.rstrip("\r\n"))
                    self._partial = ""
                else:
                    self._partial = last

    def tail(self, n: int) -> list[str]:
        with self._lock:
            out = list(self._buf)
            if self._partial:
                out.append(self._partial)
            return out[-n:] if n >= 0 else out


class _TeeStream:
    """Wraps an underlying stream; forwards every write and copies it.

    Attribute access falls through to the underlying stream so callers
    like ``rich`` that probe for ``isatty``, ``encoding``, ``buffer``,
    etc. behave unchanged.
    """

    def __init__(self, underlying: Any, buffer: _RingBuffer) -> None:
        self._underlying = underlying
        self._buffer = buffer

    def write(self, text: str) -> int:
        try:
            self._buffer.write(text)
        except Exception:
            # Capture must never break the host stream.
            pass
        return self._underlying.write(text)

    def writelines(self, lines: Any) -> None:
        for line in lines:
            self.write(line)

    def flush(self) -> None:
        self._underlying.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._underlying, name)


_install_lock = threading.Lock()
_installed = False
_stdout_buffer = _RingBuffer(_BUFFER_LINES)
_stderr_buffer = _RingBuffer(_BUFFER_LINES)
_process_start = time.time()


def install_stream_capture() -> None:
    """Install the stdout/stderr ring-buffer capture.

    Idempotent and safe to call multiple times. Does **not** affect what
    is written to the original streams — terminal and logging continue
    to receive every byte unchanged.
    """
    global _installed
    with _install_lock:
        if _installed:
            return
        sys.stdout = _TeeStream(sys.stdout, _stdout_buffer)  # type: ignore[assignment]
        sys.stderr = _TeeStream(sys.stderr, _stderr_buffer)  # type: ignore[assignment]
        _installed = True


# Install at import time when the env var is already set, so even
# startup output (before any Stage is constructed) gets captured.
if is_debug_enabled():
    install_stream_capture()


# ---------------------------------------------------------------------------
# Query handlers
# ---------------------------------------------------------------------------


def _query_info(_: dict[str, Any]) -> dict[str, Any]:
    import platform

    # Late import to keep the module standalone-loadable.
    from . import LIB_VERSION, __version__

    return {
        "llming_stage_version": __version__,
        "lib_version": LIB_VERSION,
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "pid": os.getpid(),
        "cwd": os.getcwd(),
        "hostname": platform.node(),
        "process_start": _process_start,
        "argv": sys.argv,
    }


def _query_metrics(_: dict[str, Any]) -> dict[str, Any]:
    try:
        import psutil
    except ImportError:
        return {
            "error": "psutil not installed",
            "uptime_seconds": time.time() - _process_start,
        }
    proc = psutil.Process(os.getpid())
    with proc.oneshot():
        cpu = proc.cpu_percent(interval=None)
        mem = proc.memory_info()
        thread_count = proc.num_threads()
        try:
            fds = proc.num_fds()
        except (AttributeError, psutil.AccessDenied):
            fds = None
    return {
        "cpu_percent": cpu,
        "rss_bytes": mem.rss,
        "vms_bytes": mem.vms,
        "threads": thread_count,
        "fds": fds,
        "uptime_seconds": time.time() - _process_start,
    }


def _query_threads(_: dict[str, Any]) -> list[dict[str, Any]]:
    frames = sys._current_frames()
    out: list[dict[str, Any]] = []
    for t in threading.enumerate():
        frame = frames.get(t.ident)
        entry: dict[str, Any] = {
            "ident": t.ident,
            "name": t.name,
            "daemon": t.daemon,
            "alive": t.is_alive(),
        }
        if frame is not None:
            entry["file"] = frame.f_code.co_filename
            entry["line"] = frame.f_lineno
            entry["function"] = frame.f_code.co_name
        out.append(entry)
    return out


def _query_modules(_: dict[str, Any]) -> list[dict[str, Any]]:
    import warnings

    stdlib = getattr(sys, "stdlib_module_names", frozenset())
    out: list[dict[str, Any]] = []
    for name in sorted(sys.modules):
        if "." in name:
            continue
        if name in stdlib:
            continue
        if name.startswith("_"):
            continue
        mod = sys.modules.get(name)
        if mod is None:
            continue
        # Some libraries emit DeprecationWarning on __version__ access
        # (e.g. Click 9). Probing is a read-only introspection, not a
        # call into deprecated behaviour — suppress.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            version = getattr(mod, "__version__", None) or getattr(mod, "version", None)
        out.append(
            {
                "name": name,
                "version": str(version) if version else None,
                "file": getattr(mod, "__file__", None),
            }
        )
    return out


def _query_stack(args: dict[str, Any]) -> dict[str, Any]:
    ident_arg = args.get("ident")
    frames = sys._current_frames()
    if ident_arg is None:
        # Default: the main thread.
        for t in threading.enumerate():
            if t.name == "MainThread":
                ident_arg = t.ident
                break
    try:
        ident = int(ident_arg) if ident_arg is not None else None
    except (TypeError, ValueError):
        return {"error": f"invalid ident: {ident_arg!r}"}
    frame = frames.get(ident) if ident is not None else None
    if frame is None:
        return {"error": f"no live frame for ident={ident}"}
    return {
        "ident": ident,
        "stack": [
            {"file": f.filename, "line": f.lineno, "function": f.name, "text": f.line}
            for f in traceback.extract_stack(frame)
        ],
    }


def _session_registry(websocket: WebSocket | None) -> Any:
    """Return the session registry this Stage instance mounted, or ``None``.

    Only checks ``app.state.llming_stage_registry`` — the attribute that
    ``Stage.session()`` writes when it mounts the conventional
    ``/api/session`` + WebSocket endpoints. **No fallback to the
    llming-com singleton**: a populated singleton from some other
    process / Stage / direct user is not "this app's sessions" and
    would mislead the runner UI into reporting them as available.
    """
    if websocket is None:
        return None
    app = getattr(websocket, "app", None)
    state = getattr(app, "state", None) if app is not None else None
    if state is None:
        return None
    return getattr(state, "llming_stage_registry", None)


def _session_record(session_id: str, entry: Any) -> dict[str, Any]:
    """Squash a session entry into JSON-safe shape, tolerating attribute drift."""

    def pick(*names: str) -> Any:
        for n in names:
            v = getattr(entry, n, None)
            if v is not None:
                return v
        return None

    state = pick("state") or {}
    if isinstance(state, dict):
        state_keys = sorted(state.keys())
    else:
        state_keys = []
    return {
        "session_id": session_id,
        "user_id": pick("user_id"),
        "last_seen": pick("last_seen", "last_message_at", "updated_at"),
        "created_at": pick("created_at", "registered_at"),
        "controller_ready": getattr(entry, "controller", None) is not None,
        "state_keys": state_keys,
    }


def _all_sessions(registry: Any) -> list[tuple[str, Any]]:
    """Best-effort iteration over a registry's sessions."""
    for attr in ("items", "_sessions", "sessions"):
        candidate = getattr(registry, attr, None)
        if callable(candidate):
            try:
                return list(candidate())
            except TypeError:
                pass
        elif isinstance(candidate, dict):
            return list(candidate.items())
    return []


def _query_sessions(args: dict[str, Any], websocket: WebSocket | None) -> dict[str, Any]:
    registry = _session_registry(websocket)
    if registry is None:
        return {"available": False, "sessions": []}
    items = _all_sessions(registry)
    sessions = [_session_record(sid, entry) for sid, entry in items]
    # Most-recent first. None → push to bottom by treating as -inf.
    sessions.sort(key=lambda s: (s.get("last_seen") or s.get("created_at") or 0), reverse=True)
    return {"available": True, "sessions": sessions}


def _query_session_state(args: dict[str, Any], websocket: WebSocket | None) -> dict[str, Any]:
    sid = args.get("session_id")
    if not sid:
        return {"error": "session_id required"}
    registry = _session_registry(websocket)
    if registry is None:
        return {"error": "no session registry mounted"}
    entry = registry.get_session(sid) if hasattr(registry, "get_session") else None
    if entry is None:
        return {"error": f"session not found: {sid}"}
    state = getattr(entry, "state", {}) or {}
    # Convert to JSON-safe values.
    def safe(v: Any) -> Any:
        if isinstance(v, dict):
            return {k: safe(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [safe(x) for x in v]
        if isinstance(v, (str, int, float, bool)) or v is None:
            return v
        return f"<{type(v).__name__}>"
    return {
        "record": _session_record(sid, entry),
        "state": safe(state),
    }


def _query_stdout_tail(args: dict[str, Any]) -> list[str]:
    n = int(args.get("n", _DEFAULT_TAIL))
    return _stdout_buffer.tail(n)


def _query_stderr_tail(args: dict[str, Any]) -> list[str]:
    n = int(args.get("n", _DEFAULT_TAIL))
    return _stderr_buffer.tail(n)


# Plain handlers receive `args` only.
_HANDLERS: dict[str, Any] = {
    "info": _query_info,
    "metrics": _query_metrics,
    "threads": _query_threads,
    "modules": _query_modules,
    "stack": _query_stack,
    "stdout_tail": _query_stdout_tail,
    "stderr_tail": _query_stderr_tail,
}

# Context-aware handlers receive (args, websocket) so they can look up the
# host app's session registry from the connection's scope.
_CTX_HANDLERS: dict[str, Any] = {
    "sessions": _query_sessions,
    "session_state": _query_session_state,
}


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


def _check_token(websocket: WebSocket) -> bool:
    expected = os.environ.get(_ENV_TOKEN, "").strip()
    if not expected:
        return True
    got = websocket.query_params.get("token", "")
    # Constant-time-ish compare. Strings short enough that `==` is fine
    # in practice; using hmac.compare_digest for principle.
    import hmac

    return hmac.compare_digest(got, expected)


async def _debug_ws(websocket: WebSocket) -> None:
    if not _check_token(websocket):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    try:
        while True:
            try:
                msg = await websocket.receive_json()
            except (WebSocketDisconnect, ValueError):
                break
            if not isinstance(msg, dict):
                await websocket.send_json(
                    {"ok": False, "error": "expected JSON object"}
                )
                continue
            qid = msg.get("id")
            q = msg.get("q", "")
            args = msg.get("args") or {}
            if not isinstance(args, dict):
                await websocket.send_json(
                    {"id": qid, "ok": False, "error": "args must be an object"}
                )
                continue
            handler = _HANDLERS.get(q)
            ctx_handler = _CTX_HANDLERS.get(q) if handler is None else None
            if handler is None and ctx_handler is None:
                await websocket.send_json(
                    {
                        "id": qid,
                        "ok": False,
                        "error": f"unknown query: {q!r}",
                        "available": sorted({*_HANDLERS, *_CTX_HANDLERS}),
                    }
                )
                continue
            try:
                if ctx_handler is not None:
                    data = ctx_handler(args, websocket)
                else:
                    data = handler(args)
            except Exception as exc:  # pragma: no cover  (defensive)
                await websocket.send_json(
                    {"id": qid, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
                )
                continue
            await websocket.send_json({"id": qid, "ok": True, "data": data})
    except WebSocketDisconnect:
        pass


def mount_debug(app: Any, *, asset_prefix: str = "/_stage") -> None:
    """Mount the debug WebSocket at ``<asset_prefix>/debug/ws``.

    Idempotent per app (keyed on ``asset_prefix``). Side-effect: installs
    the silent stdout/stderr ring-buffer capture (only the first call has
    any effect). Both the env var check and this function are needed to
    actually expose the endpoint — callers using ``Stage`` get it
    automatically when ``LLMING_STAGE_DEBUG`` is truthy; callers using
    ``mount_assets`` directly can call this themselves.
    """
    install_stream_capture()
    state = getattr(app, "state", None)
    flag = f"llming_stage_debug_mounted_{asset_prefix}"
    if state is not None and getattr(state, flag, False):
        return
    route = WebSocketRoute(f"{asset_prefix}/debug/ws", _debug_ws)
    app.router.routes.append(route)
    if state is not None:
        setattr(state, flag, True)


__all__ = [
    "install_stream_capture",
    "is_debug_enabled",
    "mount_debug",
]
