# 12 — Extension workbench

A polished frontend-only workbench that exercises every optional
lazy-loaded extension in one place: Marked, DOMPurify, Mermaid,
CodeMirror, Drawflow, xterm, xterm fit/web-links/WebGL, and the
vendored Quasar/Vue shell.

## What to notice

- `main.py` stays FastAPI-native and tiny: create `FastAPI()`, mount a
  `Stage`, register `home.vue`.
- Each extension is pulled by `await __stage.load(...)` exactly where
  it is needed. Nothing heavy is on the first-paint path.
- The sample is static-publishable because it has no runtime backend
  state or WebSocket.

## Run

```bash
poetry run python samples/12_extension_workbench/main.py
open http://localhost:8765
```
