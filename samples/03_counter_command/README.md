# 03 — Counter with server-side state

Demonstrates **server-authoritative state**: the counter value lives
in `SampleSession.state`, not in the browser. Every click round-trips
and the UI updates only when the server pushes back.

## What to notice

- Two `WSRouter` handlers: `counter.inc` and `counter.reset`. Both
  read and mutate `controller.entry.state["count"]`.
- The reply is a *different* message type (`counter.update`) so the
  client renders from the pushed event, not from the request's direct
  response. This is the standard reactive pattern.
- Open two tabs — each gets its own session, so each counter is
  independent. Kill one tab, the counter value survives in the
  registry (until session TTL expires).

## Run

```bash
poetry run python samples/03_counter_command/main.py
open http://localhost:8080
```
