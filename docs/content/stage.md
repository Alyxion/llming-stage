# Stage apps

`Stage` is the recommended API for new FastAPI or Starlette apps. It is
OOP and FastAPI-native: you still create and own the app, then mount
llming-stage onto it.

## Core Principle: FastAPI Stays Visible

`llming-stage` must not hide FastAPI. `Stage` mounts routes, assets,
views, sessions, and development reload onto an app you own. It does
not replace FastAPI or wrap your application in a separate framework.
The optional `stage.run()` helper is a thin `uvicorn.run(...)`
convenience for local demos. For workers, TLS, logging, deployment
processes, or anything non-trivial, run `main:app` with normal ASGI
tooling.

## Minimal App

```python title="main.py"
from llming_stage import Stage

if __name__ == "__main__":
    Stage(title="Hello world").add_view("/", "hello.vue").run()
```

For apps with backend routes, keep FastAPI explicit:

```python title="main.py"
from fastapi import FastAPI
from llming_stage import Stage

app = FastAPI()
stage = Stage(app, title="Hello world")
stage.add_view("/", "home.vue")
```

```vue title="home.vue"
<template>
  <main class="min-h-screen grid place-items-center p-8">
    <h1 class="text-5xl font-bold">Hello llming-stage</h1>
  </main>
</template>
```

`Stage(app)` ensures the internal `/_stage` routes once per app and
enables development reload by default. Tailwind utilities are bundled and
available in `.vue` templates without app-local CSS.

The `stage.run()` block is equivalent to the normal FastAPI way:

```bash
uvicorn main:app --reload
```

Tailwind is available immediately in every view:

```vue title="home.vue"
<template>
  <main class="min-h-screen bg-slate-50 p-8 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
    <h1 class="text-5xl font-black">Dashboard</h1>
  </main>
</template>
```

The `dark:` variant follows Quasar dark mode. You do not need to add a
Tailwind script, CSS file, config file, or build step to the app.

## What `Stage(app)` mounts

The following route groups are idempotently mounted:

- `/_stage/loader.js`
- `/_stage/router.js`
- `/_stage/vendor/...` including Vue, Quasar, Tailwind, and lazy libraries
- `/_stage/fonts/...`
- `/_stage/lang/...`
- `/_stage/icons/...`
- `/_stage/tabler/...`
- `/_stage/emoji/...`
- `/_stage/llming-com/...`
- `/_stage/dev/...` in development mode

It is safe for multiple subprojects to create a `Stage(app)` against the
same app. Existing `/_stage` assets are reused instead of duplicated.

## Bundle version pinning (`lib_version=`) — default for new apps

For apps that will outlive the library bundle they were written against
— typically when many small apps are hosted behind one shared static
mount — declare the vendor-bundle version you targeted:

```python
Stage(app, lib_version="2026-05")  # current LIB_VERSION, baked as a literal
```

**Always pin new apps at scaffold time.** Look up the current value with

```bash
python -c "import llming_stage; print(llming_stage.LIB_VERSION)"
```

and copy the resulting string into your `main.py` as a literal. Don't
pass `lib_version=llming_stage.LIB_VERSION` (the symbol): it always
equals "current installed", resolves to no rewrite, and gives you no
forward compatibility once the package upgrades.

Until that bundle stops being the latest on the shared host, the shell
still emits unversioned URLs (`/_stage/vendor/…`). When the shared host
upgrades to a newer bundle, this app's shell automatically starts
emitting `/_stage/v2026-05/…` instead — so the app keeps loading the
libraries it was built against, provided the shared host kept the older
bundle archived.

