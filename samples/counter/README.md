# Counter with server-side state

Demonstrates **server-authoritative state**: the counter value lives
in `SampleSession.state`, not in the browser. Every click round-trips
and the UI updates only when the server pushes back.

## What to notice

- Two `SessionRouter` handlers: `counter.inc` and `counter.reset`. The
  increment handler receives a Pydantic `IncEvent` from the flat browser
  payload and returns a Pydantic `CounterAck`.
- Python updates the UI by calling the mounted Vue method directly:
  `session.call("home.setCounter", value)`.
- The reply is a *different* message type (`counter.update`) so the
  client renders from the pushed event, not from the request's direct
  response. This is the standard reactive pattern.
- Open two tabs — each gets its own session, so each counter is
  independent. Kill one tab, the counter value survives in the
  registry (until session TTL expires).

## Run

```bash
poetry run python samples/counter/main.py
open http://localhost:8765
```
