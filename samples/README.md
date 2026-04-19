# llming-stage samples

Ten progressively richer sample apps that show how to build with
`llming-stage` + [`llming-com`](https://github.com/Alyxion/llming-com)
(the Python WebSocket session framework) by the book. Every sample
opens **one WebSocket per user** and routes reactive traffic through
`WSRouter` handlers mounted on the session controller — the
[communication model](../docs/communication-model.md) rules are
followed throughout.

Run any sample with Poetry from the repo root:

```bash
poetry install
./samples/run.sh
# → open http://localhost:8000
```

`run.sh` launches a small web gallery (FastAPI on :8000) with a sample
list on the left and an iframe on the right. Clicking a sample kills
the previously-running one and starts the new sample on :8080. Works
across every terminal because the UI is a browser.

Prefer a straight launch without the gallery? Just run the sample
directly:

```bash
poetry run python samples/02_hello_world/main.py
```

Env knobs for the gallery:

- `GALLERY_PORT` (default `8000`) — the port the gallery listens on.
- `SAMPLE_PORT`  (default `8080`) — the port each sample runs on.

## The progression

| # | Sample | Demonstrates |
|---|--------|--------------|
| 01 | [static](01_static/) | Pure static shell — no WebSocket, no llming-com. Could be deployed to GitHub Pages. |
| 02 | [hello_world](02_hello_world/) | Smallest end-to-end llming-com integration: one FE→BE call + one timer-driven BE→FE push. |
| 03 | [counter_command](03_counter_command/) | Server-side state + reactive push via `controller.send()`. |
| 04 | [multi_view](04_multi_view/) | Two SPA routes sharing one WebSocket — navigation keeps the session alive. |
| 05 | [file_upload](05_file_upload/) | HTTP POST upload (cookie-authed) + WebSocket progress notifications. |
| 06 | [chat_stream](06_chat_stream/) | Server streams token-by-token replies over the WebSocket. |
| 07 | [3d_scene](07_3d_scene/) | Lazy-loaded Three.js; purely client-side, no WebSocket needed. |
| 08 | [plotly_dashboard](08_plotly_dashboard/) | Lazy-loaded Plotly + server-pushed data stream. |
| 09 | [markdown_render](09_markdown_render/) | Lazy-loaded KaTeX + Mermaid + DOMPurify; math and diagrams on demand. |
| 10 | [full_dashboard](10_full_dashboard/) | Capstone: multi-view SPA with uploads, live charts, and a chat panel. |

## Conventions

- `main.py` is the standalone server. Runs under `poetry run python ...`.
- `static/` holds the view modules. Served at `/app-static/*`.
- `_common.py` in this directory provides the shared session/WebSocket
  bootstrap used by samples 02–10.
- The client-side WebSocket is always `window.LlmingWebSocket` (loaded
  by `llming-stage` — see [llming-com integration](../docs/llming-com.md)).
- Samples fetch `/api/session` on first mount to obtain
  `{sessionId, wsUrl}` and the auth cookie. The session is
  server-generated and returned together with a signed cookie —
  never client-picked.
- Reactive traffic uses `WSRouter` handlers on the session controller.
  HTTP endpoints appear only for file transfer (sample 05, 10) —
  never to model reactive state.

## Contributing a new sample

If the demo is genuinely AI-debuggable and each reactive feature is a
real `WSRouter` handler, it earns a folder. If it shoehorns reactive
logic into REST endpoints or opens a second WebSocket, it does not.
