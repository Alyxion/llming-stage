# Capstone dashboard

Everything from the earlier samples composed into one SPA:

| View | Demonstrates |
|------|--------------|
| `/` | Shell, navigation, shared socket setup |
| `/metric` | Lazy Plotly + server-pushed metric stream |
| `/uploads` | Cookie-authed HTTP upload + WebSocket progress |
| `/chat` | Streaming server replies |

All four views run on **one** WebSocket, **one** session, **one**
auth cookie. Navigating between them is a client-side view swap —
the chat history, live chart state, and upload list all survive.

## What to notice

- `Stage.session(...)` returns the session helper. The sample asks it
  for `sessions.router("metric")`, `sessions.router("uploads")`, and
  `sessions.router("chat")` instead of assembling a root router by hand.
- An `AppRouter` namespace (`admin`) demonstrates app-scoped handlers:
  `sessions.app_router("admin")` receives `app`, then broadcasts to
  mounted Vue method targets.
- Views call `this.$stage.connect()` and expose normal Vue `methods`.
  Python reaches those methods with addressed calls such as
  `session.call("metric.addMetricSample", t, value)`.
- `/api/upload` is the only HTTP route. It uses
  `Depends(sessions.require_session)` and pushes progress events back
  over **that session's** WebSocket — honouring the rule that HTTP is
  strictly for bulk transfer.
- Lazy-loading is visible in Network: Plotly only downloads when
  you first open `/metric`.

## Run

```bash
poetry run python samples/capstone_dashboard/main.py
open http://localhost:8765
```

## AI debugging

Because every reactive command is a router handler on the
shared controller, an AI agent can list and invoke them via the
llming-com debug API — and watch the live UI react. See the
[communication model](../../docs/content/communication-model.md) for the
architectural rules this sample follows.
