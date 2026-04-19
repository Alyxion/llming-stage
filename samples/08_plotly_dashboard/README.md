# 08 — Live Plotly dashboard

A sine wave with noise, sampled server-side at 2 Hz, streamed over
the WebSocket, drawn by a lazy-loaded Plotly.

## What to notice

- Plotly (~1 MB) is loaded only when this view mounts.
- The sampling coroutine lives on the server — the client has no
  timer, it only consumes `metric.sample` pushes.
- Starting/stopping is another pair of plain WS commands. Closing
  the tab cancels the asyncio task because `controller.send()`
  returns False once the socket is gone.
- `unmount()` purges the Plotly element so navigating away doesn't
  leak the canvas.

## Run

```bash
poetry run python samples/08_plotly_dashboard/main.py
open http://localhost:8080
```
