# Communication model

`llming-stage` defines exactly three ways the browser may talk to
(or not talk to) a server. Every interactive feature in an llming-stage
app must pick one of them — and pick the right one.

This page is normative: it lays down the rules every llming-stage app
is expected to follow.

## The three channels

| Channel | Purpose | When to use |
|---------|---------|-------------|
| **WebSocket** — one session per user, via `llming-com` | Reactive, event-driven, stateful communication | Default channel for everything interactive |
| **HTTP GET / POST** — cookie-authed, narrow scope | Large files and hash-addressable caching | Uploads, downloads, CDN-friendly assets |
| **No server at all** — purely static deploy | Offline / static-host delivery | Apps that need no server reactivity |

## Rule 1 — WebSocket is the primary channel

**All major, reactive communication flows through one per-user
WebSocket session provided by the session framework (`llming-com`).**

- One session per user. Not per tab, not per view, not per feature.
  The session is created by the host app (cookie-authed), and the SPA
  shell reuses it across every client-side navigation.
- All reactive WebSocket commands are defined as `SessionRouter` or
  `AppRouter` handlers — not as ad-hoc REST endpoints or
  `fetch()` calls. The transport, heartbeat, reconnect, and
  session-loss detection are shared machinery — do not rebuild them.
- Views call Python with `this.$stage.send("router.handler", payload)`.
  Python calls mounted Vue methods with `session.call("target.method", ...)`.
- Server→client calls go over the same socket. No Server-Sent Events,
  no long-polling, no app-level `onMessage` parser, no second WebSocket.

Why: one session is what makes the app AI-debuggable. The session
framework's debug API enumerates sessions, inspects state, and
forwards commands over exactly this channel. If interactive logic
routes around the session, it is invisible to the AI.

## Rule 2 — GET / POST for files and caching only

**HTTP endpoints are permitted, but narrowly scoped to two use cases:**

1. **Large file transfer** — uploads (`multipart/form-data`) and
   downloads (binary responses with `Content-Disposition`). These
   would saturate the WebSocket buffer and are better served through
   the browser's native HTTP stack, where the platform handles range
   requests, resumable uploads, and progress UI primitives.

2. **Hash-addressable caching** — content whose URL encodes its hash
   (e.g. `/cas/<sha256>.bin`) so intermediate caches (browser, CDN,
   reverse proxy) can serve repeat requests without round-tripping
   to the application. `ETag` + `If-None-Match` likewise.

The canonical way to declare such an endpoint is the session
framework's `@command(...)` decorator with
`build_command_router(registry, prefix="/cmd")`. A single declaration
gives you:

- A REST route (`GET /cmd/thing` for global scope,
  `POST /cmd/sessions/{sid}/thing` for session scope).
- Parameter coercion from the request body / query string.
- Automatic registration as an **MCP tool** so AI agents can invoke
  the same endpoint they already introspect.
- Injection of `controller`, `entry`, `session_id`, `registry`,
  `request` by parameter name — no manual wiring.

Dropping to a plain `@app.post(...)` route is fine when an endpoint
really is just "move these bytes" (see sample 05), but reach for
`@command` first so the AI debug surface stays complete.

Rules for any HTTP endpoint:

- **Cookie-authed through the same session cookie** that the session
  framework sets. The endpoint must verify the HMAC-signed cookie
  before serving any authenticated content. No bearer tokens, no
  ad-hoc auth headers. If the session is invalid, return 401 — the
  client's stage socket will already have redirected on session
  loss, so this is belt-and-braces.
- **Idempotent or content-addressed.** Do not model reactive state
  transitions as POSTs. A POST that changes session state without
  telling the WebSocket about it will desync the AI's view of the
  world.
- **No fan-out of business logic.** If an HTTP endpoint grows a second
  purpose ("also trigger a workflow"), split the workflow trigger back
  onto the WebSocket as a command and let the HTTP endpoint stay a
  dumb file mover.

Anything that is not file transfer or cache-friendly bulk retrieval
belongs on the WebSocket.

## Rule 3 — Static deploy must stay possible

**An llming-stage app that does not need server-side reactivity must
be deployable as a purely static bundle** — GitHub Pages, S3, any CDN.

If a view is self-contained (renders from client-side data, calls only
hash-cached HTTP GETs, does not need server-pushed events), the whole
app should run from static files.

What "static deploy" means in practice:

- `render_shell(config)` returns a fixed HTML string. Write it to
  `index.html` at build time.
- Vendor JS, fonts, icon zips, locale packs — snapshot them into the
  static output directory at their `/_stage/...` URLs.
- llming-com's `llming-ws.js` ships even in the static bundle. Views
  that don't need a WebSocket simply never call `this.$stage.connect()`.
- The SPA router runs entirely client-side; all routes resolve to the
  same `index.html` via the hosting platform's fallback rule
  (`404 → /index.html` on GitHub Pages, the built-in SPA fallback on
  Netlify/Cloudflare Pages, etc.).

What the static deploy cannot do:

- Server-pushed events (no live server = no push).
- Per-user sessions (no session framework running = no session registry).
- AI debugging via the session framework's debug API (same reason).

**Design implication.** Features that are core to a given view need to
declare their transport up-front: if a view can run without server
reactivity, it belongs in the static-capable set; if it cannot, it
pulls in the WebSocket session and the app is no longer static-deployable.
Mixing the two in one app is fine — the static-capable views stay
static-capable, the reactive views require the server.

## Decision tree

```
Is this a server-push or reactive interaction?
├── Yes  → SessionRouter/AppRouter handler + WebSocket
└── No   → Is this a large file or cache-friendly blob?
          ├── Yes  → HTTP GET/POST (cookie-authed)
          └── No   → Does this need any server state?
                    ├── Yes  → WebSocket (default)
                    └── No   → Pure client-side; no server call at all
```

## Anti-patterns

- **Second WebSocket "because the first one is busy."** The single
  session is the source of truth. Back-pressure and queuing belong in
  llming-com, not in a parallel socket.
- **REST endpoint that wraps a router handler.** If a reactive
  command already exists, call it over the WebSocket. Do not expose
  the same logic as a POST "for convenience" — it bypasses the
  session framework's debug and session machinery.
- **Hidden out-of-band calls during navigation.** Any network traffic
  a view produces must be traceable through the session. Random
  `fetch()` calls with bespoke auth defeat the AI-debug story.
- **A "reactive enough" HTTP polling loop.** If a feature polls, it
  should be pushed. Move it to a server→client command.

## Enforcement

There is no automated enforcement of these rules; they are conventions
the maintainer and reviewers apply. At code-review time, any new
HTTP route, `fetch()` call, or WebSocket connection must be justified
against this page. When in doubt, default to the WebSocket.
