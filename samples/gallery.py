"""Web gallery for the llming-stage samples.

Runs on http://localhost:8000 with a sample list on the left and an
iframe on the right. Clicking a sample kills the previous subprocess
and spawns the selected one on port 8765; the iframe then loads it.

Env overrides:
    GALLERY_PORT  — port for the gallery itself (default 8000)
    SAMPLE_PORT   — port each sample is launched on   (default 8765)
"""

from __future__ import annotations

import asyncio
import base64
import os
import signal
import socket
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from llming_stage import mount_assets

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def _logo_data_url() -> str:
    """Inline-embed the runner toolbar icon as a base64 data URL.

    Cheap (the icon is ~10 KB) and keeps the gallery a single-file HTML
    response — no extra static route needed.
    """
    path = REPO / "media" / "logo-icon.png"
    if not path.is_file():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


_LOGO_DATA_URL = _logo_data_url()


def _pick_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


GALLERY_PORT = int(os.environ.get("GALLERY_PORT", "8000"))
SAMPLE_PORT = int(os.environ.get("SAMPLE_PORT", "8765"))


def discover() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for p in sorted(HERE.iterdir()):
        if not _is_sample_dir(p):
            continue
        items.append({"name": p.name, "hint": _readme_hint(p / "README.md")})
    return items


def _is_sample_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    if (path / "main.py").is_file():
        return True
    return any(
        p.is_file() and p.suffix.lower() in {".vue", ".html", ".htm", ".js"}
        for p in path.iterdir()
    )


def _readme_hint(readme: Path) -> str:
    if not readme.is_file():
        return ""
    body: list[str] = []
    for i, line in enumerate(readme.read_text().splitlines()):
        s = line.strip()
        if i == 0 and s.startswith("#"):
            continue
        if s.startswith("#"):
            break
        if s:
            body.append(s)
        elif body:
            break
    return " ".join(body)[:120]


