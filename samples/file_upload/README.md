# File upload with WebSocket progress

The only sample that uses an HTTP endpoint for reactive-adjacent
work. It adheres to the [communication model](../../docs/content/communication-model.md)
rules:

- HTTP is used **only** to move the file bytes (narrow scope).
- Every progress event, completion event, and history query goes over
  the WebSocket.
- The HTTP endpoint is authed by the same `{app}_auth` cookie that
  `/api/session` set — no bearer tokens, no ad-hoc auth headers.

## What to notice

- `/api/upload` receives the current session with
  `Depends(sessions.require_session)`. That is how cookie-authed HTTP
  joins the session model without manual auth plumbing in the endpoint.
- Upload chunks are hashed in memory (no disk write — matches the
  no-disk-I/O convention used elsewhere in the llming ecosystem).
- Upload progress and completion call mounted Vue methods via
  `session.call("home.setProgress", ...)` and `session.call("home.finishUpload", ...)`
  on the same socket the browser opened via `/api/session`.
- `uploads.list` is a plain reactive WS command that reads server-held
  history.

## Run

```bash
poetry run python samples/file_upload/main.py
open http://localhost:8765
```
