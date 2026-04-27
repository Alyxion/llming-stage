# Installation

## Install from PyPI

```bash
pip install llming-stage
```

## Install with Poetry

```bash
poetry add llming-stage
```

`llming-stage` targets Python 3.14+ and has three required runtime
dependencies:

- **Starlette** — the HTTP framework the shell mounts onto.
- **`llming-com`** — a Python WebSocket session framework with HMAC
  cookie auth, per-session command dispatch, and an AI-debug API.
  Provides both the `LlmingWebSocket` client JS that the shell loads
  on every view **and** the server-side session infrastructure that
  makes a reactive llming app AI-debuggable. See
  [llming-com integration](llming-com.md).
- **Uvicorn** — used by the `llming-stage serve` CLI for no-Python
  development servers.

`llming-com` is not optional. `mount_assets()` will fail loudly at
startup if it cannot import it.

## Minimal FastAPI app

The recommended API for new apps is `Stage`. You still create and own
the FastAPI app; `Stage` mounts the llming-stage shell, assets, routes,
and development reload.

```python title="main.py"
from fastapi import FastAPI
from llming_stage import Stage

app = FastAPI()
Stage(app).view("/", "home.vue")
```

```vue title="home.vue"
<template>
  <main class="min-h-screen grid place-items-center p-8">
    <h1 class="text-5xl font-bold">Hello llming-stage</h1>
  </main>
</template>
```

Run it with any normal ASGI server:

```bash
uvicorn main:app --reload
```

`Stage(app)` enables browser development reload by default. See
[Stage apps](stage.md) for `.vue` support, directory discovery, and
static publishing.

## Directory discovery

For a conventional app:

```text
my-app/
  main.py
  views/
    home.vue
    chat.vue
    users/
      [id].vue
```

```python title="main.py"
from fastapi import FastAPI
from llming_stage import Stage

app = FastAPI()
Stage(app).discover()
```

## No-Python app

If the app has no backend routes, use the CLI directly:

```text
my-app/
  views/
    home.vue
```

```bash
llming-stage serve .
llming-stage build . --out dist
```

## Low-level mounting

`llming-stage` exposes two entry points: `mount_assets()` adds the asset
routes, `mount_shell()` adds the SPA shell HTML at `/`.

```python
from starlette.applications import Starlette
from llming_stage import mount_assets, mount_shell, ShellConfig

app = Starlette()

mount_assets(app)

mount_shell(
    app,
    config=ShellConfig(
        title="My llming App",
        routes=[
            ("/", "home"),
            ("/chat", "chat"),
        ],
        preload_views=["home"],
    ),
)
```

`mount_assets` must be called **before** `mount_shell` so the asset
routes (`/_stage/*`) take precedence over the shell's catch-all.

### Low-level FastAPI

`llming-stage` does not depend on FastAPI, but it works with any app that
exposes a Starlette-compatible `app.router.routes` list:

```python
from fastapi import FastAPI
from llming_stage import mount_assets, mount_shell

app = FastAPI()
mount_assets(app)
mount_shell(app, title="My llming App")
```

## Serve from a development tree

If you want to override the bundled assets with a local directory (for
development or testing a custom icon pack), pass explicit paths:

```python
from pathlib import Path

mount_assets(
    app,
    vendor_dir=Path("./my_vendor"),
    fonts_dir=Path("./my_fonts"),
    icons_zip=Path("./my_icons.zip"),
)
```

Any argument left as `None` falls back to the bundled asset.
