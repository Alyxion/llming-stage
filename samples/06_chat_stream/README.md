# 06 — Streaming chat

A long-running server task emits `chat.start` / `chat.delta` /
`chat.done` events as chunks become available. The client treats each
delta as a partial update rather than waiting for a complete reply.

## What to notice

- The `chat.ask` handler is a coroutine that yields control with
  `asyncio.sleep()` — so while one reply is streaming, other
  commands from the same client can still be handled.
- Each streamed reply carries an `id` field — the client maintains a
  map of `id → DOM element` so concurrent streams (if any) render
  independently.
- History lives on `SampleSession.state["chat"]` — inspect from a
  server console at any time.
- No REST, no SSE: one socket and direct Vue method calls such as
  `session.call("home.appendReply", id, chunk)`.

## Run

```bash
poetry run python samples/06_chat_stream/main.py
open http://localhost:8765
```
