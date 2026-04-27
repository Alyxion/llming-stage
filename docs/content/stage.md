# Stage apps

`Stage` is the recommended API for new FastAPI or Starlette apps. It is
OOP and FastAPI-native: you still create and own the app, then mount
llming-stage onto it.

## Minimal FastAPI app

```python title="main.py"
from fastapi import FastAPI
from llming_stage import Stage

app = FastAPI()
stage = Stage(app, root=__file__).view("/", "home.vue")

if __name__ == "__main__":
    stage.run()
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
available in `.vue` templates without app-local CSS. `stage.run()` is
only a local development convenience; production can still run the app
with any ASGI server using `main:app`.

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
Stage(app, dev=False).view("/", "home.vue")
```

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

## Reactive Sessions

For conventional llming-com apps, `Stage.session(...)` mounts
`/api/session` and `/ws/{session_id}`. Vue views call Python with
`this.$stage.send(...)`; Python calls mounted Vue methods with
`session.call("target.method", ...)`.

```python title="main.py"
from fastapi import FastAPI
from llming_stage import Stage

app = FastAPI()
stage = Stage(app)
sessions = stage.session()
counter = sessions.router("counter")

@counter.handler("inc")
async def inc(session, by: int = 1):
    value = int(session.state.get("count", 0)) + by
    session.state["count"] = value
    await session.call("home.setCounter", value)
    return {"ok": True}

stage.view("/", "home.vue")
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
