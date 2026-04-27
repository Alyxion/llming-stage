# llming-stage samples

Thirteen progressively richer sample apps that show how to build with
`llming-stage` + [`llming-com`](https://github.com/Alyxion/llming-com)
(the Python WebSocket session framework) by the book. Every sample
that need server reactivity open **one WebSocket per user** and route
reactive traffic through typed `SessionRouter`/`AppRouter` handlers. Purely
client-side samples do not open a WebSocket. The
[communication model](../docs/content/communication-model.md) rules are
followed throughout.

Run any sample with Poetry from the repo root:

```bash
poetry install
./samples/run.sh
# → open http://localhost:8000
```

`run.sh` launches a small web gallery (FastAPI on :8000) with a sample
list on the left and an iframe on the right. Clicking a sample kills
the previously-running one and starts the new sample on :8765. Works
across every terminal because the UI is a browser.

Prefer a straight launch without the gallery? Just run the sample
directly:

```bash
poetry run python samples/02_hello_world/main.py
```

Env knobs for the gallery:

- `GALLERY_PORT` (default `8000`) — the port the gallery listens on.
- `SAMPLE_PORT`  (default `8765`) — the port each sample runs on.

## The progression

| # | Sample | Demonstrates |
|---|--------|--------------|
| 01 | [static](01_static/) | Pure static shell — no WebSocket, no llming-com. Could be deployed to GitHub Pages. |
| 02 | [hello_world](02_hello_world/) | Smallest normal app: FastAPI + `Stage` + one tiny Vue file. |
| 03 | [counter_command](03_counter_command/) | First llming-com sample: Pydantic input/output, server-side state, and Python-to-Vue method calls. |
| 04 | [multi_view](04_multi_view/) | Two SPA routes plus an imported child Vue component sharing one WebSocket. |
| 05 | [file_upload](05_file_upload/) | HTTP POST upload (cookie-authed) + WebSocket progress notifications. |
| 06 | [chat_stream](06_chat_stream/) | Server streams token-by-token replies over the WebSocket. |
| 07 | [3d_scene](07_3d_scene/) | Lazy-loaded Three.js; purely client-side, no WebSocket needed. |
| 08 | [plotly_dashboard](08_plotly_dashboard/) | Lazy-loaded ECharts + server-pushed data stream. |
| 09 | [markdown_render](09_markdown_render/) | Lazy-loaded KaTeX + DOMPurify; math and sanitized HTML on demand. |
| 10 | [full_dashboard](10_full_dashboard/) | Capstone: session routers, app router broadcast, uploads, live charts, and chat. |
| 11 | [plotly_advanced](11_plotly_advanced/) | 3D surface, heatmap, candlestick, Sankey — chart types only in `plotly/full`. |
| 12 | [extension_workbench](12_extension_workbench/) | Marked, DOMPurify, Mermaid, CodeMirror, Drawflow, xterm, and xterm add-ons in one polished Stage app. |
| 13 | [basic_components](13_basic_components/) | Core UI surface: Tailwind layout, Quasar forms, buttons, menus, dialogs, notifications, tabs, tables, trees, and progress. |

## Conventions

- `main.py` is the standalone FastAPI server. Runs under `poetry run python ...`.
- View files live at the sample root as `home.vue`, `metric.vue`, etc.
- `static/` is reserved for real static assets such as images, not app views.
- Use Tailwind utility classes for layout and one-off styling. Add custom
  CSS only when the sample is explicitly about styling.
- Sample view files must stay declarative: no `<style>` blocks, no inline
  `style=`, no imperative `innerHTML`, and no app views hidden under
  `static/*.js`. `tests/test_sample_conventions.py` enforces this.
- Static/frontend-only samples use `Stage(app).view(...)` directly.
- llming-com samples use `_common.py` plus `view_sources={...}` for shared
  session/WebSocket bootstrap, keeping each `main.py` focused on its
  reactive idea.
- Vue views call `await this.$stage.connect()` and send reactive commands
  via `this.$stage.send("router.handler", payload)`.
- Python calls Vue methods directly with addressed calls such as
  `await session.call("home.setCounter", value)`. Child components use
  `stage-id` or their Vue `name` as the target.
- Reactive traffic uses `SessionRouter` handlers that receive `session`
  or `AppRouter` handlers that receive `app`. Use Pydantic models for
  typed payloads and return values where the shape matters.
  HTTP endpoints appear only for file transfer (sample 05, 10) —
  never to model reactive state.

## Contributing a new sample

If the demo is genuinely AI-debuggable and each reactive feature is a
real `SessionRouter` or `AppRouter` handler, it earns a folder. If it shoehorns reactive
logic into REST endpoints or opens a second WebSocket, it does not.
