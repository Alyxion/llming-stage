# 04 — Multi-view with a shared session

Two SPA routes, one WebSocket. Navigating between `/` and `/timer`
is a client-side view swap — no page reload, no reconnect, the
server-side timer keeps ticking across the transition.

## What to notice

- Shared sample support creates the session. Both views call
  `this.$stage.connect()`, which reuses one socket for the whole SPA.
- Python pushes timer changes with direct Vue method calls:
  `session.call("timer.setTimer", remaining)` and
  `session.call("timer.finishTimer")`.
- `home.vue` imports `NavDrawer.vue` and renders it with
  `stage-id="drawer"`. Python can address that child component directly
  with `session.call("drawer.open", message)`.
- `data-stage-link` on `<a>` tags lets the SPA router intercept
  clicks.
- Start the timer, click "Back home" mid-countdown, then click
  "Open timer" again — the countdown state is kept by the server and
  the UI re-synchronises on the next tick.

## Run

```bash
poetry run python samples/04_multi_view/main.py
open http://localhost:8765
```
