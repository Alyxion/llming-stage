"""Opt-in process-introspection API.

Activate by setting ``LLMING_STAGE_DEBUG=1`` in the environment **before**
importing/launching the app. When enabled, ``Stage`` mounts a WebSocket
endpoint at ``<asset_prefix>/debug/ws`` that responds to JSON queries
about the running process (CPU/memory, threads, loaded modules, recent
stdout/stderr, …).

**Disabled by default.** **Never enabled implicitly.** When enabled,
the endpoint binds to whichever interface the host app binds to and
always requires a token (``LLMING_STAGE_DEBUG_TOKEN``).

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
import asyncio
import inspect
import itertools
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
_DEFAULT_HEARTBEAT_TTL = 120.0

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
_js_eval_seq = itertools.count(1)
_js_console_logs: dict[str, collections.deque[dict[str, Any]]] = {}
_js_eval_waiters: dict[str, asyncio.Future[dict[str, Any]]] = {}
_js_console_lock = threading.Lock()


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


# ---------------------------------------------------------------------------
# Per-session browser console bridge
# ---------------------------------------------------------------------------


def _safe_text(value: Any, *, limit: int = 20000) -> str:
    if isinstance(value, str):
        text = value
    else:
        try:
            import json

            text = json.dumps(value, ensure_ascii=False)
        except Exception:
            text = str(value)
    return text if len(text) <= limit else text[:limit] + "..."


def _append_js_log(session_id: str, entry: dict[str, Any]) -> None:
    if not session_id:
        return
    record = {
        "ts": time.time(),
        "tag": _safe_text(entry.get("tag") or "[JS]", limit=32),
        "text": _safe_text(entry.get("text") or ""),
    }
    with _js_console_lock:
        buf = _js_console_logs.setdefault(
            session_id, collections.deque(maxlen=_BUFFER_LINES)
        )
        buf.append(record)


def record_js_console(session_id: str, payload: dict[str, Any]) -> None:
    """Record a browser console line emitted by a debug-enabled session."""

    level = _safe_text(payload.get("level") or "log", limit=16)
    tag = {
        "error": "[JS!]",
        "warn": "[JS*]",
        "debug": "[JS?]",
        "info": "[JSi]",
        "log": "[JS]",
    }.get(level, "[JS]")
    _append_js_log(session_id, {"tag": tag, "text": payload.get("text", "")})


def record_js_eval_result(session_id: str, payload: dict[str, Any]) -> None:
    """Record and resolve a browser-side JavaScript eval result."""

    eval_id = _safe_text(payload.get("id") or "", limit=128)
    ok = bool(payload.get("ok"))
    text = payload.get("result") if ok else payload.get("error")
    result = {
        "id": eval_id,
        "ok": ok,
        "text": _safe_text(text if text is not None else ""),
    }
    _append_js_log(
        session_id,
        {"tag": "<-" if ok else "x", "text": result["text"]},
    )
    future = _js_eval_waiters.pop(eval_id, None)
    if future is not None and not future.done():
        future.set_result(result)


def _js_console_tail(session_id: str, n: int) -> list[dict[str, Any]]:
    with _js_console_lock:
        buf = _js_console_logs.get(session_id)
        if not buf:
            return []
        items = list(buf)
    return items[-n:] if n >= 0 else items


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
    # Snapshot under the GIL so concurrent imports can't raise
    # `RuntimeError: dictionary changed size during iteration`.
    module_names = sorted(list(sys.modules))
    out: list[dict[str, Any]] = []
    for name in module_names:
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


def _mono_to_epoch(monotonic_seconds: float | None) -> float | None:
    """Convert a ``time.monotonic()`` value to a Unix epoch second.

    llming-com's ``BaseSessionEntry`` records ``last_activity`` and
    related fields with ``time.monotonic()``, which is a process-local
    clock — feeding it to ``new Date(ts*1000)`` in the runner UI
    renders timestamps in 1970. We rebase against the current
    monotonic→epoch offset so the UI shows wall-clock times.
    """
    if monotonic_seconds is None:
        return None
    return time.time() - (time.monotonic() - monotonic_seconds)


def _session_record(session_id: str, entry: Any) -> dict[str, Any]:
    """Squash a session entry into JSON-safe shape, tolerating attribute drift."""

    def pick_mono(*names: str) -> float | None:
        for n in names:
            v = getattr(entry, n, None)
            if v is not None:
                return v
        return None

    state = getattr(entry, "state", None) or {}
    if isinstance(state, dict):
        state_keys = sorted(state.keys())
    else:
        state_keys = []
    # llming-com's BaseSessionEntry only exposes `last_activity` as a
    # monotonic timestamp. Fall back to created_at-style fields for
    # subclasses that add them; default to last_activity if nothing
    # else is set so freshly-registered sessions get a usable "joined"
    # column instead of an empty cell.
    last_seen_mono = pick_mono("last_seen", "last_message_at", "updated_at", "last_activity")
    created_at_mono = pick_mono("created_at", "registered_at", "last_activity")
    last_heartbeat_mono = pick_mono("last_heartbeat")
    heartbeat_age = (
        time.monotonic() - last_heartbeat_mono
        if last_heartbeat_mono is not None
        else None
    )
    try:
        from llming_com.session import DEFAULT_HEARTBEAT_TTL
    except Exception:
        DEFAULT_HEARTBEAT_TTL = _DEFAULT_HEARTBEAT_TTL
    heartbeat_timeout = (
        heartbeat_age is None or heartbeat_age > float(DEFAULT_HEARTBEAT_TTL)
    )
    return {
        "session_id": session_id,
        "user_id": getattr(entry, "user_id", None),
        "last_seen": _mono_to_epoch(last_seen_mono),
        "created_at": _mono_to_epoch(created_at_mono),
        "last_heartbeat": _mono_to_epoch(last_heartbeat_mono),
        "heartbeat_age_seconds": heartbeat_age,
        "heartbeat_timeout_seconds": float(DEFAULT_HEARTBEAT_TTL),
        "heartbeat_status": "timeout" if heartbeat_timeout else "alive",
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


def _query_js_console_tail(args: dict[str, Any], websocket: WebSocket | None) -> dict[str, Any]:
    sid = args.get("session_id")
    if not sid:
        return {"error": "session_id required", "logs": []}
    try:
        n = int(args.get("n", _DEFAULT_TAIL))
    except (TypeError, ValueError):
        n = _DEFAULT_TAIL
    registry = _session_registry(websocket)
    if registry is None:
        return {"error": "no session registry mounted", "logs": []}
    entry = registry.get_session(sid) if hasattr(registry, "get_session") else None
    if entry is None:
        return {"error": f"session not found: {sid}", "logs": []}
    return {
        "record": _session_record(sid, entry),
        "logs": _js_console_tail(str(sid), n),
    }


async def _query_js_eval(args: dict[str, Any], websocket: WebSocket | None) -> dict[str, Any]:
    sid = args.get("session_id")
    code = args.get("code")
    if not sid:
        return {"ok": False, "error": "session_id required", "logs": []}
    if not isinstance(code, str) or not code.strip():
        return {"ok": False, "error": "code required", "logs": _js_console_tail(str(sid), _DEFAULT_TAIL)}
    registry = _session_registry(websocket)
    if registry is None:
        return {"ok": False, "error": "no session registry mounted", "logs": []}
    entry = registry.get_session(sid) if hasattr(registry, "get_session") else None
    if entry is None:
        return {"ok": False, "error": f"session not found: {sid}", "logs": []}
    controller = getattr(entry, "controller", None)
    if controller is None:
        _append_js_log(str(sid), {"tag": "x", "text": "session has no active WebSocket"})
        return {
            "ok": False,
            "error": "session has no active WebSocket",
            "logs": _js_console_tail(str(sid), _DEFAULT_TAIL),
        }

    eval_id = f"{sid}:{int(time.time() * 1000)}:{next(_js_eval_seq)}"
    loop = asyncio.get_running_loop()
    future: asyncio.Future[dict[str, Any]] = loop.create_future()
    _js_eval_waiters[eval_id] = future
    _append_js_log(str(sid), {"tag": ">", "text": code})

    try:
        sent = False
        send = getattr(controller, "send", None)
        if callable(send):
            sent = bool(
                await send(
                    {
                        "type": "llming.debug.eval",
                        "id": eval_id,
                        "code": code,
                    }
                )
            )
        if not sent:
            _js_eval_waiters.pop(eval_id, None)
            _append_js_log(str(sid), {"tag": "x", "text": "failed to send eval command"})
            return {
                "ok": False,
                "error": "failed to send eval command",
                "logs": _js_console_tail(str(sid), _DEFAULT_TAIL),
            }
        timeout = float(args.get("timeout", 8.0) or 8.0)
        result = await asyncio.wait_for(future, timeout=max(0.5, min(timeout, 30.0)))
        return {
            **result,
            "logs": _js_console_tail(str(sid), _DEFAULT_TAIL),
        }
    except asyncio.TimeoutError:
        _js_eval_waiters.pop(eval_id, None)
        _append_js_log(str(sid), {"tag": "x", "text": "JavaScript eval timed out"})
        return {
            "ok": False,
            "error": "JavaScript eval timed out",
            "logs": _js_console_tail(str(sid), _DEFAULT_TAIL),
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
    "js_console_tail": _query_js_console_tail,
    "js_eval": _query_js_eval,
}


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


def _check_auth(websocket: WebSocket) -> bool:
    """Allow the connection?

    ``LLMING_STAGE_DEBUG_TOKEN`` is mandatory. Loopback-only checks are
    not enough because any web page can attempt a WebSocket connection
    to a user's localhost service; a bearer token keeps the endpoint
    unreachable unless the runner/operator knows it.
    """
    expected = os.environ.get(_ENV_TOKEN, "").strip()
    if not expected:
        return False
    import hmac
    got = websocket.query_params.get("token", "")
    return hmac.compare_digest(got, expected)


async def _debug_ws(websocket: WebSocket) -> None:
    if not _check_auth(websocket):
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
                if inspect.isawaitable(data):
                    data = await data
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
    if not is_debug_enabled():
        return
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
    "record_js_console",
    "record_js_eval_result",
]
