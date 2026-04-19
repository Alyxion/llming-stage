# 04 — Multi-view with a shared session

Two SPA routes, one WebSocket. Navigating between `/` and `/timer`
is a client-side view swap — no page reload, no reconnect, the
server-side timer keeps ticking across the transition.

## What to notice

- `_common.py` creates the session. The home view fetches it on first
  mount and opens the socket, stored on `window.__sampleSocket`. The
  timer view reuses that socket.
- A tiny per-view listener registry (`window.__sampleListeners`)
  handles routing pushes to whichever view is mounted.
- `data-stage-link` on `<a>` tags lets the SPA router intercept
  clicks.
- Start the timer, click "Back home" mid-countdown, then click
  "Open timer" again — the countdown state is kept by the server and
  the UI re-synchronises on the next tick.

## Run

```bash
poetry run python samples/04_multi_view/main.py
open http://localhost:8080
```
