# 10 — Capstone dashboard

Everything from the earlier samples composed into one SPA:

| View | Demonstrates |
|------|--------------|
| `/` | Shell, navigation, shared socket bootstrap |
| `/metric` | Lazy Plotly + server-pushed metric stream |
| `/uploads` | Cookie-authed HTTP upload + WebSocket progress |
| `/chat` | Streaming server replies |

All four views run on **one** WebSocket, **one** session, **one**
auth cookie. Navigating between them is a client-side view swap —
the chat history, live chart state, and upload list all survive.

## What to notice

- Three `WSRouter` namespaces (`metric`, `uploads`, `chat`) are
  composed onto a single root router via `root.include(...)`. That
  root is passed to `bootstrap(..., ws_router=root)` and mounted on
  the controller at connect time. Same compose-and-mount pattern
  production llming apps use.
- The home view owns a tiny shared-socket helper
  (`window.__ensureAppSocket`) and a listener registry. Other views
  push their message handlers into that registry on mount and pop
  them on unmount.
- `/api/upload` is the only HTTP route. It uses the auth cookie
  that `/api/session` set, looks up the session entry, and pushes
  progress events back over **that session's** WebSocket — honouring
  the rule that HTTP is strictly for bulk transfer.
- Lazy-loading is visible in Network: Plotly only downloads when
  you first open `/metric`.

## Run

```bash
poetry run python samples/10_full_dashboard/main.py
open http://localhost:8080
```

## AI debugging

Because every reactive command is a WSRouter handler on the
shared controller, an AI agent can list and invoke them via the
llming-com debug API — and watch the live UI react. See the
[communication model](../../docs/communication-model.md) for the
architectural rules this sample follows.