`lib_version` is independent of the Python package version
(`__version__`). The bundle version is `llming_stage.LIB_VERSION`,
calendar-formatted (`YYYY-MM`), and only changes when files under
`llming_stage/{vendor, fonts, lang, assets}/` are swapped. See
[Assets → Shared hosting & bundle versioning](assets.md#shared-hosting-bundle-versioning)
for the full workflow including the `llming-stage export-assets` CLI
used to populate the shared host.

!!! note "Samples in this repo don't pin"
    Examples under `samples/` intentionally omit `lib_version=` — they
    travel inside the package and always upgrade with the bundle they
    target. Your apps, living in their own repos, should always pin.

## Development reload

Development reload is enabled by default. The watcher scans essential
source and asset files, including:

- Python and config: `.py`, `.pyi`, `.toml`, `.yaml`, `.yml`, `.ini`
- Views and frontend: `.vue`, `.js`, `.mjs`, `.css`, `.html`, `.json`
- Content/assets: `.md`, `.txt`, `.svg`, `.png`, `.jpg`, `.jpeg`,
  `.gif`, `.webp`, `.avif`, `.ico`, `.woff2`

Reloads are content-hash based. Touching a file without changing bytes
does not reload the browser.

Frontend/content changes send a websocket message to connected browsers
and reload the homepage. Python/config changes are classified as server
reloads. By default they emit a `server-reload` diagnostic; apps that
run under a supervising dev runner can provide a server-reload hook or
use the lower-level `mount_dev_reload(..., server_reload="exit")`.

Disable dev reload explicitly for production-style serving:

```python
stage = Stage(app, dev=False)

stage.add_view("/", "home.vue")
```

## Opt-in debug API

`Stage(...)` auto-mounts a process-introspection WebSocket at
`<asset_prefix>/debug/ws` **only** when the environment variable
`LLMING_STAGE_DEBUG=1` is set before the app boots. Disabled in every
other case. Useful for a host runner that supervises multiple
llming-stage apps and wants live CPU/memory/threads/log tails from each
one. See [Debug API](debug.md) for the env vars, security model, and
query catalog.

## Directory discovery

For conventional apps, put views under `views/` and call `discover()`:

```python title="main.py"
from fastapi import FastAPI
from llming_stage import Stage

app = FastAPI()
Stage(app).discover()
```

Route mapping:

- `views/home.vue` -> `/`
- `views/index.vue` -> `/`
- `views/chat.vue` -> `/chat`
- `views/settings.html` -> `/settings`
- `views/users/[id].vue` -> `/users/:id`
- `views/admin/index.vue` -> `/admin`

## Explicit and Generated Views

The imperative API uses active names:

```python
stage.add_view("/", "home.vue")
stage.add_view("/status", "status.vue")
```

`stage.view(...)` is decorator-only. Use it when the view content is
generated by Python instead of stored in a `.vue` file:

```python
from llming_stage import VueResponse

@stage.view("/")
def home() -> VueResponse:
    return VueResponse(
        "<main class='min-h-screen grid place-items-center'>Generated</main>"
    )
```

The decorated function must return a response object. `VueResponse` is
the normal choice because it goes through the same renderer as `.vue`
files. It accepts `template`, `script`, and `style` separately, or
`template_path`, `script_path`, and `style_path` for parts stored next
to the Python file:

```python
@stage.view("/status")
def status() -> VueResponse:
    return VueResponse(
        template="<main>Status: {{ status }}</main>",
        script_path="status.js",
    )
```

Use `HTMLResponse` only for static generated HTML. Returning `None` or a
raw string is invalid because a view route needs explicit page content
and response semantics.

## Reactive Sessions

For conventional llming-com apps, `Stage.session(...)` mounts
`/api/session` and `/ws/{session_id}`. Vue views call Python with
`this.$stage.send(...)`; Python calls mounted Vue methods with
`session.call("target.method", ...)`.

If `LLMING_AUTH_SECRET` is not set, llming-stage uses a random
per-process secret instead of a known fallback. That is fine for local
single-process development, but production and multi-worker deployments
must set one stable high-entropy `LLMING_AUTH_SECRET` so signed session
cookies survive process restarts and load balancing.

```python title="main.py"
from fastapi import FastAPI
from llming_stage import Stage

app = FastAPI()
stage = Stage(app)
sessions = stage.session()
counter = sessions.add_router("counter")

@counter.handler("inc")
async def inc(session, by: int = 1):
    value = int(session.state.get("count", 0)) + by
    session.state["count"] = value
    await session.call("home.setCounter", value)
    return {"ok": True}

stage.add_view("/", "home.vue")
```

```vue title="home.vue"
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

Root views are addressable by their view name (`home` above). Child
components can use `stage-id="drawer"` or their Vue `name` as the
target for Python calls.

Discovery is intentionally scoped to `views/` by default. It does not
publish arbitrary files from the project root.

## Supported view files

### `.vue`

Single-file components are transformed server-side into a module loaded
by the shell. This avoids requiring every app to install Node, Vite, or
a frontend build chain.

Supported blocks:

```vue
<template>
  <q-card>Hello</q-card>
</template>

<script>
export default {
  data() {
    return { count: 0 };
  },
};
</script>
```

This is a lightweight transform, not a full Vite-compatible compiler.
It is intended for normal Vue option objects, templates, and component
styles. It does not process TypeScript, scoped CSS, preprocessors,
`<script setup>`, or npm imports.

### Compatibility view files

`.html` and `.js` views are still accepted for low-level integrations,
but they are not the recommended authoring model. New apps and samples
should use root-level `.vue` files plus Tailwind/Quasar classes.

## No-Python apps

If an app has no backend routes or websocket handlers, it can be served
or statically built without writing `main.py`:

```text
hello.vue
```

```bash
llming-stage serve hello.vue
```

A directory with exactly one view file also maps that file to `/`:

```text
my-app/
  hello.vue
```

Multi-view apps use the normal `views/` convention:

```text
my-app/
  views/
    home.vue
    about.vue
  static/
    logo.svg
```

Development server:

```bash
llming-stage serve .
```

Static publish bundle:

```bash
llming-stage build . --out dist
```

Use the FastAPI form when the app needs backend routes, auth,
websockets, or llming-com command handlers.

## Portable & single-file builds

`Stage.build()` normally emits an origin-rooted bundle (assets under
`/_stage/...`) — ideal when the app owns the domain root. Three options make
the same build relocatable or fully self-contained.

### Relative, relocatable bundle

```python
stage.build("dist", asset_prefix="_stage")
```

A **relative** `asset_prefix` makes the output drop-in portable: serve it from
the domain root, a sub-path such as `/app/`, or a CDN prefix and it still finds
its libraries and mounts its views. Three things cooperate to make this work
with no rebuild:

- the shell self-locates its asset base from the loader script's own URL;
- each per-route `index.html` is depth-adjusted, so `/reports/summary/` loads
  its libraries from `../../_stage`;
- the SPA router subtracts the route the page was built for to learn the
  deployment base, so client navigation keeps matching wherever the bundle
  lands.

### Fallback bases (far or near)

```python
stage.build("dist", asset_prefix="_stage", asset_fallbacks=["../shared/_stage"])
```

Lazy libraries try the primary base first, then each fallback in order — so one
artifact works whether the vendor tree is bundled right next to the shell or
shared elsewhere. Critical libraries (Vue, Quasar) always load from the primary
base.

### Single-file delivery

```python
stage.build("dist", inline=True)                            # one self-contained file
stage.build("dist", inline=True, inline_max_bytes=300_000)  # skip very large libs
```

Produces a single `index.html` with everything folded in: critical libraries as
inline `<script>` / `<style>`, lazy libraries and view modules as base64 blocks
the loader resolves to in-memory URLs on first use. Nothing is fetched over the
network. `inline_max_bytes` caps which lazy files are inlined; anything larger
is left out and recorded in an HTML comment.

> A hard refresh on a client-only route that has no built `index.html` needs the
> host to fall back to `index.html` — standard for static SPA hosting. Every
> *registered* route gets its own `index.html`, so those survive a refresh.
