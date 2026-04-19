# llming-com integration

[`llming-com`](https://github.com/Alyxion/llming-com) is a Python
WebSocket session framework — it owns transport, per-session
registries, HMAC cookie auth, a command-dispatch system, and an
AI-debug API on the server. `llming-stage` owns the UI side and
automatically serves `llming-com`'s WebSocket client (`LlmingWebSocket`)
from the shell, so every view boots with the client globally
available.

## Two command mechanisms, different jobs

The session framework exposes two ways to register server-side
handlers. They are **not alternatives** — pick by transport.

| Mechanism | Transport | Use for | Auto-exposed as |
|-----------|-----------|---------|------------------|
| `WSRouter` + `@router.handler("name")` | WebSocket | Reactive traffic: everything interactive, stateful, pushed | n/a (WS only) |
| `@command(...)` + `build_command_router(registry, prefix="/cmd")` | HTTP | Narrow-scope endpoints: large file transfer, hash-addressable caching, idempotent queries | REST route **and** MCP tool |

Rule of thumb:

- If the client *sends* it as a reactive event → `WSRouter` handler.
- If the client *GETs* or *POSTs* it (uploads, downloads, cache-friendly
  blobs) → `@command`. The endpoint lands at `/cmd/sessions/{sid}/<name>`
  (session scope) or `/cmd/<name>` (global scope), and AI agents can
  invoke it through the MCP tool surface the framework ships.

The communication-model [Rule 2](communication-model.md#rule-2--get--post-for-files-and-caching-only)
sets the boundaries for what's fair game on HTTP at all. Within those
boundaries, `@command` is the canonical declaration.

## What the shell gives you for free

When the shell HTML is served, the browser receives (in order):

1. `vue.global.prod.js` + `quasar.umd.prod.js` — Vue + Quasar runtimes.
2. `llming-com/llming-ws.js` — the `LlmingWebSocket` class (exponential
   reconnect, heartbeat, session-loss detection).
3. `loader.js` + `router.js` — the lazy-load orchestrator and SPA
   router.

After the shell boots, `window.LlmingWebSocket` is globally available
to every view module.

## How assets are routed

`mount_assets(app)` adds the following route (among others):

```
GET /_stage/llming-com/{path:path}
```

It serves the `llming_com/static/` directory shipped inside the
installed `llming-com` wheel. If `llming-com` is not importable at
startup, `mount_assets` raises a clear `RuntimeError` — the package
refuses to run without its server counterpart.

## Opening a session

The host app owns the WebSocket endpoint. llming-stage does not mount
one for you, because the session model (who creates sessions, what
auth cookie is required, how a session ID is returned to the browser)
is application-specific.

A minimal host wiring looks like this:

```python
from starlette.applications import Starlette
from starlette.websockets import WebSocket
from llming_com import BaseSessionRegistry, run_websocket_session
from llming_stage import mount_assets, mount_shell

app = Starlette()
mount_assets(app)

@app.websocket("/ws/{session_id}")
async def ws(websocket: WebSocket, session_id: str):
    await run_websocket_session(
        websocket,
        session_id,
        BaseSessionRegistry.get(),
        on_message=lambda entry, msg: entry.controller.handle_message(msg),
    )

mount_shell(app)
```

## Connecting from a view

A view module receives the mount target element and parameters. Open
the WebSocket using the globally-loaded class:

```js
// views/home.js
window.__stageViews.home = {
  async mount(target, params) {
    const sessionId = await createSession();  // your app-specific call
    const ws = new window.LlmingWebSocket(
      `${location.origin.replace(/^http/, 'ws')}/ws/${sessionId}`,
      {
        onMessage(msg)   { /* update UI */ },
        onSessionLost()  { location.href = '/login'; },
      },
    );
    ws.connect();
    return {
      unmount() { ws.close(); },
    };
  },
};
```

Views that want a single long-lived socket across navigations should
open it once in an earlier view (or in a shell-bootstrap hook) and
hang it off `window` — the shell never reloads, so a reference stays
valid between `mount()` calls.

## Debug API from the AI side

Because llming-com's debug router runs on the same app as the shell,
an AI agent can drive the UI while it is open in the browser:

```bash
# List sessions the shell has opened
curl http://localhost:8080/api/llming/debug/sessions \
  -H "x-debug-key: $DEBUG_CHAT_API_KEY"

# Push a message down the wire — the live UI reacts to it
curl -X POST http://localhost:8080/api/llming/debug/sessions/$SID/send \
  -H "x-debug-key: $DEBUG_CHAT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "hi"}'
```

See the
[llming-com docs](https://github.com/Alyxion/llming-com) for the full
debug API reference.

## Version pinning

`pyproject.toml` pins `llming-com >= 0.1.2`. The shell only uses its
public API — `run_websocket_session`, `BaseSessionRegistry`, and the
static `llming-ws.js` — so minor upgrades are safe. Lock to a specific
version in the host app if you need reproducible deploys.