def _port_open(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(0.3)
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


class SampleRunner:
    """Owns at most one running sample subprocess.

    ``start(name)`` is idempotent: selecting the already-running sample
    is a no-op. Switching samples terminates the previous process,
    waits for its port to free up, and spawns the new one.
    """

    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.current: str | None = None
        self._lock = asyncio.Lock()

    async def start(self, name: str) -> None:
        async with self._lock:
            if self.current == name and self.proc and self.proc.poll() is None:
                return
            await self._stop_unlocked()
            main_py = HERE / name / "main.py"
            sample_dir = HERE / name
            if not _is_sample_dir(sample_dir):
                raise FileNotFoundError(name)
            env = {**os.environ, "PORT": str(SAMPLE_PORT)}
            command = (
                [sys.executable, str(main_py)]
                if main_py.is_file()
                else [
                    sys.executable,
                    "-m",
                    "llming_stage.cli",
                    "serve",
                    str(sample_dir),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(SAMPLE_PORT),
                ]
            )
            # Give the sample its own process group so reload supervisors
            # AND their workers can all be signalled together on stop.
            self.proc = subprocess.Popen(
                command,
                env=env,
                cwd=str(REPO),
                start_new_session=True,
            )
            self.current = name
            for _ in range(150):   # up to 15s
                if _port_open(SAMPLE_PORT):
                    return
                if self.proc.poll() is not None:
                    self.proc = None
                    self.current = None
                    raise RuntimeError(f"{name} exited during startup")
                await asyncio.sleep(0.1)
            raise TimeoutError(f"{name} did not open :{SAMPLE_PORT}")

    async def stop(self) -> None:
        async with self._lock:
            await self._stop_unlocked()

    async def _stop_unlocked(self) -> None:
        if self.proc is None:
            return
        try:
            _signal_group(self.proc, signal.SIGTERM)
            for _ in range(100):
                if self.proc.poll() is not None:
                    break
                await asyncio.sleep(0.1)
            if self.proc.poll() is None:
                _signal_group(self.proc, signal.SIGKILL)
                self.proc.wait(timeout=5)
        finally:
            self.proc = None
            self.current = None
            for _ in range(50):
                if not _port_open(SAMPLE_PORT):
                    break
                await asyncio.sleep(0.1)


def _signal_group(proc: subprocess.Popen, sig: int) -> None:
    """Send *sig* to the entire process group of *proc*.

    Reload supervisors spawn worker children; killing only the parent
    PID leaves the worker orphaned and the port still bound. By
    starting each sample in its own session (``start_new_session``)
    we can signal the whole group.
    """
    try:
        os.killpg(os.getpgid(proc.pid), sig)
    except ProcessLookupError:
        pass


runner = SampleRunner()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await runner.stop()


app = FastAPI(lifespan=lifespan)
# Mount llming-stage's vendor assets so the gallery UI can pull Vue +
# Quasar + Material Icons from /_stage/… — same pipeline the samples use.
mount_assets(app)


@app.get("/api/samples")
async def list_samples() -> dict:
    return {
        "samples": discover(),
        "current": runner.current,
        "sample_port": SAMPLE_PORT,
    }


@app.post("/api/switch/{name}")
async def switch(name: str) -> dict:
    valid = {s["name"] for s in discover()}
    if name not in valid:
        raise HTTPException(404, f"unknown sample: {name}")
    try:
        await runner.start(name)
    except (TimeoutError, RuntimeError) as exc:
        raise HTTPException(500, str(exc))
    return {"current": runner.current}


@app.post("/api/stop")
async def stop() -> dict:
    await runner.stop()
    return {"current": None}


@app.get("/")
async def index() -> HTMLResponse:
    body = (
        _INDEX_HTML
        .replace("__SAMPLE_PORT__", str(SAMPLE_PORT))
        .replace("__LOGO_DATA_URL__", _LOGO_DATA_URL)
    )
    return HTMLResponse(body)


_INDEX_HTML = r"""<!doctype html>
<html lang="en" class="full-height">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>llming-stage runner</title>
<link rel="stylesheet" href="/_stage/fonts/fonts.css">
<link rel="stylesheet" href="/_stage/vendor/quasar.prod.css">
<style>
  /* ------------------------------------------------------------------
     Runner UI theme. Dark slate chrome around the sample iframe, with
     Roboto everywhere except actual code blocks. All colors scoped via
     CSS variables so retheming later is a one-line change.
     ------------------------------------------------------------------ */
  :root {
    --rn-bg:       #0b1220;   /* deepest chrome */
    --rn-surface:  #111a2c;   /* drawer, footer panels */
    --rn-surface2: #18243a;   /* hover / active card */
    --rn-border:   rgba(255, 255, 255, 0.06);
    --rn-text:     #e2e8f0;   /* slate-200 */
    --rn-text-dim: #94a3b8;   /* slate-400 */
    --rn-text-mut: #64748b;   /* slate-500 */
    --rn-accent:   #6366f1;   /* indigo-500 */
    --rn-positive: #10b981;
    --rn-mono:     ui-monospace, "SF Mono", "JetBrains Mono", "Roboto Mono", Menlo, Consolas, monospace;
  }
  html, body, #app, .q-layout {
    font-family: "Roboto", system-ui, -apple-system, "Segoe UI", sans-serif;
    background: var(--rn-bg);
    color: var(--rn-text);
  }
  /* Runner chrome is *UI*, not document content — disable text-select
     and force the pointer cursor on every interactive surface. Only the
     iframe and the console/state code blocks remain selectable. */
  .rn-header, .rn-drawer, .rn-debug, .rn-tabs, .rn-console-bar {
    user-select: none;
    -webkit-user-select: none;
  }
  .rn-tab, .rn-mode, .rn-session-row { cursor: pointer; }

  /* Header --------------------------------------------------------- */
  .rn-header {
    background: var(--rn-surface) !important;
    border-bottom: 1px solid var(--rn-border);
    box-shadow: none !important;
  }
  .rn-header .q-toolbar { min-height: 56px; padding: 0 14px; gap: 6px; }
  .rn-header .q-toolbar__title { padding: 0; }
  .rn-title { display: flex; flex-direction: column; line-height: 1.15; }
  .rn-title-main {
    font-size: 17px;
    font-weight: 600;
    letter-spacing: 0.005em;
    color: var(--rn-text);
  }
  .rn-title-sub {
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.12em;
    color: var(--rn-text-mut);
    text-transform: uppercase;
    margin-top: 2px;
  }
  .rn-logo {
    width: 34px;
    height: 34px;
    margin: 0 10px 0 4px;
    border-radius: 7px;
    object-fit: cover;
    flex: 0 0 auto;
    box-shadow: 0 0 0 1px var(--rn-border);
    background: var(--rn-surface2);
  }
  .rn-header .rn-current {
    display: inline-flex;
    align-items: center;
    height: 24px;
    padding: 0 10px;
    margin-left: 14px;
    border-radius: 6px;
    background: var(--rn-surface2);
    color: var(--rn-text);
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0;
  }
  .rn-header .q-btn {
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--rn-text-dim);
    min-height: 32px;
    padding: 0 10px;
  }
  .rn-header .q-btn:hover { color: var(--rn-text); }
  .rn-header .q-btn--round { padding: 0; min-height: 32px; min-width: 32px; }

  /* Left drawer (sample list) ------------------------------------- */
  .rn-drawer { background: var(--rn-surface) !important; }
  .rn-drawer .q-item-label--header {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.12em;
    color: var(--rn-text-mut);
    padding: 14px 16px 6px;
    text-transform: uppercase;
  }
  .rn-drawer .q-item {
    min-height: 50px;
    padding: 8px 14px;
    border-left: 2px solid transparent;
    color: var(--rn-text-dim);
    transition: background 80ms, color 80ms, border-color 80ms;
  }
  .rn-drawer .q-item:hover { background: rgba(255,255,255,0.025); color: var(--rn-text); }
  .rn-drawer .q-item--active,
  .rn-drawer .q-item--active:hover {
    background: var(--rn-surface2) !important;
    border-left-color: var(--rn-accent);
    color: var(--rn-text) !important;
  }
  .rn-drawer .rn-sample-name {
    font-size: 13px;
    font-weight: 500;
    color: inherit;
    letter-spacing: 0;
  }
  .rn-drawer .rn-sample-hint {
    font-size: 11px;
    color: var(--rn-text-mut);
    line-height: 1.4;
    margin-top: 2px;
  }

  /* Debug footer pane --------------------------------------------- */
  .rn-debug {
    background: var(--rn-bg) !important;
    border-top: 1px solid var(--rn-border);
    box-shadow: none !important;
    color: var(--rn-text);
  }
  .rn-debug-header {
    background: var(--rn-surface);
    border-bottom: 1px solid var(--rn-border);
    padding: 8px 12px;
    height: 36px;
    flex: 0 0 auto;
  }
  .rn-debug-header .rn-debug-title {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.16em;
    color: var(--rn-text-dim);
    text-transform: uppercase;
  }
  .rn-debug-status {
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.04em;
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--rn-surface2);
    color: var(--rn-text-dim);
  }
  .rn-debug-status--on { background: rgba(16,185,129,0.15); color: var(--rn-positive); }
  .rn-tabs {
    background: var(--rn-surface);
    border-right: 1px solid var(--rn-border);
  }
  .rn-tab {
    min-height: 36px;
    padding: 0 16px;
    color: var(--rn-text-dim);
    font-size: 12px;
    letter-spacing: 0.02em;
    border-left: 2px solid transparent;
    transition: background 80ms, color 80ms, border-color 80ms;
  }
  .rn-tab:hover { background: rgba(255,255,255,0.025); color: var(--rn-text); }
  .rn-tab--active,
  .rn-tab--active:hover {
    background: var(--rn-surface2);
    border-left-color: var(--rn-accent);
    color: var(--rn-text);
  }
  .rn-detail { background: var(--rn-bg); }
  .rn-console {
    margin: 0;
    padding: 12px 14px;
    font-family: var(--rn-mono);
    font-size: 12px;
    line-height: 1.5;
    color: #cbd5e1;
    background: #050912;
    white-space: pre;
    overflow: auto;
  }
  .rn-stat-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.12em;
    color: var(--rn-text-mut);
    text-transform: uppercase;
  }
  .rn-stat-value {
    font-family: var(--rn-mono);
    font-size: 20px;
    font-weight: 500;
    color: var(--rn-text);
    line-height: 1.2;
    margin-top: 2px;
  }
  .rn-stat-unit { font-size: 11px; color: var(--rn-text-mut); margin-left: 2px; }
  .rn-runtime-line { font-family: var(--rn-mono); font-size: 12px; color: var(--rn-text); margin-top: 2px; }
  .rn-list-row {
    font-family: var(--rn-mono);
    font-size: 12px;
    padding: 4px 14px;
    color: var(--rn-text);
    border-bottom: 1px solid var(--rn-border);
  }
  .rn-list-row .rn-dim { color: var(--rn-text-mut); }
  .rn-list-row .rn-sub { color: var(--rn-text-dim); font-size: 11px; }
  .rn-section-header {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.12em;
    color: var(--rn-text-mut);
    text-transform: uppercase;
    padding: 10px 14px 4px;
    background: var(--rn-surface);
    border-bottom: 1px solid var(--rn-border);
    position: sticky; top: 0; z-index: 1;
  }

  /* Console toolbar + JS REPL */
  .rn-console-bar {
    background: var(--rn-surface);
    border-bottom: 1px solid var(--rn-border);
    padding: 6px 10px;
    flex: 0 0 auto;
    gap: 8px;
  }
  .rn-mode-group {
    display: inline-flex;
    border-radius: 999px;
    background: var(--rn-bg);
    padding: 2px;
    border: 1px solid var(--rn-border);
  }
  .rn-mode {
    background: transparent;
    border: none;
    color: var(--rn-text-dim);
    font: 500 11px/1 "Roboto", sans-serif;
    letter-spacing: 0.04em;
    padding: 4px 12px;
    border-radius: 999px;
    cursor: pointer;
  }
  .rn-mode:hover { color: var(--rn-text); }
  .rn-mode--on { background: var(--rn-surface2); color: var(--rn-text); }
  .rn-bridge-pill {
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.04em;
    color: var(--rn-text-mut);
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--rn-surface2);
  }
  .rn-bridge-pill--on {
    background: rgba(99,102,241,0.18);
    color: #c7d2fe;
  }
  .rn-console-input {
    background: var(--rn-surface);
    border-top: 1px solid var(--rn-border);
    flex: 0 0 auto;
    padding: 0 10px;
  }
  .rn-console-input .rn-prompt {
    font-family: var(--rn-mono);
    color: #818cf8;
    padding: 0 6px 0 2px;
    font-size: 12px;
  }
  .rn-console-input input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    color: var(--rn-text);
    font-family: var(--rn-mono);
    font-size: 12px;
    padding: 8px 0;
  }
  .rn-console-input input:disabled { color: var(--rn-text-mut); }
  .rn-console-input .q-btn {
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.06em;
    color: var(--rn-text-dim);
    min-height: 24px;
    padding: 0 8px;
  }

  /* Sessions */
  .rn-sessions-bar {
    height: 30px;
    padding: 0 12px;
    background: var(--rn-surface);
    border-bottom: 1px solid var(--rn-border);
    flex: 0 0 auto;
  }
  .rn-live-pill {
    display: inline-flex; align-items: center;
    gap: 6px;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--rn-positive);
    background: rgba(16,185,129,0.12);
    padding: 2px 8px;
    border-radius: 999px;
  }
  .rn-live-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--rn-positive);
    box-shadow: 0 0 0 0 rgba(16,185,129,0.6);
    animation: rn-pulse 1.4s ease-out infinite;
  }
  @keyframes rn-pulse {
    0%   { box-shadow: 0 0 0 0   rgba(16,185,129,0.55); }
    70%  { box-shadow: 0 0 0 6px rgba(16,185,129,0);    }
    100% { box-shadow: 0 0 0 0   rgba(16,185,129,0);    }
  }
  .rn-session-row {
    padding: 8px 12px;
    border-bottom: 1px solid var(--rn-border);
    cursor: pointer;
    color: var(--rn-text);
    transition: background 80ms;
  }
  .rn-session-row:hover { background: rgba(255,255,255,0.025); }
  .rn-session-row--active,
  .rn-session-row--active:hover {
    background: var(--rn-surface2);
    border-left: 2px solid var(--rn-accent);
    padding-left: 10px;
  }
  .rn-session-id {
    font-family: var(--rn-mono);
    font-size: 12px;
    color: var(--rn-text);
  }
  .rn-session-flag {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.08em;
    color: var(--rn-text-mut);
    padding: 1px 6px;
    border-radius: 4px;
    background: var(--rn-bg);
  }
  .rn-session-flag--on {
    color: var(--rn-positive);
    background: rgba(16,185,129,0.12);
  }
  .rn-kv {
    display: flex;
    padding: 4px 14px;
    font-family: var(--rn-mono);
    font-size: 12px;
    color: var(--rn-text);
    gap: 12px;
  }
  .rn-kv-key {
    width: 140px;
    color: var(--rn-text-mut);
  }
  .rn-state {
    margin: 0;
    padding: 8px 14px;
    font-family: var(--rn-mono);
    font-size: 11px;
    color: var(--rn-text);
    background: var(--rn-bg);
    white-space: pre;
    overflow: auto;
  }
  .rn-empty { padding: 16px 18px; }
  .rn-empty-title {
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--rn-text);
  }
  .rn-empty-hint {
    font-size: 12px;
    color: var(--rn-text-dim);
    margin-top: 6px;
    line-height: 1.5;
  }
  .rn-empty-hint code {
    font-family: var(--rn-mono);
    font-size: 11px;
    background: var(--rn-surface);
    padding: 1px 5px;
    border-radius: 4px;
    color: var(--rn-text);
  }
</style>
</head>
<body class="full-height no-margin rn-body">
<div id="app" class="full-height">
  <q-layout view="hHh Lpr fFf">
    <q-header class="rn-header">
      <q-toolbar>
        <q-btn flat dense round icon="menu" aria-label="toggle sidebar" @click="drawer = !drawer"></q-btn>
        <img v-if="logoUrl" :src="logoUrl" class="rn-logo" alt="llming-stage" />
        <q-toolbar-title class="row items-center no-wrap">
          <div class="rn-title">
            <span class="rn-title-main">llming-stage</span>
            <span class="rn-title-sub">Sample Gallery</span>
          </div>
          <span v-if="current" class="rn-current" :data-test="'current'">{{ current }}</span>
        </q-toolbar-title>
        <q-btn flat dense icon="refresh" label="reload" :disable="!current || busy"
               @click="reload" data-test="btn-reload"></q-btn>
        <q-btn flat dense icon="open_in_new" label="open" :disable="!current || busy"
               @click="popout" data-test="btn-popout"></q-btn>
        <q-btn flat dense icon="stop" label="stop" :disable="!current || busy"
               @click="stop" data-test="btn-stop"></q-btn>
        <q-btn v-if="debugAvailable" flat dense round icon="bug_report"
               aria-label="toggle debug panel"
               :style="debugDrawer ? { color: 'var(--rn-positive)' } : {}"
               @click="debugDrawer = !debugDrawer" data-test="btn-debug">
          <q-tooltip>Debug pane ({{ debugStatus }})</q-tooltip>
        </q-btn>
        <q-btn flat dense round :icon="dark ? 'light_mode' : 'dark_mode'"
               :aria-label="dark ? 'switch to light mode' : 'switch to dark mode'"
               @click="toggleDark" data-test="btn-dark"></q-btn>
      </q-toolbar>
    </q-header>

    <q-drawer v-model="drawer" :width="280" show-if-above bordered side="left" class="rn-drawer">
      <q-scroll-area class="fit">
        <q-list>
          <q-item-label header>SAMPLES</q-item-label>
          <q-item v-for="s in samples" :key="s.name" clickable v-ripple
                  :active="s.name === current"
                  active-class="q-item--active"
                  @click="pick(s.name)" :data-sample="s.name">
            <q-item-section>
              <q-item-label class="rn-sample-name">{{ s.name }}</q-item-label>
              <q-item-label class="rn-sample-hint" lines="2">{{ s.hint }}</q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
      </q-scroll-area>
    </q-drawer>


    <q-page-container>
      <q-page class="column no-padding overflow-hidden" :style-fn="pageStyleFn">
        <q-banner v-if="error" dense class="bg-negative text-white">
          <template v-slot:avatar><q-icon name="error" /></template>
          {{ error }}
        </q-banner>
        <div class="col relative-position">
          <iframe v-if="iframeSrc" :src="iframeSrc" class="absolute-full full-width full-height no-border transparent"
                  id="frame" data-test="frame"></iframe>
          <div v-else-if="busy" class="absolute-full column items-center justify-center text-center q-pa-lg q-gutter-sm">
            <q-spinner color="primary" size="32px"></q-spinner>
            <div class="text-grey">{{ status }}</div>
          </div>
          <div v-else class="absolute-full column items-center justify-center text-center q-pa-lg text-grey">
            Pick a sample on the left to launch it.
          </div>
        </div>
      </q-page>
    </q-page-container>

    <q-footer v-if="debugAvailable && debugDrawer" class="rn-debug" style="height: 280px">
      <div class="column full-height">
        <div class="rn-debug-header row items-center no-wrap">
          <span class="rn-debug-title">Debug</span>
          <span class="q-ml-sm rn-debug-status"
                :class="debugReady ? 'rn-debug-status--on' : ''">
            {{ debugStatus }}
          </span>
          <q-space />
          <span v-if="info.pid" class="rn-debug-status">pid {{ info.pid }}</span>
        </div>
        <div class="row no-wrap col">
          <div class="rn-tabs col-auto column" style="width: 160px; min-width: 160px;">
            <div v-for="tab in debugTabs" :key="tab.id"
                 class="rn-tab row items-center no-wrap"
                 :class="activeDebugTab === tab.id ? 'rn-tab--active' : ''"
                 @click="selectDebugTab(tab.id)">
              <span>{{ tab.label }}</span>
            </div>
          </div>

          <div class="rn-detail col relative-position">
            <!-- Console: streaming Python stdout + iframe JS console + REPL -->
            <div v-if="activeDebugTab === 'console'" class="absolute-full column no-wrap">
              <div class="rn-console-bar row items-center no-wrap">
                <div class="rn-mode-group row no-wrap">
                  <button class="rn-mode" :class="consoleMode === 'both' ? 'rn-mode--on' : ''"
                          @click="consoleMode = 'both'">Both</button>
                  <button class="rn-mode" :class="consoleMode === 'py' ? 'rn-mode--on' : ''"
                          @click="consoleMode = 'py'">PY</button>
                  <button class="rn-mode" :class="consoleMode === 'js' ? 'rn-mode--on' : ''"
                          @click="consoleMode = 'js'">JS</button>
                </div>
                <q-space />
                <span class="rn-bridge-pill" :class="bridgeReady ? 'rn-bridge-pill--on' : ''">
                  JS bridge {{ bridgeReady ? 'ready' : 'idle' }}
                </span>
              </div>
              <pre ref="consoleEl" class="rn-console col">{{ stdoutText }}</pre>
              <div class="rn-console-input row items-center no-wrap">
                <span class="rn-prompt">JS&nbsp;›</span>
                <input v-model="jsInput"
                       :disabled="!bridgeReady"
                       :placeholder="bridgeReady ? 'expression — Enter to run, ↑/↓ for history' : 'JS bridge not active'"
                       @keyup.enter="runJs"
                       @keydown="jsInputKey" />
                <q-btn flat dense size="sm" label="run"
                       :disable="!bridgeReady"
                       @click="runJs"></q-btn>
              </div>
            </div>

            <!-- Metrics: compact stats grid -->
            <div v-else-if="activeDebugTab === 'metrics'"
                 class="absolute-full" style="padding: 16px 18px;">
              <div class="row q-col-gutter-lg">
                <div class="col-3">
                  <div class="rn-stat-label">CPU</div>
                  <div class="rn-stat-value">{{ metrics.cpu_percent.toFixed(1) }}<span class="rn-stat-unit">%</span></div>
                </div>
                <div class="col-3">
                  <div class="rn-stat-label">Memory</div>
                  <div class="rn-stat-value">{{ (metrics.rss_bytes / 1024 / 1024).toFixed(0) }}<span class="rn-stat-unit">MB</span></div>
                </div>
                <div class="col-3">
                  <div class="rn-stat-label">Uptime</div>
                  <div class="rn-stat-value">{{ Math.round(metrics.uptime_seconds) }}<span class="rn-stat-unit">s</span></div>
                </div>
                <div class="col-3">
                  <div class="rn-stat-label">Threads · FDs</div>
                  <div class="rn-stat-value">{{ metrics.threads }} <span class="rn-stat-unit">·</span> {{ metrics.fds ?? '?' }}</div>
                </div>
              </div>
              <div class="q-mt-lg">
                <div class="rn-stat-label">Runtime</div>
                <div class="rn-runtime-line">
                  {{ info.llming_stage_version || '?' }} · bundle {{ info.lib_version || '?' }} · python {{ info.python_version || '?' }}
                </div>
                <div class="rn-runtime-line" style="color: var(--rn-text-dim);">
                  {{ info.hostname || '?' }} · {{ info.platform || '?' }}
                </div>
              </div>
            </div>

            <!-- Threads: live frames -->
            <q-scroll-area v-else-if="activeDebugTab === 'threads'" class="absolute-full">
              <div v-for="t in threads" :key="t.ident" class="rn-list-row">
                <span class="text-weight-medium">{{ t.name }}</span>
                <span class="rn-dim"> · ident {{ t.ident }}</span>
                <div v-if="t.function" class="rn-sub">
                  {{ shortFile(t.file) }}:{{ t.line }} · {{ t.function }}
                </div>
              </div>
            </q-scroll-area>

            <!-- Modules: Python (server) + Browser (lazy-loaded JS libs) -->
            <q-scroll-area v-else-if="activeDebugTab === 'modules'" class="absolute-full">
              <div class="rn-section-header">Browser · llming-stage extensions</div>
              <div v-if="!extensions.loaded.length && !Object.keys(extensions.versions).length"
                   class="rn-list-row rn-dim">no extensions detected yet</div>
              <div v-for="name in Array.from(new Set([...Object.keys(extensions.versions), ...extensions.loaded])).sort()"
                   :key="'js-' + name" class="rn-list-row">
                <span>{{ name }}</span>
                <span v-if="extensions.versions[name]" class="rn-dim">  =={{ extensions.versions[name] }}</span>
                <span v-else-if="!extensions.versions[name] && extensions.loaded.includes(name)"
                      class="rn-sub">  · loaded</span>
              </div>

              <div class="rn-section-header">Python · sys.modules</div>
              <div v-for="m in modules" :key="'py-' + m.name" class="rn-list-row">
                <span>{{ m.name }}</span>
                <span v-if="m.version" class="rn-dim">  =={{ m.version }}</span>
              </div>
            </q-scroll-area>

            <!-- Sessions: list left, detail right -->
            <div v-else-if="activeDebugTab === 'sessions'" class="absolute-full row no-wrap">
              <div class="col-5 column" style="border-right: 1px solid var(--rn-border); min-width: 0;">
                <div class="rn-sessions-bar row items-center no-wrap" v-if="sessionsAvailable">
                  <span class="rn-stat-label">{{ sessions.length }} session{{ sessions.length === 1 ? '' : 's' }}</span>
                  <q-space />
                  <span class="rn-live-pill">
                    <span class="rn-live-dot"></span>
                    live
                  </span>
                </div>
                <q-scroll-area class="col">
                  <div v-if="!sessionsAvailable" class="rn-empty">
                    <div class="rn-empty-title">Not connected to a server</div>
                    <div class="rn-empty-hint">
                      This view runs entirely in your browser — there's
                      no live server connection to show.
                    </div>
                  </div>
                  <div v-else-if="!sessions.length" class="rn-empty">
                    <div class="rn-empty-title">Waiting for a connection</div>
                    <div class="rn-empty-hint">
                      Open the sample in a tab — new sessions appear
                      here automatically.
                    </div>
                  </div>
                  <div v-for="s in sessions" :key="s.session_id"
                       class="rn-session-row"
                       :class="activeSessionId === s.session_id ? 'rn-session-row--active' : ''"
                       @click="openSession(s.session_id)">
                    <div class="row no-wrap items-center">
                      <span class="rn-session-id">{{ s.session_id.slice(0, 12) }}</span>
                      <q-space />
                      <span class="rn-session-flag" :class="s.controller_ready ? 'rn-session-flag--on' : ''">
                        {{ s.controller_ready ? 'ws' : '—' }}
                      </span>
                    </div>
                    <div class="rn-sub">
                      <span v-if="s.user_id">{{ s.user_id }}</span>
                      <span v-if="s.last_seen">  · last {{ fmtTs(s.last_seen) }}</span>
                    </div>
                  </div>
                </q-scroll-area>
              </div>
              <div class="col column" style="min-width: 0;">
                <q-scroll-area v-if="activeSessionDetail" class="col">
                  <div class="rn-section-header">{{ activeSessionId }}</div>
                  <div v-if="activeSessionDetail.error" class="rn-list-row rn-dim">
                    {{ activeSessionDetail.error }}
                  </div>
                  <template v-else>
                    <div class="rn-kv">
                      <span class="rn-kv-key">user_id</span>
                      <span class="rn-kv-value">{{ activeSessionDetail.record?.user_id || '—' }}</span>
                    </div>
                    <div class="rn-kv">
                      <span class="rn-kv-key">controller_ready</span>
                      <span class="rn-kv-value">{{ activeSessionDetail.record?.controller_ready ? 'yes' : 'no' }}</span>
                    </div>
                    <div class="rn-kv" v-if="activeSessionDetail.record?.last_seen">
                      <span class="rn-kv-key">last_seen</span>
                      <span class="rn-kv-value">{{ fmtTs(activeSessionDetail.record.last_seen) }}</span>
                    </div>
                    <div class="rn-kv" v-if="activeSessionDetail.record?.created_at">
                      <span class="rn-kv-key">created_at</span>
                      <span class="rn-kv-value">{{ fmtTs(activeSessionDetail.record.created_at) }}</span>
                    </div>
                    <div class="rn-section-header" style="margin-top: 8px;">state</div>
                    <pre class="rn-state">{{ JSON.stringify(activeSessionDetail.state || {}, null, 2) }}</pre>
                  </template>
                </q-scroll-area>
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

<script src="/_stage/vendor/vue.global.prod.js"></script>
<script src="/_stage/vendor/quasar.umd.prod.js"></script>
<script>
(() => {
  const SAMPLE_PORT = '__SAMPLE_PORT__';
  const sampleOrigin = location.protocol + '//' + location.hostname + ':' + SAMPLE_PORT;
  const LOGO_URL = '__LOGO_DATA_URL__';

  const { createApp, ref, computed, onMounted, watch, nextTick } = Vue;

  const App = {
    setup() {
      // --- Local-storage persistence (last picked sample, debug-tab, etc.)
      const PREF = {
        sample:       'gallery-sample',
        debugTab:     'gallery-debug-tab',
        debugDrawer:  'gallery-debug-drawer',
        consoleMode:  'gallery-console-mode',
      };
      function loadPref(key, fallback) {
        try {
          const v = localStorage.getItem(key);
          return v === null ? fallback : v;
        } catch (_) { return fallback; }
      }
      function savePref(key, value) {
        try { localStorage.setItem(key, value); } catch (_) {}
      }
      function clearPref(key) {
        try { localStorage.removeItem(key); } catch (_) {}
      }

      const samples = ref([]);
      const current = ref(null);
      const busy = ref(false);
      const status = ref('idle');
      const error = ref('');
      const iframeSrc = ref(null);
      const drawer = ref(true);
      const debugDrawer = ref(loadPref(PREF.debugDrawer, '1') === '1');

      // --- Debug WS state ---
      const debugAvailable = ref(false);   // true once a WS open succeeded
      const debugReady = ref(false);       // currently connected
      const debugStatus = ref('idle');
      const debugError = ref('');
      const activeDebugTab = ref(loadPref(PREF.debugTab, 'console'));
      const debugTabs = [
        { id: 'console',  label: 'Console' },
        { id: 'metrics',  label: 'Metrics' },
        { id: 'threads',  label: 'Threads' },
        { id: 'modules',  label: 'Modules' },
        { id: 'sessions', label: 'Sessions' },
      ];
      const info = ref({});
      const metrics = ref({
        cpu_percent: 0, rss_bytes: 0, vms_bytes: 0,
        threads: 0, fds: null, uptime_seconds: 0,
      });
      const modules = ref([]);
      const threads = ref([]);
      const stdout = ref([]);
      const sessions = ref([]);
      const sessionsAvailable = ref(true);
      const activeSessionId = ref(null);
      const activeSessionDetail = ref(null);
      const sessionsRefreshedAt = ref(0);

      // Console — interleaved Python stdout + JS console + eval echoes.
      const jsLog = ref([]);            // {kind: 'js'|'eval-in'|'eval-out'|'eval-err', level?, text, ts}
      const consoleMode = ref(loadPref(PREF.consoleMode, 'both'));  // 'both' | 'py' | 'js'
      const jsInput = ref('');
      const jsHistory = ref([]);
      let jsHistoryIdx = -1;
      let evalSeq = 1;
      const evalPending = new Map();
      const bridgeReady = ref(false);
      const extensions = ref({ loaded: [], versions: {}, stage_base: '', stage_lib_version: '' });

      const consoleEntries = computed(() => {
        const m = consoleMode.value;
        const out = [];
        if (m !== 'js') {
          for (const line of stdout.value) out.push({ kind: 'py', text: line, ts: 0 });
        }
        if (m !== 'py') {
          for (const e of jsLog.value) out.push(e);
        }
        return out;
      });

      const stdoutText = computed(() => {
        if (!consoleEntries.value.length) return '(no output captured yet)';
        return consoleEntries.value.map(e => {
          let tag;
          if (e.kind === 'py') tag = '[PY]';
          else if (e.kind === 'eval-in') tag = '> ';
          else if (e.kind === 'eval-out') tag = '← ';
          else if (e.kind === 'eval-err') tag = '✗ ';
          else tag = '[JS' + (e.level === 'error' ? '!' : e.level === 'warn' ? '*' : '') + ']';
          return tag + (tag.length === 2 ? '' : ' ') + e.text;
        }).join('\n');
      });

      const consoleEl = ref(null);
      let debugWs = null;
      let metricsTimer = null;
      let consoleTimer = null;
      let sessionsTimer = null;
      let nextId = 1;
      const pending = new Map();
      const shortFile = (f) => f ? f.split('/').slice(-2).join('/') : '?';
      const fmtTs = (ts) => {
        if (!ts) return '';
        const d = new Date(typeof ts === 'number' && ts < 1e12 ? ts * 1000 : ts);
        return d.toLocaleTimeString();
      };

      // --- Always scroll the console pane to the bottom after content updates.
      function scrollConsoleBottom() {
        nextTick(() => {
          const el = consoleEl.value;
          if (el) el.scrollTop = el.scrollHeight;
        });
      }

      // --- iframe <-> runner postMessage bridge (shell side opted in via env var)
      function postToIframe(payload) {
        const f = document.getElementById('frame');
        if (!f || !f.contentWindow) return;
        f.contentWindow.postMessage({ ...payload, source: 'llming-stage-runner' }, '*');
      }

      window.addEventListener('message', (ev) => {
        const m = ev.data;
        if (!m || m.source !== 'llming-stage-bridge') return;
        if (m.type === 'ready') {
          bridgeReady.value = true;
          // Pull initial extension list so the Modules tab shows the browser-side
          // libs without the user having to click first.
          postToIframe({ type: 'extensions', id: 'init' });
          return;
        }
        if (m.type === 'console') {
          jsLog.value.push({ kind: 'js', level: m.level, text: m.text, ts: m.ts });
          if (jsLog.value.length > 500) jsLog.value.splice(0, jsLog.value.length - 500);
          if (activeDebugTab.value === 'console') scrollConsoleBottom();
          return;
        }
        if (m.type === 'eval-result') {
          const p = evalPending.get(m.id);
          if (p) {
            evalPending.delete(m.id);
            if (m.ok) p.resolve(m.result);
            else p.reject(new Error(m.error));
          }
          return;
        }
        if (m.type === 'extensions-result') {
          extensions.value = {
            loaded: m.loaded || [],
            versions: m.versions || {},
            stage_base: m.stage_base || '',
            stage_lib_version: m.stage_lib_version || '',
          };
          return;
        }
      });

      function runJs() {
        const code = jsInput.value.trim();
        if (!code) return;
        if (!bridgeReady.value) {
          jsLog.value.push({ kind: 'eval-err', text: 'bridge not ready', ts: Date.now() });
          jsInput.value = '';
          return;
        }
        jsLog.value.push({ kind: 'eval-in', text: code, ts: Date.now() });
        jsHistory.value.push(code);
        jsHistoryIdx = jsHistory.value.length;
        const id = 'e' + (evalSeq++);
        postToIframe({ type: 'eval', id, code });
        new Promise((resolve, reject) => {
          evalPending.set(id, { resolve, reject });
          setTimeout(() => {
            if (evalPending.has(id)) {
              evalPending.delete(id);
              reject(new Error('eval timeout'));
            }
          }, 5000);
        }).then(
          (r) => jsLog.value.push({ kind: 'eval-out', text: String(r), ts: Date.now() }),
          (e) => jsLog.value.push({ kind: 'eval-err', text: e.message, ts: Date.now() }),
        ).finally(() => {
          if (activeDebugTab.value === 'console') scrollConsoleBottom();
        });
        jsInput.value = '';
        scrollConsoleBottom();
      }

      function jsInputKey(ev) {
        if (ev.key === 'ArrowUp') {
          if (!jsHistory.value.length) return;
          jsHistoryIdx = Math.max(0, jsHistoryIdx - 1);
          jsInput.value = jsHistory.value[jsHistoryIdx] || '';
          ev.preventDefault();
        } else if (ev.key === 'ArrowDown') {
          if (!jsHistory.value.length) return;
          jsHistoryIdx = Math.min(jsHistory.value.length, jsHistoryIdx + 1);
          jsInput.value = jsHistory.value[jsHistoryIdx] || '';
          ev.preventDefault();
        }
      }

      const darkPref = localStorage.getItem('gallery-dark');
      const dark = ref(darkPref === null ? true : darkPref === 'true');
      Quasar.Dark.set(dark.value);

      // Build the iframe URL. Pass `stage_dark=0|1` so the llming-stage
      // shell inside the iframe sets Quasar's dark mode to match the
      // gallery — otherwise sample text renders near-black on our dark
      // background.
      const freshUrl = () =>
        sampleOrigin + '/?_t=' + Date.now() +
        '&stage_dark=' + (dark.value ? '1' : '0');

      const toggleDark = () => {
        dark.value = !dark.value;
        Quasar.Dark.set(dark.value);
        localStorage.setItem('gallery-dark', String(dark.value));
        // Reload iframe with the new theme param so the running sample
        // flips too.
        if (current.value) iframeSrc.value = freshUrl();
      };

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

      async function pollMetrics() {
        try {
          const r = await sendQ('metrics');
          metrics.value = r.data;
        } catch (_) {}
      }

      async function fetchInfo() {
        try { info.value = (await sendQ('info')).data || {}; } catch (_) {}
      }
      async function fetchModules() {
        try { modules.value = (await sendQ('modules')).data || []; } catch (_) {}
      }
      async function fetchThreads() {
        try { threads.value = (await sendQ('threads')).data || []; } catch (_) {}
      }
      async function fetchStdout() {
        try {
          const r = await sendQ('stdout_tail', { n: 300 });
          stdout.value = r.data || [];
          if (activeDebugTab.value === 'console') scrollConsoleBottom();
        } catch (_) {}
      }

      async function fetchSessions() {
        try {
          const r = await sendQ('sessions');
          sessionsAvailable.value = !!(r.data && r.data.available);
          sessions.value = (r.data && r.data.sessions) || [];
          sessionsRefreshedAt.value = Date.now();
          // Refresh the open detail when its session is still in the list.
          if (activeSessionId.value) {
            const still = sessions.value.find(s => s.session_id === activeSessionId.value);
            if (!still) { activeSessionId.value = null; activeSessionDetail.value = null; }
            else { openSession(activeSessionId.value); }  // refresh detail too
          }
        } catch (_) {}
      }
      async function openSession(sid) {
        activeSessionId.value = sid;
        activeSessionDetail.value = null;
        try {
          const r = await sendQ('session_state', { session_id: sid });
          activeSessionDetail.value = r.data || null;
        } catch (_) {
          activeSessionDetail.value = { error: 'fetch failed' };
        }
      }

      // Per-tab polling lifecycle: only the active tab generates traffic.
      function applyTabPolling() {
        // Console polls stdout every second when active.
        if (consoleTimer) { clearInterval(consoleTimer); consoleTimer = null; }
        if (debugReady.value && debugDrawer.value && activeDebugTab.value === 'console') {
          fetchStdout();
          consoleTimer = setInterval(fetchStdout, 1000);
        }
        // Metrics ticker only when the pane is open + metrics tab is active.
        if (metricsTimer) { clearInterval(metricsTimer); metricsTimer = null; }
        if (debugReady.value && debugDrawer.value && activeDebugTab.value === 'metrics') {
          pollMetrics();
          metricsTimer = setInterval(pollMetrics, 1000);
        }
        // Sessions ticker: 1 Hz while the tab is active so new connections
        // from other browser tabs/windows show up promptly.
        if (sessionsTimer) { clearInterval(sessionsTimer); sessionsTimer = null; }
        if (debugReady.value && debugDrawer.value && activeDebugTab.value === 'sessions') {
          fetchSessions();
          sessionsTimer = setInterval(fetchSessions, 1000);
        }
      }

      function selectDebugTab(tabId) {
        activeDebugTab.value = tabId;
        if (tabId === 'threads') fetchThreads();
        else if (tabId === 'modules') {
          if (!modules.value.length) fetchModules();
          if (bridgeReady.value) postToIframe({ type: 'extensions', id: 'mods' });
        } else if (tabId === 'sessions') fetchSessions();
        else if (tabId === 'console') scrollConsoleBottom();
        applyTabPolling();
      }

      // Re-evaluate polling whenever the pane is toggled.
      watch(debugDrawer, applyTabPolling);

      // Persist UI state.
      watch(activeDebugTab, (v) => savePref(PREF.debugTab, v));
      watch(debugDrawer,    (v) => savePref(PREF.debugDrawer, v ? '1' : '0'));
      watch(consoleMode,    (v) => savePref(PREF.consoleMode, v));

      // Each iframe reload reboots the JS context, so the browser-side log
      // and bridge readiness should reset too. The Python-side stdout
      // buffer stays because the subprocess didn't restart.
      watch(iframeSrc, () => {
        jsLog.value = [];
        bridgeReady.value = false;
        evalPending.forEach(({ reject }) => reject(new Error('iframe reloaded')));
        evalPending.clear();
        extensions.value = { loaded: [], versions: {}, stage_base: '', stage_lib_version: '' };
      });

      function disconnectDebug() {
        if (metricsTimer)  { clearInterval(metricsTimer);  metricsTimer = null; }
        if (consoleTimer)  { clearInterval(consoleTimer);  consoleTimer = null; }
        if (sessionsTimer) { clearInterval(sessionsTimer); sessionsTimer = null; }
        if (debugWs) {
          try { debugWs.close(); } catch (_) {}
          debugWs = null;
        }
        pending.forEach(({ reject }) => reject(new Error('disconnected')));
        pending.clear();
        evalPending.forEach(({ reject }) => reject(new Error('disconnected')));
        evalPending.clear();
        debugReady.value = false;
        debugAvailable.value = false;
        debugStatus.value = 'idle';
        bridgeReady.value = false;
        info.value = {};
        metrics.value = {
          cpu_percent: 0, rss_bytes: 0, vms_bytes: 0,
          threads: 0, fds: null, uptime_seconds: 0,
        };
        modules.value = [];
        threads.value = [];
        stdout.value = [];
        jsLog.value = [];
        sessions.value = [];
        sessionsAvailable.value = true;
        activeSessionId.value = null;
        activeSessionDetail.value = null;
        extensions.value = { loaded: [], versions: {}, stage_base: '', stage_lib_version: '' };
      }

      function connectDebug() {
        disconnectDebug();
        if (!current.value) return;
        debugStatus.value = 'connecting';
        debugError.value = '';
        const wsScheme = location.protocol === 'https:' ? 'wss' : 'ws';
        const url = `${wsScheme}://${location.hostname}:${SAMPLE_PORT}/_stage/debug/ws`;
        const ws = new WebSocket(url);
        debugWs = ws;
        ws.onopen = () => {
          debugAvailable.value = true;
          debugReady.value = true;
          debugStatus.value = 'connected';
          // One-shot info fetch on connect (cheap, static for lifetime).
          fetchInfo();
          // Always kick the active tab's polling immediately.
          applyTabPolling();
          // If a non-metrics tab is active, do a single eager fetch so the
          // user doesn't have to switch tabs to populate.
          if (activeDebugTab.value === 'threads') fetchThreads();
          if (activeDebugTab.value === 'modules') fetchModules();
        };
        ws.onmessage = (ev) => {
          let msg;
          try { msg = JSON.parse(ev.data); } catch { return; }
          if (msg.id != null && pending.has(msg.id)) {
            const { resolve, reject } = pending.get(msg.id);
            pending.delete(msg.id);
            if (msg.ok) resolve(msg);
            else reject(new Error(msg.error || 'query failed'));
          }
        };
        ws.onerror = () => {
          // Don't surface as a visible error — debug may simply be off.
          debugStatus.value = 'unavailable';
        };
        ws.onclose = () => {
          if (metricsTimer) { clearInterval(metricsTimer); metricsTimer = null; }
          if (consoleTimer) { clearInterval(consoleTimer); consoleTimer = null; }
          if (debugReady.value) debugStatus.value = 'closed';
          debugReady.value = false;
          // Keep debugAvailable=true so the toggle stays visible — the user
          // can reload via the gallery's reload button to reconnect.
        };
      }

      async function refresh() {
        const r = await fetch('/api/samples').then(r => r.json());
        samples.value = r.samples;
        current.value = r.current;
        if (current.value) {
          status.value = 'running';
          iframeSrc.value = freshUrl();
          savePref(PREF.sample, current.value);
          connectDebug();
          return;
        }
        // Server has nothing running. If a previous selection is
        // remembered AND still exists, auto-launch it so the user lands
        // back on the same sample they were using.
        const stored = loadPref(PREF.sample, null);
        if (stored && samples.value.some((s) => s.name === stored)) {
          pick(stored);
        }
      }

      async function pick(name) {
        if (busy.value || name === current.value) return;
        busy.value = true;
        error.value = '';
        status.value = 'starting ' + name + '…';
        iframeSrc.value = null;
        try {
          const r = await fetch('/api/switch/' + encodeURIComponent(name), { method: 'POST' });
          if (!r.ok) {
            const msg = await r.text();
            error.value = 'failed to start ' + name + ': ' + msg;
            status.value = 'idle';
            return;
          }
          const j = await r.json();
          current.value = j.current;
          status.value = 'running';
          iframeSrc.value = freshUrl();
          savePref(PREF.sample, j.current);
          // Sample's HTTP is already up at this point (gallery polled
          // for it); the debug route is registered in the same app pass
          // so the WS is immediately reachable.
          connectDebug();
        } catch (e) {
          error.value = e.message || String(e);
          status.value = 'idle';
        } finally {
          busy.value = false;
        }
      }

      async function stop() {
        if (busy.value) return;
        busy.value = true;
        status.value = 'stopping…';
        error.value = '';
        try {
          disconnectDebug();
          await fetch('/api/stop', { method: 'POST' });
          current.value = null;
          iframeSrc.value = null;
          status.value = 'idle';
          // Explicit stop = forget the last pick; don't auto-relaunch
          // on the next reload.
          clearPref(PREF.sample);
        } finally {
          busy.value = false;
        }
      }

      function reload() {
        if (current.value) iframeSrc.value = freshUrl();
      }

      function popout() {
        // `noopener` makes the new tab a fresh top-level browsing
        // context: no `window.opener`, AND it starts with empty
        // sessionStorage (HTML spec — only opener-linked windows
        // clone storage on creation). Without this, the popped-out
        // tab inherits the iframe's session hint and the two WSes
        // end up sharing one session, starving the iframe of pushes.
        if (current.value) window.open(sampleOrigin + '/', '_blank', 'noopener');
      }

      // Quasar callback: receives the offset reserved by header/footer
      // and the full viewport height, and returns the exact height the
      // q-page should occupy. Keeps the iframe inside the visible
      // preview area so the sample's `min-h-screen` (= 100vh of the
      // iframe document) matches reality and never overflows the gallery
      // viewport.
      const pageStyleFn = (offset, height) => ({
        height: `${height - offset}px`,
      });

      onMounted(refresh);

      return {
        samples, current, busy, status, error, iframeSrc, drawer,
        dark, toggleDark,
        sampleOrigin, logoUrl: LOGO_URL,
        pick, stop, reload, popout,
        pageStyleFn,
        // Debug pane
        debugDrawer, debugAvailable, debugReady, debugStatus, debugError,
        debugTabs, activeDebugTab, selectDebugTab,
        info, metrics, modules, threads, stdoutText, consoleEl, shortFile, fmtTs,
        // Console toggles + JS REPL
        consoleMode, jsInput, runJs, jsInputKey, bridgeReady,
        extensions,
        // Sessions
        sessions, sessionsAvailable, activeSessionId, activeSessionDetail,
        sessionsRefreshedAt,
        openSession,
      };
    },
  };

  const app = createApp(App);
  app.use(Quasar);
  app.mount('#app');
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn

    reload = os.environ.get("STAGE_RELOAD", "1") != "0"
    if reload:
        uvicorn.run(
            "gallery:app",
            host="127.0.0.1",
            port=GALLERY_PORT,
            reload=True,
            reload_dirs=[str(HERE)],
            app_dir=str(HERE),
            log_level="info",
        )
    else:
        uvicorn.run(app, host="127.0.0.1", port=GALLERY_PORT, log_level="info")
