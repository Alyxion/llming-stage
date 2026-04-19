<p align="center"><img src="https://raw.githubusercontent.com/Alyxion/llming-stage/main/docs/logo-small.png" alt="LLMing Stage" width="400"></p>

# llming-stage

[![Python 3.14+](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/Alyxion/llming-stage/blob/main/LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/llming-stage.svg)](https://pypi.org/project/llming-stage/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-purple.svg)](https://github.com/astral-sh/ruff)

**A Vue + Quasar single-page app shell wired to a per-session WebSocket framework — build reactive, AI-debuggable web apps in pure Python.**

`llming-stage` is the shared SPA foundation for the llming ecosystem. It pairs a Vue + Quasar single-page shell with [`llming-com`](https://github.com/Alyxion/llming-com) — a Python WebSocket session framework that ships HMAC cookie auth, a per-session command dispatcher, and an AI-debug API out of the box. The two together let AI agents inspect and drive a live UI without any bespoke frontend wiring. Unlike NiceGUI, an `llming-stage` app can also be deployed as a **purely static bundle** (GitHub Pages, S3, any CDN) when no server-side reactivity is needed.

## Features

- **App shell** — one HTML document that boots Vue + Quasar once, loads the llming-com WebSocket client, and hosts whichever view the SPA router mounts
- **SPA router** — dependency-free client-side router that lazy-loads view modules; navigation keeps Vue, Quasar, fonts, and the WebSocket alive across view swaps
- **Session framework built in** — `window.LlmingWebSocket` (from `llming-com`) is available on every view after shell boot, pre-wired for reactive command traffic and AI debugging
- **Lazy-load orchestrator** — `window.__stage.load('mermaid')` fetches a library the first time it's needed and never again; KaTeX, Mermaid, Plotly, Three.js, and DOMPurify pre-registered
- **Hardened asset routes** — path-canonicalised Starlette handlers with whitelist-only serving, extension allowlist, symlink rejection, and null-byte/traversal filters
- **Zip-backed icon & emoji sets** — 9,072 Phosphor icons (6 weights) and 3,731 Noto Emoji served individually from packaged zip archives, so the wheel file listing stays sane
- **Static-capable** — `render_shell(config)` returns a fixed HTML string; vendor JS, fonts, icons, and `llming-ws.js` are all snapshottable for pure static hosting
- **Communication model** — three-channel architecture (WebSocket-primary, HTTP for files/caching, static for no-server views) documented as normative rules

## Architecture

```
llming-com        Python WebSocket session framework — transport,
                  HMAC cookie auth, per-session command dispatcher,
                  AI-debug API.
    ↑
llming-stage      App shell · SPA router · vendor JS · fonts · icons.
    ↑
Your views        home · settings · chat · ... (loaded on demand).
```

## Quick Start

### Installation

```bash
pip install llming-stage
```

`llming-com` (the underlying session framework) is a required runtime dependency and is installed automatically. `llming-stage` fails loudly at startup if it cannot import it.

### Minimal app

```python
from starlette.applications import Starlette
from llming_com import BaseSessionRegistry, run_websocket_session
from llming_stage import mount_assets, mount_shell, ShellConfig

app = Starlette()

# 1. Static assets (vendor JS, fonts, icons, llming-com client).
mount_assets(app)

# 2. WebSocket endpoint that llming-com drives.
@app.websocket("/ws/{session_id}")
async def ws(websocket, session_id: str):
    await run_websocket_session(
        websocket, session_id, BaseSessionRegistry.get(),
        on_message=lambda entry, msg: entry.controller.handle_message(msg),
    )

# 3. The SPA shell.
mount_shell(app, config=ShellConfig(
    title="My llming App",
    routes=[("/", "home"), ("/chat", "chat")],
    preload_views=["home"],
))
```

When a browser hits `/`, it receives the shell HTML. Vue + Quasar boot, `LlmingWebSocket` connects, the SPA router mounts the home view. Navigation to `/chat` swaps the view without dropping the socket — the AI's debug session keeps observing the same user across views.

### Writing a view module

```js
// home.js — registered via window.__stage.register('home', { js: '/app/home.js' })
window.__stageViews = window.__stageViews || {};
window.__stageViews.home = {
  mount(target, params) {
    target.innerHTML = '<h1>Hub</h1>';
    return {
      unmount() { target.innerHTML = ''; }
    };
  },
};
```

## Path prefix

All assets are served under `/_stage/` by default. The underscore signals framework-internal and mirrors NiceGUI's `/_nicegui/` convention.

```
/_stage/vendor/…         Vue, Quasar, Three.js, Plotly, KaTeX, DOMPurify
/_stage/fonts/…          Roboto, Material Icons (woff2) + fonts.css
/_stage/icons/…          Phosphor Icons (served from zip)
/_stage/emoji/…          Noto Emoji (served from zip)
/_stage/lang/…           71 Quasar locale packs
/_stage/llming-com/…     LlmingWebSocket client from the installed llming-com wheel
/_stage/loader.js        Lazy-load orchestrator
/_stage/router.js        SPA router
```

## Communication model

Every interactive feature must fit exactly one of three channels — see [`docs/communication-model.md`](docs/communication-model.md) for the full rules.

| Channel | Purpose |
|---------|---------|
| **WebSocket** — one session per user (via `llming-com`) | All reactive, event-driven, stateful communication. Uses `WSRouter` command handlers. |
| **HTTP GET/POST** — cookie-authed | Narrow scope: large file transfer and hash-addressable caching only |
| **Pure static** — no server at all | Apps that need no server reactivity, deployed to GitHub Pages, S3, any CDN |

## Project Structure

```
llming-stage/
├── llming_stage/           # App shell, asset servers, SPA router
│   ├── shell.py            # ShellConfig, mount_assets, mount_shell, render_shell
│   ├── asset_server.py     # Path-hardened Starlette handlers
│   ├── zip_server.py       # Zip-backed SVG serving
│   ├── vendor/             # Vue, Quasar, Three, Plotly, KaTeX, DOMPurify
│   ├── fonts/              # Roboto + Material Icons (woff2) + fonts.css
│   ├── lang/               # 71 Quasar locale packs
│   ├── assets/             # phosphor-icons.zip, noto-emoji.zip
│   └── static/             # loader.js, router.js
├── tests/                  # 50 tests (path validation, serving, shell)
├── docs/                   # MkDocs Material site
└── scripts/                # Asset bundling + content guard
```

## Documentation

Full docs live in [`docs/`](docs) and render with `mkdocs serve`. Highlights:

- [Installation](docs/installation.md) — package install + host-app wiring
- [App shell](docs/shell.md) — `ShellConfig`, view module lifecycle, client-side routing
- [Communication model](docs/communication-model.md) — normative three-channel rules
- [llming-com integration](docs/llming-com.md) — session bootstrap, AI debug API
- [Assets](docs/assets.md) — vendor JS, fonts, icons, locale packs
- [Lazy loading](docs/lazy-loading.md) — `window.__stage.load()` and view modules
- [Security](docs/security.md) — path-traversal hardening
- [API reference](docs/api.md) — Python API + JavaScript runtime surface

## Development

```bash
poetry install
poetry run pytest                         # 50 tests
python scripts/bundle_assets.py           # rebuild bundled vendor/fonts/icons
python scripts/content_guard.py           # pre-commit content check
```

## License

This project is licensed under the [MIT License](https://github.com/Alyxion/llming-stage/blob/main/LICENSE). Copyright (c) 2026 [Michael Ikemann](https://github.com/Alyxion). Every bundled third-party resource is tracked in [`THIRD_PARTY.md`](THIRD_PARTY.md) — no AGPL/GPL/LGPL files are ever permitted in this repository.
