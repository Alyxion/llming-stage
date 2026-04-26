<p align="center"><img src="https://raw.githubusercontent.com/Alyxion/llming-stage/main/media/logo-small.png" alt="LLMing Stage" width="400"></p>

# llming-stage

[![Python 3.14+](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/Alyxion/llming-stage/blob/main/LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/llming-stage.svg)](https://pypi.org/project/llming-stage/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-purple.svg)](https://github.com/astral-sh/ruff)

### Build Vue + Quasar UIs that AI can build, drive, and debug.

`llming-stage` is the SPA foundation for AI-assisted frontend work. You write a real Vue + Quasar app, not a Python shim. Reactive traffic and sessions flow through [`llming-com`](https://github.com/Alyxion/llming-com), and that's the same channel an AI assistant uses to inspect state, invoke commands, and push events into the running page.

```mermaid
flowchart LR
    User(["👤 User"]) --> Browser
    AI(["🤖 AI assistant"]) <--> Com
    Browser["<b>Browser</b><br/>Vue + Quasar SPA<br/>(llming-stage shell)"]
    Com["<b>Python server</b><br/>llming-com<br/>sessions · auth · commands<br/>HTTP / MCP debug API"]
    Browser <-->|"per-user WebSocket<br/>reactive commands · server pushes"| Com

    classDef live fill:#1976d2,stroke:#1565c0,color:#fff,stroke-width:1.5px
    classDef ai fill:#a855f7,stroke:#7c3aed,color:#fff,stroke-width:1.5px
    class Browser,Com live
    class AI ai
```

`llming-com` ships the sessions, auth, command dispatcher, and the debug surface — without it, the AI side of the picture goes away. When you eventually deploy and the app no longer needs server reactivity, the same shell + view modules can ship as a static bundle to any CDN.

---

### What you get

- **An AI-debuggable runtime** — every reactive command, session, and event is browseable, invokable, and observable through one HTTP / MCP surface.
- **Modern frontend, zero boilerplate** — Vue 3 + Quasar 2 with a lazy-load orchestrator and an SPA router that keeps the WebSocket and view state alive across navigations.
- **Per-user sessions out of the box** — `llming-com` runs the wire and the auth; you write JS views and Python handlers.
- **Static-deployable** — when there's no server-side reactivity at runtime, the same code ships to GitHub Pages, S3, or any CDN.
- **No third-party network** — every asset is vendored. A page loaded from an `llming-stage` app makes zero requests to Google Fonts, jsDelivr, or any other external host. Privacy/GDPR-friendly by default; enforced by static and runtime tests.

---

### See it in action

```bash
poetry install
./samples/run.sh        # opens a web gallery at http://localhost:8000
```

Ten sample apps — from a one-line "hello" to a Three.js particle tornado and an 8-chart ECharts dashboard — with dark/light theme, hot reload, and AI-debug control.

---

### Minimal app

```python
from starlette.applications import Starlette
from llming_com import BaseSessionRegistry, run_websocket_session
from llming_stage import mount_assets, mount_shell, ShellConfig

app = Starlette()
mount_assets(app)

@app.websocket("/ws/{session_id}")
async def ws(websocket, session_id: str):
    await run_websocket_session(
        websocket, session_id, BaseSessionRegistry.get(),
        on_message=lambda entry, msg: entry.controller.handle_message(msg),
    )

mount_shell(app, config=ShellConfig(
    title="My App",
    routes=[("/", "home"), ("/chat", "chat")],
    preload_views=["home"],
))
```

The browser gets a real Vue + Quasar SPA; the view modules are JavaScript. `llming-com` carries the wire, the sessions, and the debug surface the AI uses.

---

### Learn more

Full docs in [`docs/content/`](docs/content):

- [Quick start](docs/content/installation.md) · [App shell](docs/content/shell.md) · [Communication model](docs/content/communication-model.md)
- [llming-com integration](docs/content/llming-com.md) · [Assets & lazy loading](docs/content/lazy-loading.md)
- [Security](docs/content/security.md) · [API reference](docs/content/api.md)

---

MIT licensed. © 2026 [Michael Ikemann](https://github.com/Alyxion). Bundled third-party files are listed in [`THIRD_PARTY.md`](THIRD_PARTY.md); no AGPL/GPL/LGPL is ever permitted.
