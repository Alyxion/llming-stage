# 02 — hello_world

The smallest end-to-end llming-com integration. Everything is in
`main.py` — no `_common.py` shortcut. Read the file top-to-bottom
and you have seen the whole llming-com surface area needed to build
a reactive app.

## What it shows

- **FE → BE**: button click sends `{type: 'hello.say', name: ...}`
  on the WebSocket. The `hello.say` handler replies with
  `hello.reply`.
- **BE → FE (timer)**: on WebSocket connect, the server spawns an
  `asyncio.Task` that pushes `{type: 'tick', n}` every second. The
  task is cancelled in `on_disconnect`.

## About the timer

llming-com does not ship a unified per-session scheduler. The
mechanisms it owns are:

- **TTL cleanup** on the session registry (runs periodically,
  evicts idle sessions).
- **Heartbeat ack** in `BaseController.handle_message` (the client
  sends `heartbeat`, the server replies `heartbeat_ack`).

Anything else — periodic pushes, polling an external system,
streaming chunks — is built on top with plain `asyncio.create_task`
inside the WebSocket lifecycle. This sample shows the canonical
shape: create the task in `on_connect`, store the handle on the
session entry, cancel it in `on_disconnect`. If this pattern gets
repeated enough across llming apps, it's a candidate for a small
helper upstream in llming-com.

## Run

```bash
poetry run python samples/02_hello_world/main.py
open http://localhost:8080
```
