# 05 — File upload with WebSocket progress

The only sample that uses an HTTP endpoint for reactive-adjacent
work. It adheres to the [communication model](../../docs/communication-model.md)
rules:

- HTTP is used **only** to move the file bytes (narrow scope).
- Every progress event, completion event, and history query goes over
  the WebSocket.
- The HTTP endpoint is authed by the same `{app}_auth` cookie that
  `/api/session` set — no bearer tokens, no ad-hoc auth headers.

## What to notice

- `/api/upload` looks up `auth.get_auth_session_id(request)` from the
  cookie, then finds the session entry in the registry. That is how
  cookie-authed HTTP joins the session model.
- Upload chunks are hashed in memory (no disk write — matches the
  no-disk-I/O convention used elsewhere in the llming ecosystem).
- `upload.progress` + `upload.done` pushes go through
  `entry.controller.send(...)` on the *same* socket the browser opened
  via `/api/session`.
- `uploads.list` is a plain reactive WS command that reads server-held
  history.

## Run

```bash
poetry run python samples/05_file_upload/main.py
open http://localhost:8080
```
