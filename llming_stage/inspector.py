"""Standalone inspector for already-running llming-stage apps."""

from __future__ import annotations

import asyncio
import contextlib
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import httpx
import websockets
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, Response
from starlette.requests import Request
from starlette.websockets import WebSocketDisconnect

from .shell import mount_assets

_ASSET_PREFIX = "/_inspector_stage"
_TARGET_QUERY = "_llming_inspector_target"

_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


@dataclass(frozen=True)
class InspectorConfig:
    target: str
    token: str = ""


def create_inspector_app(config: InspectorConfig) -> FastAPI:
    """Create a same-origin inspector proxy for *config.target*."""

    target = _normalize_target(config.target)
    client = httpx.AsyncClient(follow_redirects=False, timeout=30.0)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await client.aclose()

    app = FastAPI(lifespan=lifespan)
    mount_assets(app, asset_prefix=_ASSET_PREFIX)

    @app.get("/")
    async def inspector_index(request: Request) -> Response:
        if request.query_params.get(_TARGET_QUERY) == "1":
            return await _proxy_http(client, request, target, "")
        return HTMLResponse(
            _INSPECTOR_HTML
            .replace("__ASSET_PREFIX__", _ASSET_PREFIX)
            .replace("__TARGET_QUERY__", _TARGET_QUERY)
            .replace("__TARGET_JSON__", json.dumps(target))
            .replace("__DEBUG_TOKEN_JSON__", json.dumps(config.token))
        )

    @app.get("/_inspector_config")
    async def inspector_config() -> dict[str, str]:
        return {"target": target, "token": bool(config.token)}

    @app.websocket("/{path:path}")
    async def proxy_websocket(websocket: WebSocket, path: str) -> None:
        await _proxy_websocket(websocket, target, path)

    @app.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    )
    async def proxy_http(request: Request, path: str) -> Response:
        return await _proxy_http(client, request, target, path)

    return app


def _normalize_target(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("inspect target must be an absolute http(s) URL")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _target_http_url(target: str, path: str, query: bytes) -> str:
    suffix = "/" + path.lstrip("/")
    if path == "":
        suffix = "/"
    url = target.rstrip("/") + suffix
    if query:
        url += "?" + query.decode("latin-1")
    return url


def _target_ws_url(target: str, path: str, query: bytes) -> str:
    parsed = urlsplit(_target_http_url(target, path, query))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, ""))


def _proxy_headers(
    headers: list[tuple[bytes, bytes]],
    *,
    websocket: bool = False,
) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw_name, raw_value in headers:
        name = raw_name.decode("latin-1")
        lower = name.lower()
        if lower in _HOP_HEADERS:
            continue
        if websocket and (lower == "host" or lower.startswith("sec-websocket-")):
            continue
        out[name] = raw_value.decode("latin-1")
    return out


def _response_headers(headers: httpx.Headers) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, value in headers.items():
        lower = name.lower()
        if lower in _HOP_HEADERS or lower == "content-length":
            continue
        out[name] = value
    return out


async def _proxy_http(
    client: httpx.AsyncClient,
    request: Request,
    target: str,
    path: str,
) -> Response:
    upstream = await client.request(
        request.method,
        _target_http_url(target, path, request.scope.get("query_string", b"")),
        headers=_proxy_headers(request.scope.get("headers", [])),
        content=await request.body(),
    )
    return Response(
        upstream.content,
        status_code=upstream.status_code,
        headers=_response_headers(upstream.headers),
        media_type=upstream.headers.get("content-type"),
    )


