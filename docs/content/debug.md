# Debug API

Opt-in process-introspection. Designed for a host runner (or a single
operator with a `websocat`) to fetch the running app's metrics, threads,
loaded modules, recent stdout/stderr, and stack frames on demand.

!!! warning "Disabled by default — never auto-enables"
    The debug endpoint is mounted **only** when the environment variable
    `LLMING_STAGE_DEBUG` is set to a truthy value before the app boots.
    Without that env var, no debug route exists, no capture is
    installed, and the running process behaves identically to any
    non-debug deployment.

## Enabling

```bash
LLMING_STAGE_DEBUG=1 poetry run python main.py
```

When the variable is set:

- `Stage(...)` automatically registers a WebSocket endpoint at
  `<asset_prefix>/debug/ws` (defaults to `/_stage/debug/ws`).
- `sys.stdout` and `sys.stderr` are wrapped in a silent ring-buffer
  capture (1000 lines each). The original streams still receive every
  byte — terminal, logging, and any pipes are unaffected.
- The debug code itself **emits zero log lines**. Queries return data
  on demand; they do not push or log on connect/disconnect.

Users wiring `mount_assets()` directly without `Stage` can opt in
manually:

```python
from llming_stage import is_debug_enabled, mount_assets, mount_debug

mount_assets(app)
if is_debug_enabled():
    mount_debug(app)
```

`mount_debug()` itself is also env-gated: if `LLMING_STAGE_DEBUG` is
unset, calling it mounts nothing.

## Securing the endpoint

The debug endpoint binds to whichever interface the host app binds to.
It always requires a bearer token; loopback alone is not trusted because
web pages can attempt WebSocket connections to localhost services.

```bash
LLMING_STAGE_DEBUG=1 \
LLMING_STAGE_DEBUG_TOKEN=$(openssl rand -hex 32) \
poetry run python main.py
```

Clients then connect with the token in the query string:

```
ws://host:port/_stage/debug/ws?token=<the-token>
```

Connections without a matching token are closed with WebSocket close
code `4401` before `accept()`, so they never enter the message loop.
The token comparison uses `hmac.compare_digest`.

The optional iframe runner bridge is separate from the process
WebSocket. It is injected only when both `LLMING_STAGE_DEBUG=1` and
`LLMING_STAGE_DEBUG_PARENT_ORIGIN` are set. The latter is a comma-separated
allow-list of exact parent origins, for example:

```bash
LLMING_STAGE_DEBUG=1 \
LLMING_STAGE_DEBUG_PARENT_ORIGIN=http://127.0.0.1:8000,http://localhost:8000 \
poetry run python main.py
```

Without that parent-origin allow-list, no iframe `postMessage` bridge is
served.

## Debug actions

Debug actions are small browser-side helpers for getting a complex app
back into a useful state after reload: fill fields, select tabs, open a
route, seed demo data, or run a short multi-step flow.

Actions live in sidecar modules next to views:

```text
home.vue
home.debug.js
```

The sidecar is discovered and served only when `LLMING_STAGE_DEBUG` is
truthy before `Stage(...)` registers the view. In production mode, the
module URL is not put into the shell and `/_stage/app/<view>.debug.js`
falls through like any unknown app route. Generated Python views use the
registered view name, for example `home.debug.js` next to `main.py`.

```js
// home.debug.js
export default function debug(ctx) {
  ctx.action("checkout.seed", {
    label: "Seed checkout form",
    scope: "Checkout",
    group: "Forms",
    params: {
      customer: { type: "string", default: "Ada Lovelace" },
      tier: { type: "string", default: "Pro", options: ["Free", "Pro", "Enterprise"] },
    },
    presets: [
      { id: "enterprise", label: "Enterprise", params: { tier: "Enterprise" } },
    ],
  }, (params) => {
    const view = ctx.view;
    view.customer = params.customer;
    view.tier = params.tier;
  });

  ctx.flow("checkout.ready", {
    label: "Checkout demo state",
    steps: [["checkout.seed", { customer: "Grace Hopper", tier: "Enterprise" }]],
  });
}
```

The `ctx` object exposes `enabled`, `viewName`, `view`, `component(id)`,
`stage`, `router`, `command(type, payload)`, `action(...)`, and `flow(...)`.
Action params support `string`, `number`, `boolean`, and `json`, plus an
`options` array for select controls.

