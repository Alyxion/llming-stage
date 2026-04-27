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
| `SessionRouter` + `@router.handler("name")` | WebSocket | Per-user reactive traffic with typed `session` | n/a (WS only) |
| `AppRouter` + `@router.handler("name")` | WebSocket | App-wide commands with typed `app` context | n/a (WS only) |
| `@command(...)` + `build_command_router(registry, prefix="/cmd")` | HTTP | Narrow-scope endpoints: large file transfer, hash-addressable caching, idempotent queries | REST route **and** MCP tool |

Rule of thumb:

- If the client *sends* it as per-session reactive event → `SessionRouter`.
- If the client *sends* it as app-wide command → `AppRouter`.
- If the client *GETs* or *POSTs* it (uploads, downloads, cache-friendly
  blobs) → `@command`. The endpoint lands at `/cmd/sessions/{sid}/<name>`
  (session scope) or `/cmd/<name>` (global scope), and AI agents can
  invoke it through the MCP tool surface the framework ships.

The communication-model [Rule 2](communication-model.md#rule-2-get-post-for-files-and-caching-only)
sets the boundaries for what's fair game on HTTP at all. Within those
boundaries, `@command` is the canonical declaration.

## Handler Shape

Sample apps use typed session/app handlers. A single Pydantic payload
parameter is parsed from the flat browser message, and a Pydantic return
model is serialized back to the same JSON shape.

```python
from pydantic import BaseModel
from llming_com import SessionRouter

counter = SessionRouter(prefix="counter")

class IncEvent(BaseModel):
    by: int = 1

class CounterAck(BaseModel):
    ok: bool
    value: int

@counter.handler("inc")
async def inc(session: SampleSession, event: IncEvent) -> CounterAck:
    session.state["count"] = int(session.state.get("count", 0)) + event.by
    await session.call("home.setCounter", session.state["count"])
    return CounterAck(ok=True, value=session.state["count"])
```

Use `session.state` for per-user server state, `session.call(...)` for
Python-to-Vue method calls, and `session.start_timer(...)` for
server-driven ticks. `AppRouter` handlers receive `app` instead:

```python
from llming_com import AppRouter, BaseLlmingApp

admin = AppRouter(prefix="admin")

@admin.handler("broadcast")
async def broadcast(app: BaseLlmingApp[SampleSession], message: str) -> dict:
    sent = await app.broadcast("home.setBroadcast", message)
    return {"ok": True, "sent": sent}
```

## What the shell gives you for free

When the shell HTML is served, the browser receives (in order):

1. `vue.global.prod.js` + `quasar.umd.prod.js` — Vue + Quasar runtimes.
2. `llming-com/llming-ws.js` — the `LlmingWebSocket` class (exponential
   reconnect, heartbeat, session-loss detection).
3. `loader.js` + `router.js` — the lazy-load orchestrator and SPA
   router.

After the shell boots, Vue views normally use `this.$stage.connect()`
and `this.$stage.send(...)`; direct `window.LlmingWebSocket` use is
reserved for lower-level integrations.

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

For conventional apps, `Stage.session(...)` mounts `/api/session` and
`/ws/{session_id}`:

```python
from fastapi import FastAPI
from llming_stage import Stage

app = FastAPI()
stage = Stage(app).session(session_router=counter, app_router=admin)
stage.view("/", "home.vue")
```

## Connecting from a view

Vue components call Python routers with `$stage.send(...)`. Python calls
Vue methods by addressed target, e.g. `session.call("home.setCounter")`.
Root views are registered by their view name; child components can use
`stage-id` or their Vue `name`.

```vue
<script>
export default {
  data() {
    return { value: 0 };
  },

  async mounted() {
    await this.$stage.connect();
  },

  methods: {
    inc() {
      this.$stage.send("counter.inc", { by: 1 });
    },
    setCounter(value) {
      this.value = value;
    },
  },
};
</script>
```

For nested components:

```vue
<NavDrawer stage-id="drawer" />
```

```python
await session.call("drawer.open")
```

## Debug API from the AI side

Because llming-com's debug router runs on the same app as the shell,
an AI agent can drive the UI while it is open in the browser:

```bash
# List sessions the shell has opened
curl http://localhost:8765/api/llming/debug/sessions \
  -H "x-debug-key: $DEBUG_CHAT_API_KEY"

# Push a message down the wire — the live UI reacts to it
curl -X POST http://localhost:8765/api/llming/debug/sessions/$SID/send \
  -H "x-debug-key: $DEBUG_CHAT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "hi"}'
```

See the
[llming-com docs](https://github.com/Alyxion/llming-com) for the full
debug API reference.

## Version pinning

Runtime packaging requires `llming-com >= 0.1.5,<0.2`. During local
development this repository uses the sibling `../llming-com` path as an
editable dev dependency so router/client changes can be tested together
before the next PyPI release.
