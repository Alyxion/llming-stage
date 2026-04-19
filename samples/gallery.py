"""Web gallery for the llming-stage samples.

Runs on http://localhost:8000 with a sample list on the left and an
iframe on the right. Clicking a sample kills the previous subprocess
and spawns the selected one on port 8080; the iframe then loads it.

Env overrides:
    GALLERY_PORT  — port for the gallery itself (default 8000)
    SAMPLE_PORT   — port each sample is launched on   (default 8080)
"""

from __future__ import annotations

import asyncio
import os
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


def _pick_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


GALLERY_PORT = int(os.environ.get("GALLERY_PORT", "8000"))
# Default to an OS-assigned free port rather than hardcoding 8080 —
# common dev tools (Teams/OneDrive/Jira/...) often squat on 8080.
SAMPLE_PORT = int(os.environ.get("SAMPLE_PORT") or _pick_free_port())


def discover() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for p in sorted(HERE.iterdir()):
        if not (p.is_dir() and (p / "main.py").is_file()):
            continue
        items.append({"name": p.name, "hint": _readme_hint(p / "README.md")})
    return items


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
            if not main_py.is_file():
                raise FileNotFoundError(name)
            env = {**os.environ, "PORT": str(SAMPLE_PORT)}
            self.proc = subprocess.Popen(
                [sys.executable, str(main_py)],
                env=env,
                cwd=str(REPO),
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
            self.proc.terminate()
            for _ in range(100):
                if self.proc.poll() is not None:
                    break
                await asyncio.sleep(0.1)
            if self.proc.poll() is None:
                self.proc.kill()
                self.proc.wait(timeout=5)
        finally:
            self.proc = None
            self.current = None
            for _ in range(50):
                if not _port_open(SAMPLE_PORT):
                    break
                await asyncio.sleep(0.1)


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
    return HTMLResponse(_INDEX_HTML.replace("__SAMPLE_PORT__", str(SAMPLE_PORT)))


_INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>llming-stage gallery</title>
<link rel="stylesheet" href="/_stage/fonts/fonts.css">
<link rel="stylesheet" href="/_stage/vendor/quasar.prod.css">
<style>
  html, body, #app { height: 100%; margin: 0; }
  .name-mono { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 13px; }
  .sample-hint { line-height: 1.35; }
  /* q-page applies min-height but not height; iframes collapse to their
   * default 150px in that case. Give the page an explicit height and
   * anchor the iframe inset:0 so it always fills the visible area. */
  .iframe-page { height: calc(100vh - 50px); padding: 0; overflow: hidden; }
  .iframe-host { position: relative; width: 100%; height: 100%; }
  .iframe-fill { position: absolute; inset: 0; width: 100%; height: 100%; border: 0;
                 display: block; background: transparent; }
  .iframe-placeholder { position: absolute; inset: 0; display: flex; align-items: center;
                        justify-content: center; text-align: center; padding: 24px; opacity: .8; }
</style>
</head>
<body>
<div id="app">
  <q-layout view="hHh Lpr lFf">
    <q-header elevated>
      <q-toolbar>
        <q-btn flat dense round icon="menu" aria-label="toggle sidebar" @click="drawer = !drawer"></q-btn>
        <q-toolbar-title class="row items-center q-gutter-sm">
          <span>llming-stage gallery</span>
          <q-chip v-if="current" dense square color="primary" text-color="white" :data-test="'current'">
            <span class="name-mono">{{ current }}</span>
          </q-chip>
          <span v-if="current" class="text-caption text-grey-4">{{ sampleOrigin }}</span>
        </q-toolbar-title>
        <q-btn flat dense icon="refresh" label="reload" :disable="!current || busy"
               @click="reload" data-test="btn-reload"></q-btn>
        <q-btn flat dense icon="open_in_new" label="open" :disable="!current || busy"
               @click="popout" data-test="btn-popout"></q-btn>
        <q-btn flat dense icon="stop" label="stop" :disable="!current || busy"
               @click="stop" data-test="btn-stop"></q-btn>
        <q-btn flat dense round :icon="dark ? 'light_mode' : 'dark_mode'"
               :aria-label="dark ? 'switch to light mode' : 'switch to dark mode'"
               @click="toggleDark" data-test="btn-dark"></q-btn>
      </q-toolbar>
    </q-header>

    <q-drawer v-model="drawer" :width="320" show-if-above bordered side="left">
      <q-scroll-area class="fit">
        <q-list separator>
          <q-item-label header>SAMPLES</q-item-label>
          <q-item v-for="s in samples" :key="s.name" clickable v-ripple
                  :active="s.name === current" active-class="bg-primary text-white"
                  @click="pick(s.name)" :data-sample="s.name">
            <q-item-section>
              <q-item-label class="name-mono">{{ s.name }}</q-item-label>
              <q-item-label caption lines="2" class="sample-hint">{{ s.hint }}</q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
      </q-scroll-area>
    </q-drawer>

    <q-page-container>
      <q-banner v-if="error" dense class="bg-negative text-white">
        <template v-slot:avatar><q-icon name="error" /></template>
        {{ error }}
      </q-banner>
      <q-page class="iframe-page">
        <div class="iframe-host">
          <iframe v-if="iframeSrc" :src="iframeSrc" class="iframe-fill"
                  id="frame" data-test="frame"></iframe>
          <div v-else-if="busy" class="iframe-placeholder column items-center q-gutter-sm">
            <q-spinner color="primary" size="32px"></q-spinner>
            <div class="text-grey">{{ status }}</div>
          </div>
          <div v-else class="iframe-placeholder text-grey">
            Pick a sample on the left to launch it.
          </div>
        </div>
      </q-page>
    </q-page-container>
  </q-layout>
</div>

<script src="/_stage/vendor/vue.global.prod.js"></script>
<script src="/_stage/vendor/quasar.umd.prod.js"></script>
<script>
(() => {
  const SAMPLE_PORT = '__SAMPLE_PORT__';
  const sampleOrigin = location.protocol + '//' + location.hostname + ':' + SAMPLE_PORT;

  const { createApp, ref, computed, onMounted } = Vue;

  const App = {
    setup() {
      const samples = ref([]);
      const current = ref(null);
      const busy = ref(false);
      const status = ref('idle');
      const error = ref('');
      const iframeSrc = ref(null);
      const drawer = ref(true);

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

      async function refresh() {
        const r = await fetch('/api/samples').then(r => r.json());
        samples.value = r.samples;
        current.value = r.current;
        if (current.value) {
          status.value = 'running';
          iframeSrc.value = freshUrl();
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
          await fetch('/api/stop', { method: 'POST' });
          current.value = null;
          iframeSrc.value = null;
          status.value = 'idle';
        } finally {
          busy.value = false;
        }
      }

      function reload() {
        if (current.value) iframeSrc.value = freshUrl();
      }

      function popout() {
        if (current.value) window.open(sampleOrigin + '/', '_blank');
      }

      onMounted(refresh);

      return {
        samples, current, busy, status, error, iframeSrc, drawer,
        dark, toggleDark,
        sampleOrigin,
        pick, stop, reload, popout,
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

    uvicorn.run(app, host="127.0.0.1", port=GALLERY_PORT, log_level="info")