The gallery debug pane shows actions inside the selected **Sessions**
detail, because actions are browser-session specific. Operators get
large one-click action buttons or preset buttons for the preview
session. Reload automation state is stored in the sample iframe's
IndexedDB and is never read unless debug mode is enabled.

Normal apps never render debug chrome, even when `LLMING_STAGE_DEBUG` is
enabled. To inspect an already-running app, launch the standalone
inspector from another terminal:

```bash
LLMING_STAGE_DEBUG_TOKEN=s3cret \
llming-stage inspect http://127.0.0.1:8765 --port 8000
```

Open `http://127.0.0.1:8000/`. The inspector owns that second port's
root page and proxies the target app behind the iframe, so the target app
is shown unchanged while the inspector can still access the same debug
actions, sessions, console, metrics, and modules surface. This is
intended for apps already running under an IDE/debugger, for example a
VS Code debug session. The target app must have `LLMING_STAGE_DEBUG=1`
and a matching `LLMING_STAGE_DEBUG_TOKEN` set before boot.

Actions can also be triggered by URL in debug mode:

```text
/?stage_action=checkout.seed&customer=Ada
/?stage_preset=checkout.seed:enterprise
/?stage_flow=checkout.ready
```

For structured params, pass base64url-encoded JSON in `stage_params`.

## Protocol

JSON request/response over a single long-lived WebSocket. Each request
is one object; the response is one object.

```json
// → request
{"id": 1, "q": "metrics"}

// ← response
{"id": 1, "ok": true, "data": {"cpu_percent": 1.2, "rss_bytes": 145000000, ...}}
```

The `id` field is echoed for correlation. Optional — omit if you don't
need it; the response will omit it too. Unknown queries return
`{"ok": false, "error": "...", "available": [...]}` so clients can
discover the catalog.

## Query catalog

| Query | Args | Returns |
|-------|------|---------|
| `info` | — | Package versions, Python info, PID, CWD, hostname, process start, `argv`. Static across the process lifetime. |
| `metrics` | — | `cpu_percent`, `rss_bytes`, `vms_bytes`, `threads`, `fds`, `uptime_seconds`. CPU is measured against the previous sample, so the first call returns 0 — poll at >=2 Hz for meaningful values. |
| `threads` | — | List of `{ident, name, daemon, alive, file, line, function}` for every live thread (current frame). |
| `modules` | — | List of `{name, version, file}` for non-stdlib, non-private top-level imported modules. `version` is best-effort (`module.__version__` / `module.version`). |
| `stack` | `{ident?: int}` | Full stack frames for one thread. `ident` defaults to the main thread. |
| `stdout_tail` | `{n?: int}` | Last `n` lines from the captured stdout ring buffer (default 200, max 1000). |
| `stderr_tail` | `{n?: int}` | Same, for stderr. |

## Smoke check from the shell

Quick interactive verification with [`websocat`](https://github.com/vi/websocat):

```bash
$ LLMING_STAGE_DEBUG=1 LLMING_STAGE_DEBUG_TOKEN=s3cret poetry run python main.py &

$ echo '{"q": "info"}' | websocat 'ws://127.0.0.1:8765/_stage/debug/ws?token=s3cret' | jq .
{
  "ok": true,
  "data": {
    "llming_stage_version": "0.1.5",
    "lib_version": "2026-05",
    "python_version": "3.14.3",
    "pid": 88712,
    ...
  }
}
```

## Performance

- The endpoint is idle until a client connects. No background timers,
  no polling, no batched pushes.
- `metrics` is the most expensive query (one `psutil.Process.oneshot()`)
  and still well under a millisecond per call on a typical laptop.
- `stack` and `threads` use `sys._current_frames()` which momentarily
  pauses other threads. Safe to call at 1 Hz; avoid 100 Hz polling.
- `stdout_tail` / `stderr_tail` are O(n) copy of the ring buffer.
  Negligible at the 200-line default.

## What it is *not*

- **Not a debugger.** It doesn't pause execution, set breakpoints, or
  let you call arbitrary code. For interactive debugging use `pdb`,
  `debugpy`, or `py-spy dump --pid <pid>`.
- **Not a logging system.** Queries are pull-only. Nothing is
  pushed to the WebSocket on its own.
- **Not auditable.** Any client that knows the URL + token has read
  access to every query. Treat the token like a session cookie.
