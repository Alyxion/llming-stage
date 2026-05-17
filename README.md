<p align="center"><img src="https://raw.githubusercontent.com/Alyxion/llming-stage/main/media/llming-stage-logo-small.png" alt="LLMing Stage" width="400"></p>

# llming-stage

[![Python 3.14+](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/Alyxion/llming-stage/blob/main/LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/llming-stage.svg)](https://pypi.org/project/llming-stage/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-purple.svg)](https://github.com/astral-sh/ruff)

### AI-native frontend development where AI builds, inspects, and operates.

Build real apps, dashboards, and internal tools as browser UIs your AI can understand and control. `llming-stage` gives an AI assistant a live stage to work on: it can inspect the running browser, call server commands, react to session state, and push updates into the page through the same channel your app uses.

<p align="center"><img src="https://raw.githubusercontent.com/Alyxion/llming-stage/main/media/readme-showcase.webp" alt="llming-stage sample showcase" width="760"></p>

Build the app as a real browser UI, then let AI operate it while it runs. Under the hood, `llming-stage` ships the app shell, bundled frontend libraries, local assets, routing, lazy loading, and the `llming-com` session wire.

---

### What you get

- **AI-operable apps** - every session, command, and server-pushed event can be inspected and invoked through the debug surface.
- **One live channel per user** - reactive traffic runs over the per-session `llming-com` WebSocket; no duplicate app sockets.
- **Real frontend code** - write normal view files and components instead of Python pretending to be UI.
- **Fast local iteration** - run a sample, edit a view, and keep the browser shell, sessions, and debug tools alive.
- **Vendored assets** - no runtime calls to Google Fonts, jsDelivr, unpkg, cdnjs, analytics beacons, or other third-party hosts.
- **Static exit path** - when an app no longer needs server reactivity, the same shell and view modules can be shipped as static files.

---

### Try it

```bash
poetry install
poetry run python samples/gallery.py
```

Open `http://127.0.0.1:8000` and switch between the polished samples: Three.js, analytics dashboards, Plotly charts, command-driven sessions, uploads, and the extension workbench.

To inspect an already-running debug-enabled app without changing its UI:

```bash
LLMING_STAGE_DEBUG_TOKEN=s3cret llming-stage inspect http://127.0.0.1:8765
```

Open `http://127.0.0.1:8000/`. The inspector attaches from the outside; your app keeps rendering exactly its own UI.

---

### Minimal App

```python
from llming_stage import Stage

if __name__ == "__main__":
    Stage(title="Hello world").add_view("/", "hello.vue").run()
```

```vue
<template>
  <main class="min-h-screen grid place-items-center p-8">
    <h1 class="text-5xl font-bold">Hello llming-stage</h1>
  </main>
</template>
```

For a static view without a Python app:

```bash
llming-stage serve hello.vue
```

---

### Reactive App

```python
from fastapi import FastAPI
from llming_stage import Stage

app = FastAPI()
stage = Stage(app)
sessions = stage.session()
counter = sessions.add_router("counter")

@counter.handler("inc")
async def inc(session, by: int = 1):
    value = int(session.state.get("count", 0)) + by
    session.state["count"] = value
    await session.call("home.setCounter", value)
    return {"ok": True}

stage.add_view("/", "home.vue")
```

`llming-stage` mounts the browser shell and asset routes. `llming-com` carries the authenticated session, command dispatch, and AI-debug surface.

---

### Learn More

- [Quick start](https://github.com/Alyxion/llming-stage/blob/main/docs/content/installation.md)
- [Stage apps](https://github.com/Alyxion/llming-stage/blob/main/docs/content/stage.md)
- [Communication model](https://github.com/Alyxion/llming-stage/blob/main/docs/content/communication-model.md)
- [llming-com integration](https://github.com/Alyxion/llming-stage/blob/main/docs/content/llming-com.md)
- [Assets and lazy loading](https://github.com/Alyxion/llming-stage/blob/main/docs/content/lazy-loading.md)
- [Security](https://github.com/Alyxion/llming-stage/blob/main/docs/content/security.md)
- [API reference](https://github.com/Alyxion/llming-stage/blob/main/docs/content/api.md)

<p align="center"><img src="https://raw.githubusercontent.com/Alyxion/llming-stage/main/media/runtime-architecture.png" alt="llming-stage runtime architecture" width="760"></p>

---

MIT licensed. Bundled third-party files are listed in [THIRD_PARTY.md](https://github.com/Alyxion/llming-stage/blob/main/THIRD_PARTY.md); no AGPL/GPL/LGPL is permitted.
