# llming-stage

A Vue + Quasar SPA shell for building reactive, AI-debuggable web
apps in pure Python.

`llming-stage` is the Vue + Quasar UI foundation that pairs with
[`llming-com`](https://github.com/Alyxion/llming-com) — a Python
WebSocket session framework — to form a complete stack:

- **`llming-com`** — the session framework. WebSocket transport,
  per-session registry with TTL cleanup, HMAC cookie auth, a
  command-dispatch system (`WSRouter` for reactive WS traffic +
  `@command` / `build_command_router` for HTTP), and a debug API
  that lets AI agents inspect and drive a live session.
- **`llming-stage`** — the UI foundation. App shell, SPA router,
  vendored Vue + Quasar + CSS + fonts + icons, and the wiring that
  loads the session framework's WebSocket client on every view.

Together they let you build an application where an AI agent can
inspect, debug, and drive the live UI while a user is still on the
page — without writing transport, session, or frontend-bootstrap code
yourself.

## Static-capable unlike NiceGUI

A defining difference: an llming-stage app that does not need server
reactivity can be deployed as a **purely static bundle** — GitHub
Pages, S3, any CDN. NiceGUI requires a live Python server for every
interaction; llming-stage does not. Views that need server-pushed
events pull in the WebSocket session and the full llming-com stack;
views that don't, stay static. See
[Communication model](communication-model.md).

## What `llming-stage` provides

- **An app shell.** One HTML document that boots Vue + Quasar once,
  loads the llming-com WebSocket client, keeps the socket alive across
  navigations, and hosts whichever view the router mounts.
- **A client-side router.** A small dependency-free router that
  lazy-loads view modules on demand.
- **Path-hardened asset routes.** Starlette routes for vendor JS, fonts,
  locale packs, and llming-com's client JS — with path traversal
  defences baked in.
- **Zip-backed icon/emoji serving.** Thousands of individual SVGs served
  directly from packaged zip archives.
- **A lazy-load orchestrator.** `window.__stage.load('mermaid')` loads
  a library the first time it is needed, and never again.

## Why the session framework is mandatory

The whole point of `llming-stage` is to let AI agents interact with a
running frontend through the session framework's debug and command
APIs. The shell pre-loads `LlmingWebSocket` (`llming-com`'s client
JS) and exposes it globally so every view can use it. Without
`llming-com`:

- The shell has no WebSocket client to load.
- The debug API has nothing to inspect.
- Reactive command handlers have no transport to drive.

`pip install llming-stage` pulls in `llming-com` automatically. The
shell fails loudly at startup if the dependency is missing.

## The shift in architecture

Before:

```
/          → home.html  (Vue, WebSocket client, fonts — all loaded from scratch)
/chat      → chat.html  (loads all of it again; drops the existing WebSocket)
```

After:

```
/          → shell.html → WebSocket opens → SPA router mounts home view
/chat      → same shell, same Vue, same socket → router mounts chat view
```

## Getting started

See [Installation](installation.md) and [App shell](shell.md).

## Licensing

`llming-stage` is MIT licensed. Every bundled third-party resource is
tracked in
[`THIRD_PARTY.md`](https://github.com/Alyxion/llming-stage/blob/main/THIRD_PARTY.md)
with its own license, version, and source URL. **No AGPL/GPL/LGPL
files are ever permitted in this repository.**