async def _proxy_websocket(websocket: WebSocket, target: str, path: str) -> None:
    upstream_url = _target_ws_url(target, path, websocket.scope.get("query_string", b""))
    headers = _proxy_headers(websocket.scope.get("headers", []), websocket=True)
    await websocket.accept()
    try:
        async with websockets.connect(upstream_url, additional_headers=headers) as upstream:
            client_to_upstream = asyncio.create_task(
                _relay_client_to_upstream(websocket, upstream)
            )
            upstream_to_client = asyncio.create_task(
                _relay_upstream_to_client(websocket, upstream)
            )
            done, pending = await asyncio.wait(
                {client_to_upstream, upstream_to_client},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in done:
                with contextlib.suppress(Exception):
                    task.result()
    except Exception:
        with contextlib.suppress(Exception):
            await websocket.close(code=1011)


async def _relay_client_to_upstream(websocket: WebSocket, upstream: object) -> None:
    while True:
        try:
            message = await websocket.receive()
        except WebSocketDisconnect:
            await upstream.close()  # type: ignore[attr-defined]
            return
        msg_type = message.get("type")
        if msg_type == "websocket.disconnect":
            await upstream.close()  # type: ignore[attr-defined]
            return
        if "text" in message:
            await upstream.send(message["text"])  # type: ignore[attr-defined]
        elif "bytes" in message:
            await upstream.send(message["bytes"])  # type: ignore[attr-defined]


async def _relay_upstream_to_client(websocket: WebSocket, upstream: object) -> None:
    async for message in upstream:  # type: ignore[operator]
        if isinstance(message, bytes):
            await websocket.send_bytes(message)
        else:
            await websocket.send_text(message)


_INSPECTOR_HTML = r"""<!doctype html>
<html lang="en" class="full-height">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>llming-stage inspector</title>
<link rel="stylesheet" href="__ASSET_PREFIX__/fonts/fonts.css">
<link rel="stylesheet" href="__ASSET_PREFIX__/vendor/quasar.prod.css">
<style>
  :root {
    --rn-bg: #0b1220;
    --rn-surface: #111a2c;
    --rn-surface2: #18243a;
    --rn-border: rgba(255,255,255,0.08);
    --rn-text: #e2e8f0;
    --rn-text-dim: #94a3b8;
    --rn-text-mut: #64748b;
    --rn-accent: #6366f1;
    --rn-positive: #10b981;
    --rn-warning: #f59e0b;
    --rn-mono: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace;
  }
  html, body, #app, .q-layout {
    height: 100%;
    margin: 0;
    background: var(--rn-bg);
    color: var(--rn-text);
    font-family: "Roboto", system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  .rn-header {
    background: var(--rn-surface) !important;
    border-bottom: 1px solid var(--rn-border);
    box-shadow: none !important;
  }
  .rn-header .q-toolbar { min-height: 48px; padding: 0 14px; gap: 8px; }
  .rn-title { display: flex; flex-direction: column; line-height: 1.12; }
  .rn-title-main { font-size: 16px; font-weight: 700; color: var(--rn-text); }
  .rn-title-sub {
    margin-top: 2px;
    color: var(--rn-text-mut);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }
  .rn-target {
    display: inline-flex;
    align-items: center;
    max-width: 42vw;
    height: 24px;
    padding: 0 9px;
    border-radius: 6px;
    background: var(--rn-surface2);
    color: var(--rn-text-dim);
    font-family: var(--rn-mono);
    font-size: 11px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .rn-header .q-btn {
    min-height: 30px;
    padding: 0 9px;
    color: var(--rn-text-dim);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .rn-header .q-btn:hover { color: var(--rn-text); }
  .rn-frame { width: 100%; height: 100%; border: 0; background: white; }
  .rn-debug {
    background: var(--rn-bg) !important;
    border-top: 1px solid var(--rn-border);
    color: var(--rn-text);
  }
  .rn-debug-resize {
    position: absolute;
    left: 0;
    right: 0;
    top: -4px;
    height: 8px;
    cursor: ns-resize;
    z-index: 3;
  }
  .rn-debug-resize::before {
    content: "";
    position: absolute;
    left: 50%;
    top: 3px;
    width: 72px;
    height: 2px;
    transform: translateX(-50%);
    border-radius: 999px;
    background: rgba(148,163,184,0.5);
  }
  .rn-debug-drag-cover {
    position: fixed;
    inset: 0;
    z-index: 10000;
    cursor: ns-resize;
  }
  .rn-debug-header, .rn-session-tabs, .rn-actions-toolbar, .rn-console-bar {
    background: var(--rn-surface);
    border-bottom: 1px solid var(--rn-border);
  }
  .rn-debug-header {
    height: 34px;
    padding: 7px 12px;
    flex: 0 0 auto;
  }
  .rn-debug-title {
    color: var(--rn-text-dim);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.15em;
    text-transform: uppercase;
  }
  .rn-debug-status, .rn-session-flag, .rn-live-pill {
    border-radius: 999px;
    background: var(--rn-surface2);
    color: var(--rn-text-dim);
    font-size: 10px;
    font-weight: 700;
    padding: 2px 8px;
  }
  .rn-debug-status--on, .rn-session-flag--on, .rn-live-pill {
    background: rgba(16,185,129,0.14);
    color: var(--rn-positive);
  }
  .rn-tabs {
    width: 144px;
    min-width: 144px;
    background: var(--rn-surface);
    border-right: 1px solid var(--rn-border);
  }
  .rn-tab {
    min-height: 36px;
    padding: 0 16px;
    border-left: 2px solid transparent;
    color: var(--rn-text-dim);
    cursor: pointer;
    font-size: 12px;
  }
  .rn-tab:hover, .rn-tab--active {
    background: var(--rn-surface2);
    border-left-color: var(--rn-accent);
    color: var(--rn-text);
  }
  .rn-detail { background: var(--rn-bg); }
  .rn-debug * { scrollbar-color: rgba(100,116,139,0.7) rgba(15,23,42,0.7); scrollbar-width: thin; }
  .rn-debug *::-webkit-scrollbar { width: 9px; height: 9px; }
  .rn-debug *::-webkit-scrollbar-track { background: rgba(15,23,42,0.7); }
  .rn-debug *::-webkit-scrollbar-thumb {
    background: rgba(100,116,139,0.7);
    border: 2px solid rgba(15,23,42,0.7);
    border-radius: 999px;
  }
  .rn-console {
    margin: 0;
    padding: 12px 14px;
    background: #050912;
    color: #cbd5e1;
    font: 12px/1.5 var(--rn-mono);
    white-space: pre;
    overflow: auto;
  }
  .rn-console-input {
    background: var(--rn-surface);
    border-top: 1px solid var(--rn-border);
    padding: 0 10px;
  }
  .rn-console-input input {
    flex: 1;
    border: 0;
    outline: none;
    background: transparent;
    color: var(--rn-text);
    font: 12px/1.4 var(--rn-mono);
    padding: 8px 0;
  }
  .rn-console-input input:disabled {
    color: var(--rn-text-mut);
    cursor: not-allowed;
  }
  .rn-prompt { color: #818cf8; font-family: var(--rn-mono); padding-right: 8px; }
  .rn-section-header {
    position: sticky;
    top: 0;
    z-index: 1;
    padding: 10px 14px 5px;
    background: var(--rn-surface);
    border-bottom: 1px solid var(--rn-border);
    color: var(--rn-text-mut);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }
  .rn-list-row {
    border-bottom: 1px solid var(--rn-border);
    color: var(--rn-text);
    font: 12px/1.45 var(--rn-mono);
    padding: 6px 14px;
  }
  .rn-sub, .rn-dim { color: var(--rn-text-dim); font-size: 11px; }
  .rn-empty { padding: 18px; color: var(--rn-text-dim); }
  .rn-empty-title {
    color: var(--rn-text);
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .rn-empty-hint { margin-top: 7px; font-size: 12px; line-height: 1.45; }
  .rn-sessions-list {
    width: 260px;
    flex: 0 0 260px;
    min-width: 220px;
    max-width: 300px;
    border-right: 1px solid var(--rn-border);
    overflow: hidden;
    position: relative;
    z-index: 2;
  }
  .rn-sessions-bar { height: 30px; padding: 0 12px; background: var(--rn-surface); border-bottom: 1px solid var(--rn-border); }
  .rn-stat-label {
    color: var(--rn-text-mut);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }
  .rn-stat-value {
    color: var(--rn-text);
    font-family: var(--rn-mono);
    font-size: 20px;
    font-weight: 700;
    line-height: 1.2;
    margin-top: 3px;
    overflow-wrap: anywhere;
  }
  .rn-stat-unit { color: var(--rn-text-mut); font-size: 11px; margin-left: 2px; }
  .rn-session-row {
    border-bottom: 1px solid var(--rn-border);
    color: var(--rn-text);
    cursor: pointer;
    padding: 8px 12px;
  }
  .rn-session-row:hover, .rn-session-row--active {
    background: var(--rn-surface2);
  }
  .rn-session-row--active { border-left: 2px solid var(--rn-accent); padding-left: 10px; }
  .rn-session-id { font-family: var(--rn-mono); font-size: 12px; }
  .rn-session-flag--timeout, .rn-heartbeat--timeout {
    background: rgba(245,158,11,0.14);
    color: var(--rn-warning);
  }
  .rn-session-tabs { display: flex; gap: 4px; padding: 7px 10px; }
  .rn-session-tab {
    min-height: 24px;
    border: 1px solid transparent;
    border-radius: 5px;
    background: transparent;
    color: var(--rn-text-dim);
    cursor: pointer;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.08em;
    padding: 0 10px;
    text-transform: uppercase;
  }
  .rn-session-tab--active, .rn-session-tab:hover {
    background: var(--rn-surface2);
    border-color: var(--rn-border);
    color: var(--rn-text);
  }
  .rn-actions-toolbar { height: 42px; padding: 6px 10px; gap: 8px; }
  .rn-actions-search {
    width: 260px;
    max-width: 45vw;
    border: 1px solid var(--rn-border);
    border-radius: 6px;
    outline: none;
    background: var(--rn-bg);
    color: var(--rn-text);
    font: 12px/1.3 var(--rn-mono);
    padding: 6px 9px;
  }
  .rn-action-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 10px;
    padding: 12px;
    min-width: 0;
  }
  .rn-action-tile {
    min-height: 74px;
    border: 1px solid var(--rn-border);
    border-radius: 7px;
    background: var(--rn-surface);
    color: var(--rn-text);
    cursor: pointer;
    padding: 10px 12px;
    text-align: left;
  }
  .rn-action-tile:hover { background: var(--rn-surface2); }
  .rn-action-tile-title { display: block; font-size: 13px; font-weight: 800; line-height: 1.25; }
  .rn-action-tile-meta { display: block; margin-top: 5px; color: var(--rn-text-mut); font: 10px/1.3 var(--rn-mono); }
  .rn-action-msg { color: var(--rn-text-dim); font: 11px/1.4 var(--rn-mono); }
  .rn-state {
    margin: 0;
    padding: 8px 14px;
    background: var(--rn-bg);
    color: var(--rn-text);
    font: 11px/1.4 var(--rn-mono);
    white-space: pre;
    overflow: auto;
  }
  .rn-kv { display: flex; gap: 12px; padding: 5px 14px; font: 12px/1.4 var(--rn-mono); }
  .rn-kv-key { width: 150px; color: var(--rn-text-mut); }
</style>
</head>
<body class="full-height no-margin">
<div id="app" class="full-height">
  <q-layout view="hHh Lpr fFf">
    <q-header class="rn-header">
      <q-toolbar>
        <q-toolbar-title class="row items-center no-wrap">
          <div class="rn-title">
            <span class="rn-title-main">llming-stage inspector</span>
            <span class="rn-title-sub">Attached app</span>
          </div>
          <span class="rn-target q-ml-md">{{ target }}</span>
        </q-toolbar-title>
        <q-btn flat dense icon="refresh" label="reload" @click="reload"></q-btn>
        <q-btn flat dense icon="open_in_new" label="open target" @click="openTarget"></q-btn>
        <q-btn flat dense round icon="bug_report"
               :style="debugDrawer ? { color: 'var(--rn-positive)' } : {}"
               @click="toggleDebugDrawer" data-test="btn-debug">
          <q-tooltip>Debug pane ({{ debugStatus }})</q-tooltip>
        </q-btn>
        <q-btn flat dense round :icon="dark ? 'light_mode' : 'dark_mode'"
               @click="toggleDark"></q-btn>
      </q-toolbar>
    </q-header>

    <q-page-container>
      <q-page class="column no-padding overflow-hidden" :style-fn="pageStyleFn">
        <iframe ref="frameEl" :key="iframeKey" :src="iframeSrc" class="rn-frame"
                data-test="inspector-frame" @load="onFrameLoad"></iframe>
      </q-page>
    </q-page-container>

    <q-footer v-if="debugDrawer" class="rn-debug" :style="{ height: debugHeight + 'px' }">
      <div class="rn-debug-resize" @pointerdown="startDebugResize"></div>
      <div v-if="resizingDebug" class="rn-debug-drag-cover"></div>
      <div class="column full-height">
        <div class="rn-debug-header row items-center no-wrap">
          <span class="rn-debug-title">Debug</span>
          <span class="q-ml-sm rn-debug-status" :class="debugReady ? 'rn-debug-status--on' : ''">{{ debugStatus }}</span>
          <q-space></q-space>
          <span v-if="info.pid" class="rn-debug-status">pid {{ info.pid }}</span>
        </div>
        <div class="row no-wrap col">
          <div class="rn-tabs col-auto column">
            <div v-for="tab in debugTabs" :key="tab.id"
                 class="rn-tab row items-center no-wrap"
                 :class="activeDebugTab === tab.id ? 'rn-tab--active' : ''"
                 @click="selectDebugTab(tab.id)">
              {{ tab.label }}
            </div>
          </div>
          <div class="rn-detail col relative-position">
            <div v-if="activeDebugTab === 'console'" class="absolute-full column no-wrap">
              <div class="rn-console-bar row items-center no-wrap q-px-sm">
                <span class="rn-action-msg">Python process stdout</span>
                <q-space></q-space>
                <span class="rn-debug-status" :class="debugReady ? 'rn-debug-status--on' : ''">
                  process {{ debugReady ? 'connected' : 'idle' }}
                </span>
              </div>
              <pre ref="consoleEl" class="rn-console col">{{ stdoutText }}</pre>
            </div>

            <div v-else-if="activeDebugTab === 'metrics'" class="absolute-full q-pa-md">
              <div class="row q-col-gutter-lg">
                <div class="col-2"><div class="rn-stat-label">PID</div><div class="rn-stat-value">{{ info.pid || '-' }}</div></div>
                <div class="col-2"><div class="rn-stat-label">CPU</div><div class="rn-stat-value">{{ metrics.cpu_percent.toFixed(1) }}<span class="rn-stat-unit">%</span></div></div>
                <div class="col-2"><div class="rn-stat-label">Memory</div><div class="rn-stat-value">{{ (metrics.rss_bytes / 1024 / 1024).toFixed(0) }}<span class="rn-stat-unit">MB</span></div></div>
                <div class="col-2"><div class="rn-stat-label">Uptime</div><div class="rn-stat-value">{{ Math.round(metrics.uptime_seconds) }}<span class="rn-stat-unit">s</span></div></div>
                <div class="col-2"><div class="rn-stat-label">Threads</div><div class="rn-stat-value">{{ metrics.threads }}</div></div>
                <div class="col-2"><div class="rn-stat-label">FDs</div><div class="rn-stat-value">{{ metrics.fds ?? '-' }}</div></div>
              </div>
              <div class="q-mt-lg rn-action-msg">
                {{ info.llming_stage_version || '?' }} · bundle {{ info.lib_version || '?' }} · python {{ info.python_version || '?' }}
              </div>
            </div>

            <q-scroll-area v-else-if="activeDebugTab === 'threads'" class="absolute-full">
              <div v-for="t in threads" :key="t.ident" class="rn-list-row">
                <span>{{ t.name }}</span><span class="rn-dim"> · {{ t.ident }}</span>
                <div v-if="t.function" class="rn-sub">{{ shortFile(t.file) }}:{{ t.line }} · {{ t.function }}</div>
              </div>
            </q-scroll-area>

            <q-scroll-area v-else-if="activeDebugTab === 'modules'" class="absolute-full">
              <div class="rn-section-header">Browser · llming-stage extensions</div>
              <div v-for="name in Array.from(new Set([...Object.keys(extensions.versions), ...extensions.loaded])).sort()"
                   :key="'js-' + name" class="rn-list-row">
                <span>{{ name }}</span>
                <span v-if="extensions.versions[name]" class="rn-dim"> =={{ extensions.versions[name] }}</span>
                <span v-else class="rn-sub"> · loaded</span>
              </div>
              <div class="rn-section-header">Python · sys.modules</div>
              <div v-for="m in modules" :key="'py-' + m.name" class="rn-list-row">
                <span>{{ m.name }}</span><span v-if="m.version" class="rn-dim"> =={{ m.version }}</span>
              </div>
            </q-scroll-area>

            <div v-else class="absolute-full row no-wrap">
              <div class="rn-sessions-list column">
                <div class="rn-sessions-bar row items-center no-wrap" v-if="sessionsAvailable">
                  <span class="rn-stat-label">{{ sessions.length }} session{{ sessions.length === 1 ? '' : 's' }}</span>
                  <q-space></q-space><span class="rn-live-pill">live</span>
                </div>
                <q-scroll-area class="col">
                  <div v-if="!sessionsAvailable" class="rn-empty">
                    <div class="rn-empty-title">No session API</div>
                    <div class="rn-empty-hint">The target debug endpoint is reachable, but this app has no llming-com session registry.</div>
                  </div>
                  <div v-else-if="!sessions.length" class="rn-empty">
                    <div class="rn-empty-title">Waiting for a session</div>
                    <div class="rn-empty-hint">The attached iframe will create one once the app connects.</div>
                  </div>
                  <div v-for="s in displaySessions" :key="s.session_id"
                       class="rn-session-row"
                       :class="activeSessionId === s.session_id ? 'rn-session-row--active' : ''"
                       @click="openSession(s.session_id, { row: s })">
                    <div class="row items-center no-wrap">
                      <span class="rn-session-id">{{ s.session_id.slice(0, 12) }}</span>
                      <q-space></q-space>
                      <span class="rn-session-flag" :class="s.controller_ready ? 'rn-session-flag--on' : ''">{{ s.controller_ready ? 'ws' : '-' }}</span>
                      <span class="rn-session-flag q-ml-xs" :class="heartbeatClass(s)">{{ heartbeatLabel(s) }}</span>
                    </div>
                    <div class="rn-sub">
                      {{ s.user_id || '' }} <span :class="heartbeatClass(s)">· {{ s.heartbeat_text }}</span>
                    </div>
                  </div>
                </q-scroll-area>
              </div>

              <div class="col column" style="min-width:0; overflow:hidden; position:relative;">
                <div v-if="activeSessionDetail" class="absolute-full column no-wrap">
                  <div class="rn-section-header">{{ activeSessionId }}</div>
                  <div class="rn-session-tabs">
                    <button v-for="tab in sessionTabs" :key="tab.id" type="button"
                            class="rn-session-tab"
                            :class="activeSessionTab === tab.id ? 'rn-session-tab--active' : ''"
                            @click="activeSessionTab = tab.id">{{ tab.label }}</button>
                    <q-space></q-space>
                    <span class="rn-action-msg">{{ selectedSessionActionStatus }}</span>
                  </div>
                  <template v-if="!activeSessionDetail.error">
                    <div v-if="activeSessionTab === 'actions'" class="col column no-wrap">
                      <div class="rn-actions-toolbar row items-center no-wrap">
                        <input v-model="actionSearch" class="rn-actions-search" placeholder="filter actions" />
                        <q-space></q-space>
                        <q-btn flat dense size="sm" label="refresh" @click="requestDebugActions"></q-btn>
                      </div>
                      <q-scroll-area class="col">
                        <div v-if="!bridgeReady" class="rn-empty">
                          <div class="rn-empty-title">Iframe not ready</div>
                          <div class="rn-empty-hint">Reload the preview if the app is still starting.</div>
                        </div>
                        <div v-else-if="!selectedSessionHasActions" class="rn-empty">
                          <div class="rn-empty-title">No actions for this session</div>
                          <div class="rn-empty-hint">Actions are browser-session specific. Select the iframe session.</div>
                        </div>
                        <div v-else-if="!debugActionItems.length" class="rn-empty">
                          <div class="rn-empty-title">No matching actions</div>
                          <div class="rn-empty-hint">No visible debug actions are registered for the current view.</div>
                        </div>
                        <template v-else>
                          <template v-for="group in groupedDebugActions" :key="group.name">
                            <div class="rn-section-header">{{ group.name }}</div>
                            <div class="rn-action-grid">
                              <template v-for="item in group.items" :key="item.id">
                                <button v-if="!(item.presets || []).length" type="button" class="rn-action-tile"
                                        :disabled="debugActionBusy === item.id"
                                        @click="runDebugAction(item)">
                                  <span class="rn-action-tile-title">{{ item.label }}</span>
                                  <span class="rn-action-tile-meta">{{ item.id }}</span>
                                </button>
                                <button v-for="preset in item.presets || []" :key="item.id + ':' + preset.id"
                                        type="button" class="rn-action-tile"
                                        @click="runDebugPreset(item, preset)">
                                  <span class="rn-action-tile-title">{{ preset.label }}</span>
                                  <span class="rn-action-tile-meta">{{ item.label }}</span>
                                </button>
                              </template>
                            </div>
                          </template>
                        </template>
                      </q-scroll-area>
                    </div>
                    <div v-else-if="activeSessionTab === 'js'" class="col column no-wrap">
                      <div class="rn-console-bar row items-center no-wrap q-px-sm">
                        <span class="rn-action-msg">
                          JavaScript console via selected browser session
                        </span>
                        <q-space></q-space>
                        <span class="rn-debug-status" :class="selectedSessionCanEval ? 'rn-debug-status--on' : ''">
                          session {{ selectedSessionCanEval ? 'ready' : 'offline' }}
                        </span>
                      </div>
                      <pre ref="jsConsoleEl" class="rn-console col">{{ jsConsoleText }}</pre>
                      <div class="rn-console-input row items-center no-wrap">
                        <span class="rn-prompt">JS ›</span>
                        <input v-model="jsInput"
                               :disabled="!selectedSessionCanEval"
                               :placeholder="selectedSessionCanEval ? 'expression' : 'select a live session'"
                               @keyup.enter="runJs" />
                        <q-btn flat dense size="sm" label="run"
                               :disable="!selectedSessionCanEval"
                               @click="runJs"></q-btn>
                      </div>
                    </div>
                    <q-scroll-area v-else-if="activeSessionTab === 'state'" class="col">
                      <pre class="rn-state">{{ JSON.stringify(activeSessionDetail.state || {}, null, 2) }}</pre>
                    </q-scroll-area>
                    <q-scroll-area v-else class="col">
                      <div class="rn-kv"><span class="rn-kv-key">user_id</span><span>{{ activeSessionDetail.record?.user_id || '-' }}</span></div>
                      <div class="rn-kv"><span class="rn-kv-key">controller_ready</span><span>{{ activeSessionDetail.record?.controller_ready ? 'yes' : 'no' }}</span></div>
                      <div class="rn-kv"><span class="rn-kv-key">life_sign</span><span>{{ activeSessionDisplay?.record?.heartbeat_text || '-' }}</span></div>
                    </q-scroll-area>
                  </template>
                  <div v-else class="rn-empty">{{ activeSessionDetail.error }}</div>
                </div>
                <div v-else class="absolute-full column items-center justify-center text-grey">
                  <span class="rn-stat-label">select a session</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </q-footer>
  </q-layout>
</div>

<script src="__ASSET_PREFIX__/vendor/vue.global.prod.js"></script>
<script src="__ASSET_PREFIX__/vendor/quasar.umd.prod.js"></script>
<script>
(() => {
  const TARGET = __TARGET_JSON__;
  const DEBUG_TOKEN = __DEBUG_TOKEN_JSON__;
  const { createApp, ref, computed, onMounted, watch, nextTick } = Vue;

  const App = {
    setup() {
      const target = TARGET;
      const frameEl = ref(null);
      const iframeKey = ref(0);
      const dark = ref(localStorage.getItem('inspector-dark') !== 'false');
      const debugDrawer = ref(false);
      const debugHeight = ref(340);
      const resizingDebug = ref(false);
      const activeDebugTab = ref(localStorage.getItem('inspector-debug-tab') || 'sessions');
      const debugTabs = [
        { id: 'console', label: 'Console' },
        { id: 'metrics', label: 'Metrics' },
        { id: 'threads', label: 'Threads' },
        { id: 'modules', label: 'Modules' },
        { id: 'sessions', label: 'Sessions' },
      ];
      const debugReady = ref(false);
      const debugStatus = ref('connecting');
      const bridgeReady = ref(false);
      const info = ref({});
      const metrics = ref({ cpu_percent: 0, rss_bytes: 0, vms_bytes: 0, threads: 0, fds: null, uptime_seconds: 0 });
      const modules = ref([]);
      const threads = ref([]);
      const stdout = ref([]);
      const jsConsole = ref({ sessionId: null, logs: [] });
      const jsInput = ref('');
      const sessions = ref([]);
      const sessionsAvailable = ref(true);
      const activeSessionId = ref(null);
      const activeSessionDetail = ref(null);
      const activeSessionTab = ref('actions');
      const sessionTabs = [
        { id: 'actions', label: 'Actions' },
        { id: 'js', label: 'JS' },
        { id: 'state', label: 'State' },
        { id: 'info', label: 'Info' },
      ];
      const nowTick = ref(Date.now());
      const extensions = ref({ loaded: [], versions: {} });
      const debugActionState = ref({ enabled: false, sessionId: null, currentView: null, actions: [], flows: [] });
      const debugActionBusy = ref(null);
      const actionSearch = ref('');
      const debugActionMessage = ref('');
      const consoleEl = ref(null);
      const jsConsoleEl = ref(null);
      let debugWs = null;
      let metricsTimer = null;
      let consoleTimer = null;
      let sessionsTimer = null;
      let jsConsoleTimer = null;
      let nowTimer = null;
      let nextId = 1;
      let sessionDetailSeq = 1;
      const pending = new Map();

      Quasar.Dark.set(dark.value);

      const iframeSrc = computed(() =>
        '/?__TARGET_QUERY__=1&_inspector_t=' + Date.now() + '&stage_dark=' + (dark.value ? '1' : '0')
      );
      const stdoutText = computed(() => {
        return stdout.value.length
          ? stdout.value.map((line) => '[PY] ' + line).join('\n')
          : '(no Python output captured yet)';
      });
      const jsConsoleText = computed(() => {
        const logs = jsConsole.value.sessionId === activeSessionId.value ? jsConsole.value.logs || [] : [];
        return logs.length
          ? logs.map((e) => e.tag + ' ' + e.text).join('\n')
          : '(no JavaScript output captured yet)';
      });
      const displaySessions = computed(() => {
        nowTick.value;
        return sessions.value.map((s) => ({ ...s, heartbeat_text: heartbeatSeconds(s) }));
      });
      const activeSessionDisplay = computed(() => {
        nowTick.value;
        const detail = activeSessionDetail.value;
        if (!detail || !detail.record) return detail;
        return { ...detail, record: { ...detail.record, heartbeat_text: heartbeatSeconds(detail.record) } };
      });
      const selectedSessionHasActions = computed(() => {
        const state = debugActionState.value || {};
        return !!(state.enabled && state.sessionId && activeSessionId.value && state.sessionId === activeSessionId.value);
      });
      const selectedSessionCanEval = computed(() => {
        const record = activeSessionDetail.value && activeSessionDetail.value.record;
        return !!(activeSessionId.value && record && record.controller_ready);
      });
      const debugActionItems = computed(() => {
        if (!selectedSessionHasActions.value) return [];
        const q = actionSearch.value.trim().toLowerCase();
        const actions = (debugActionState.value.actions || [])
          .filter((item) => item.button !== false)
          .map((item) => ({ ...item, kind: 'action' }));
        return actions.filter((item) => {
          if (!q) return true;
          return [item.id, item.label, item.description, item.scope, item.group, ...(item.tags || [])]
            .filter(Boolean).join(' ').toLowerCase().includes(q);
        });
      });
      const groupedDebugActions = computed(() => {
        const groups = new Map();
        for (const item of debugActionItems.value) {
          const name = (item.scope || 'app') + ' · ' + (item.group || 'General');
          if (!groups.has(name)) groups.set(name, []);
          groups.get(name).push(item);
        }
        return Array.from(groups.entries()).map(([name, items]) => ({ name, items }));
      });
      const selectedSessionActionStatus = computed(() => {
        if (!bridgeReady.value) return 'iframe idle';
        const state = debugActionState.value || {};
        if (!state.enabled) return 'debug actions disabled';
        if (!activeSessionId.value) return 'select a session';
        if (!state.sessionId) return 'session not ready';
        if (state.sessionId !== activeSessionId.value) return 'actions belong to ' + state.sessionId.slice(0, 12);
        return debugActionItems.value.length + ' available';
      });

      const shortFile = (f) => f ? f.split('/').slice(-2).join('/') : '?';
      const pageStyleFn = (offset, height) => ({ height: `${height - offset}px` });
      const heartbeatAgeSeconds = (s) => {
        if (!s || !s.last_heartbeat) return null;
        const ts = s.last_heartbeat < 1e12 ? s.last_heartbeat * 1000 : s.last_heartbeat;
        return Math.max(0, Math.round((nowTick.value - ts) / 1000));
      };
      const heartbeatLabel = (s) => s && s.heartbeat_status === 'alive' ? 'alive' : 'timeout';
      const heartbeatClass = (s) => s && s.heartbeat_status === 'alive'
        ? 'rn-session-flag--on'
        : 'rn-session-flag--timeout rn-heartbeat--timeout';
      const heartbeatSeconds = (s) => {
        if (!s || s.heartbeat_status !== 'alive') return 'timeout';
        const age = heartbeatAgeSeconds(s);
        return age === null ? 'timeout' : 'alive ' + age + 's';
      };
      function scrollConsoleBottom() {
        nextTick(() => {
          const el = consoleEl.value;
          if (el) el.scrollTop = el.scrollHeight;
        });
      }
      function scrollJsConsoleBottom() {
        nextTick(() => {
          const el = jsConsoleEl.value;
          if (el) el.scrollTop = el.scrollHeight;
        });
      }
      function frameWindow() {
        return frameEl.value && frameEl.value.contentWindow;
      }
      function onFrameLoad() {
        bridgeReady.value = false;
        debugActionState.value = { enabled: false, sessionId: null, currentView: null, actions: [], flows: [] };
        setTimeout(() => {
          const win = frameWindow();
          bridgeReady.value = !!(win && win.__stage);
          requestDebugActions();
          refreshExtensions();
          if (debugDrawer.value && activeDebugTab.value === 'sessions') fetchSessions();
        }, 100);
      }
      function requestDebugActions() {
        const win = frameWindow();
        const debug = win && win.__stage && win.__stage.debug;
        if (!debug || !debug.snapshot) {
          debugActionState.value = { enabled: false, sessionId: null, currentView: null, actions: [], flows: [] };
          return Promise.resolve(debugActionState.value);
        }
        return Promise.resolve(debug.snapshot()).then((snapshot) => {
          debugActionState.value = snapshot || debugActionState.value;
          return debugActionState.value;
        }).catch((e) => {
          debugActionMessage.value = e.message || String(e);
        });
      }
      function refreshExtensions() {
        const win = frameWindow();
        if (!win) return;
        const versions = {};
        if (win.Vue) versions.vue = win.Vue.version;
        if (win.Quasar) versions.quasar = win.Quasar.version;
        if (win.echarts) versions.echarts = win.echarts.version;
        if (win.Plotly) versions.plotly = win.Plotly.version;
        if (win.THREE) versions.three = 'r' + win.THREE.REVISION;
        if (win.mermaid) versions.mermaid = win.mermaid.version;
        extensions.value = {
          loaded: win.__stage && win.__stage.loaded ? Array.from(win.__stage.loaded) : [],
          versions,
        };
      }
      function runDebugAction(item) {
        return runDebugRequest({ kind: 'action', id: item.id, params: {}, source: 'inspector' }, item.id);
      }
      function runDebugPreset(item, preset) {
        return runDebugRequest({ kind: 'preset', id: item.id + ':' + preset.id, source: 'inspector' }, item.id + ':' + preset.id);
      }
      function runDebugRequest(request, busyId) {
        const win = frameWindow();
        const debug = win && win.__stage && win.__stage.debug;
        if (!debug || !debug.runRequest) return;
        debugActionBusy.value = busyId;
        debugActionMessage.value = '';
        Promise.resolve(debug.runRequest(request)).then(() => {
          debugActionMessage.value = 'ran ' + request.id;
          return requestDebugActions();
        }).catch((e) => {
          debugActionMessage.value = e.message || String(e);
        }).finally(() => {
          debugActionBusy.value = null;
        });
      }
      async function fetchJsConsole() {
        if (!activeSessionId.value || activeSessionTab.value !== 'js') return;
        try {
          const r = await sendQ('js_console_tail', { session_id: activeSessionId.value, n: 500 });
          jsConsole.value = { sessionId: activeSessionId.value, logs: (r.data && r.data.logs) || [] };
          scrollJsConsoleBottom();
        } catch (_) {}
      }
      async function runJs() {
        const code = jsInput.value.trim();
        if (!code) return;
        if (!selectedSessionCanEval.value) return;
        jsInput.value = '';
        try {
          const r = await sendQ('js_eval', { session_id: activeSessionId.value, code });
          jsConsole.value = { sessionId: activeSessionId.value, logs: (r.data && r.data.logs) || [] };
        } catch (e) {
          const logs = jsConsole.value.sessionId === activeSessionId.value ? jsConsole.value.logs.slice() : [];
          logs.push({ tag: 'x', text: String(e && e.message || e) });
          jsConsole.value = { sessionId: activeSessionId.value, logs };
        }
        scrollJsConsoleBottom();
      }
      function sendQ(q, args) {
        return new Promise((resolve, reject) => {
          if (!debugWs || debugWs.readyState !== WebSocket.OPEN) {
            reject(new Error('debug WS not connected'));
            return;
          }
          const id = nextId++;
          pending.set(id, { resolve, reject });
          debugWs.send(JSON.stringify({ id, q, args: args || {} }));
        });
      }
      async function fetchInfo() { try { info.value = (await sendQ('info')).data || {}; } catch (_) {} }
      async function pollMetrics() { try { metrics.value = (await sendQ('metrics')).data || metrics.value; } catch (_) {} }
      async function fetchModules() { try { modules.value = (await sendQ('modules')).data || []; } catch (_) {} }
      async function fetchThreads() { try { threads.value = (await sendQ('threads')).data || []; } catch (_) {} }
      async function fetchStdout() {
        try {
          stdout.value = (await sendQ('stdout_tail', { n: 300 })).data || [];
          if (activeDebugTab.value === 'console') scrollConsoleBottom();
        } catch (_) {}
      }
      async function fetchSessions() {
        try {
          const r = await sendQ('sessions');
          sessionsAvailable.value = !!(r.data && r.data.available);
          sessions.value = (r.data && r.data.sessions) || [];
          if (!activeSessionId.value && sessions.value.length === 1) {
            await openSession(sessions.value[0].session_id, { row: sessions.value[0] });
            return;
          }
          if (activeSessionId.value) {
            const still = sessions.value.find((s) => s.session_id === activeSessionId.value);
            if (!still) { activeSessionId.value = null; activeSessionDetail.value = null; }
            else await openSession(activeSessionId.value, { row: still, refresh: true });
          }
        } catch (_) {}
      }
      async function openSession(sid, options = {}) {
        const row = options.row || sessions.value.find((s) => s.session_id === sid) || null;
        const seq = sessionDetailSeq++;
        activeSessionId.value = sid;
        if (!options.refresh || !activeSessionDetail.value) {
          activeSessionDetail.value = row ? { record: row, state: {}, loading: true } : { record: { session_id: sid }, state: {}, loading: true };
        }
        try {
          const r = await sendQ('session_state', { session_id: sid });
          if (seq !== sessionDetailSeq - 1 || activeSessionId.value !== sid) return;
          activeSessionDetail.value = r.data || null;
        } catch (_) {
          if (activeSessionId.value === sid) activeSessionDetail.value = { error: 'fetch failed' };
        }
        requestDebugActions();
      }
      function applyTabPolling() {
        if (metricsTimer) { clearInterval(metricsTimer); metricsTimer = null; }
        if (consoleTimer) { clearInterval(consoleTimer); consoleTimer = null; }
        if (sessionsTimer) { clearInterval(sessionsTimer); sessionsTimer = null; }
        if (jsConsoleTimer) { clearInterval(jsConsoleTimer); jsConsoleTimer = null; }
        if (!debugReady.value || !debugDrawer.value) return;
        if (activeDebugTab.value === 'metrics') { pollMetrics(); metricsTimer = setInterval(pollMetrics, 1000); }
        if (activeDebugTab.value === 'console') { fetchStdout(); consoleTimer = setInterval(fetchStdout, 1000); }
        if (activeDebugTab.value === 'sessions') { fetchSessions(); sessionsTimer = setInterval(fetchSessions, 1000); }
        if (activeDebugTab.value === 'sessions' && activeSessionTab.value === 'js') {
          fetchJsConsole();
          jsConsoleTimer = setInterval(fetchJsConsole, 1000);
        }
      }
      function selectDebugTab(tabId) {
        activeDebugTab.value = tabId;
        localStorage.setItem('inspector-debug-tab', tabId);
        if (tabId === 'threads') fetchThreads();
        if (tabId === 'modules') { fetchModules(); refreshExtensions(); }
        if (tabId === 'sessions') { fetchSessions(); requestDebugActions(); }
        if (tabId === 'console') scrollConsoleBottom();
        applyTabPolling();
      }
      function connectDebug() {
        const token = encodeURIComponent(DEBUG_TOKEN || '');
        const wsScheme = location.protocol === 'https:' ? 'wss' : 'ws';
        const ws = new WebSocket(`${wsScheme}://${location.host}/_stage/debug/ws?token=${token}`);
        debugWs = ws;
        ws.onopen = () => {
          debugReady.value = true;
          debugStatus.value = 'connected';
          nowTimer = setInterval(() => { nowTick.value = Date.now(); }, 1000);
          fetchInfo();
          applyTabPolling();
        };
        ws.onmessage = (ev) => {
          let msg;
          try { msg = JSON.parse(ev.data); } catch (_) { return; }
          if (msg.id != null && pending.has(msg.id)) {
            const p = pending.get(msg.id);
            pending.delete(msg.id);
            if (msg.ok) p.resolve(msg);
            else p.reject(new Error(msg.error || 'query failed'));
          }
        };
        ws.onerror = () => { debugStatus.value = DEBUG_TOKEN ? 'unavailable' : 'missing token'; };
        ws.onclose = () => {
          debugReady.value = false;
          if (debugStatus.value === 'connected') debugStatus.value = 'closed';
          if (metricsTimer) clearInterval(metricsTimer);
          if (consoleTimer) clearInterval(consoleTimer);
          if (sessionsTimer) clearInterval(sessionsTimer);
          if (jsConsoleTimer) clearInterval(jsConsoleTimer);
          if (nowTimer) clearInterval(nowTimer);
        };
      }
      function toggleDebugDrawer() {
        debugDrawer.value = !debugDrawer.value;
        localStorage.setItem('inspector-debug-drawer', String(debugDrawer.value));
        applyTabPolling();
      }
      function startDebugResize(ev) {
        ev.preventDefault();
        resizingDebug.value = true;
        const startY = ev.clientY;
        const startHeight = debugHeight.value;
        const maxHeight = Math.max(260, window.innerHeight - 120);
        const move = (moveEv) => {
          debugHeight.value = Math.round(Math.max(220, Math.min(maxHeight, startHeight + startY - moveEv.clientY)));
        };
        const up = () => {
          resizingDebug.value = false;
          window.removeEventListener('pointermove', move);
          window.removeEventListener('pointerup', up);
          window.removeEventListener('pointercancel', up);
          localStorage.setItem('inspector-debug-height', String(debugHeight.value));
        };
        window.addEventListener('pointermove', move);
        window.addEventListener('pointerup', up);
        window.addEventListener('pointercancel', up);
      }
      function reload() { iframeKey.value += 1; }
      function openTarget() { window.open(TARGET + '/', '_blank', 'noopener'); }
      function toggleDark() {
        dark.value = !dark.value;
        Quasar.Dark.set(dark.value);
        localStorage.setItem('inspector-dark', String(dark.value));
        reload();
      }
      watch(debugDrawer, applyTabPolling);
      watch(activeSessionTab, applyTabPolling);
      watch(activeSessionId, () => {
        if (activeSessionTab.value === 'js') fetchJsConsole();
      });
      onMounted(() => {
        debugDrawer.value = localStorage.getItem('inspector-debug-drawer') === 'true';
        debugHeight.value = Number(localStorage.getItem('inspector-debug-height') || 340) || 340;
        connectDebug();
      });
      return {
        target, frameEl, iframeKey, iframeSrc, onFrameLoad, pageStyleFn,
        dark, toggleDark, reload, openTarget,
        debugDrawer, toggleDebugDrawer, debugHeight, resizingDebug, startDebugResize,
        debugReady, debugStatus, bridgeReady, debugTabs, activeDebugTab, selectDebugTab,
        info, metrics, modules, threads, stdoutText, consoleEl, jsConsoleEl,
        jsConsoleText, jsInput, runJs, shortFile,
        sessionsAvailable, sessions, displaySessions, activeSessionId, activeSessionDetail,
        activeSessionTab, sessionTabs, activeSessionDisplay, heartbeatLabel, heartbeatClass,
        debugActionState, debugActionItems, groupedDebugActions, actionSearch,
        selectedSessionHasActions, selectedSessionCanEval, selectedSessionActionStatus, debugActionBusy,
        debugActionMessage, requestDebugActions, runDebugAction, runDebugPreset,
        extensions, openSession,
      };
    },
  };
  createApp(App).use(Quasar).mount('#app');
})();
</script>
</body>
</html>
"""
