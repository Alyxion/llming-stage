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

- Three `SessionRouter` namespaces (`metric`, `uploads`, `chat`) are
  composed onto a single root router via `root.include(...)`. That
  root is passed to `bootstrap(..., ws_router=root)` and mounted on
  the controller at connect time. Same compose-and-mount pattern
  production llming apps use.
- An `AppRouter` namespace (`admin`) demonstrates app-scoped handlers:
  it receives `app`, then broadcasts to mounted Vue method targets.
- Views call `this.$stage.connect()` and expose normal Vue `methods`.
  Python reaches those methods with addressed calls such as
  `session.call("metric.addMetricSample", t, value)`.
- `/api/upload` is the only HTTP route. It uses the auth cookie
  that `/api/session` set, looks up the session entry, and pushes
  progress events back over **that session's** WebSocket — honouring
  the rule that HTTP is strictly for bulk transfer.
- Lazy-loading is visible in Network: Plotly only downloads when
  you first open `/metric`.

## Run

```bash
poetry run python samples/10_full_dashboard/main.py
open http://localhost:8765
```

## AI debugging

Because every reactive command is a router handler on the
shared controller, an AI agent can list and invoke them via the
llming-com debug API — and watch the live UI react. See the
[communication model](../../docs/content/communication-model.md) for the
architectural rules this sample follows.
