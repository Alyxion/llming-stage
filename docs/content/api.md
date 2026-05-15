# API reference

## `Stage(app=None, **kwargs)`

FastAPI/Starlette-native OOP helper for new apps. It keeps the host app
owned by FastAPI while ensuring llming-stage internals are mounted once.
If *app* is omitted, `Stage` creates a default `FastAPI` app and forwards
valid extra keyword arguments to `FastAPI(...)`.
Development reload is enabled by default. `stage.run()` is only a thin
local-development wrapper around `uvicorn.run`; native ASGI tooling
remains the production path.

Selected keyword arguments:

| Argument | Meaning |
|----------|---------|
| `title` | Document `<title>`. |
| `root` | Directory or file the Stage's views resolve against. Defaults to the calling Python file's parent. |
| `asset_prefix` | URL prefix where assets are mounted. Defaults to `/_stage`. |
| `dev` / `dev_reload` | Enable development reload. Default `True`. |
| `lib_version` | Optional vendor-bundle pin (calendar `YYYY-MM`). When the pin equals the installed `LIB_VERSION` (or is omitted), URLs stay unversioned; when pinned to an older bundle, every asset URL gains a `/v<YYYY-MM>/` segment. See [Assets → Shared hosting & bundle versioning](assets.md#shared-hosting-bundle-versioning). |

```python
from llming_stage import Stage

if __name__ == "__main__":
    Stage(title="Hello world").add_view("/", "hello.vue").run()
```

Explicit FastAPI ownership remains the normal shape for real apps:

```python
from fastapi import FastAPI
from llming_stage import Stage

app = FastAPI()
stage = Stage(app, title="My app")
stage.add_view("/", "home.vue")
```

Directory discovery maps conventional files under `views/`:

```python
Stage(app).discover()
```

Reactive session apps can mount the conventional llming-com session
routes and ask the returned helper for namespaced routers:

```python
stage = Stage(app)
sessions = stage.session()
counter = sessions.add_router("counter")
admin = sessions.add_app_router("admin")
```

`sessions.require_session` is a FastAPI dependency for cookie-authenticated
HTTP endpoints that need the current session, for example uploads.

Examples:

- `views/home.vue` -> `/`
- `views/chat.vue` -> `/chat`
- `views/users/[id].vue` -> `/users/:id`
- `views/about.vue` -> `/about`

Supported view file types:

- `.vue`: server-side transformed into a Vue component module loaded by the shell.
- `.html` / `.js`: compatibility paths for low-level integrations. New apps should use `.vue`.

### `stage.add_view(...)` and `@stage.view(...)`

Use `stage.add_view(...)` for active registration of file-backed views:

```python
stage.add_view("/", "home.vue")
stage.add_view("/chat", "chat.vue")
```

Use `@stage.view(...)` only as a decorator for generated views. The
function must return a response object; returning `None` or a raw string
is an error.

```python
from llming_stage import VueResponse

@stage.view("/")
def home() -> VueResponse:
    return VueResponse("<main>Hello from Python</main>")
```

`VueResponse` accepts either plain template HTML or a Vue SFC string:

```python
@stage.view("/status")
def status() -> VueResponse:
    return VueResponse(
        template="<main>Status: {{ status }}</main>",
        script_path="status.js",
    )
```

`template`, `script`, and `style` can be provided separately. Use
`template_path`, `script_path`, or `style_path` to load a part from a
file relative to the Python file that defines the view. For larger
components, prefer a normal `.vue` file and `stage.add_view(...)`.

Use `HTMLResponse` only when the generated route should be static HTML
rather than a Vue component.

`Stage(app)` ensures these internal routes once per app:

- `/_stage/loader.js`
- `/_stage/router.js`
- `/_stage/vendor/...`
- `/_stage/fonts/...`
- `/_stage/icons/...`
- `/_stage/tabler/...`
- `/_stage/emoji/...`
- `/_stage/llming-com/...`
- `/_stage/dev/...` when development reload is enabled

No-Python apps can be served or statically built with the CLI:

```bash
llming-stage serve hello.vue
llming-stage serve .
llming-stage build . --out dist
```

Shared-host operators dump the installed package's vendor bundle with:

```bash
llming-stage export-assets --out /var/www/_stage
```

See [Assets → Shared hosting & bundle versioning](assets.md#shared-hosting-bundle-versioning).

### `stage.run(**kwargs)`

Thin local-development wrapper around `uvicorn.run`. It exists so tiny
examples can stay short, but it does not add a second serving model.

```python
if __name__ == "__main__":
    stage.run()
```

Equivalent explicit uvicorn shape:

```python
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8765,
        reload=True,
        reload_dirs=["."],
        app_dir=".",
    )
```

Use uvicorn, Hypercorn, Gunicorn workers, or your deployment server
directly when you need process management, TLS, workers, logging, or
production configuration.

## `mount_assets(app, **kwargs)`

Attach the asset-serving routes to *app* (any Starlette/FastAPI app).

```python
def mount_assets(
    app,
    *,
    asset_prefix: str = "/_stage",
    vendor_dir: Path | None = None,
    fonts_dir: Path | None = None,
    lang_dir: Path | None = None,
    static_dir: Path | None = None,
    icons_zip: Path | None = None,
    emoji_zip: Path | None = None,
    tabler_zip: Path | None = None,
    lib_version_segment: str = "",
) -> None
```

All directory/archive arguments default to the files bundled in the
installed package. Pass explicit paths to override individual assets.

`lib_version_segment` is a pre-resolved version string used by `Stage`
when an app pins an older bundle: a non-empty value inserts `/v<value>/`
between `asset_prefix` and every category subpath. Apps almost never
set this directly — `Stage(app, lib_version="2026-05")` derives it
automatically. See [Assets → Shared hosting & bundle versioning](assets.md#shared-hosting-bundle-versioning).

The registered routes are:

- `<prefix>/loader.js`
- `<prefix>/router.js`
- `<prefix>/vendor/{path:path}`
- `<prefix>/fonts/{path:path}`
- `<prefix>/lang/{path:path}`
- `<prefix>/icons/{path:path}`  (served from `phosphor-icons.zip`)
- `<prefix>/tabler/{path:path}`  (served from `tabler-icons.zip`)
- `<prefix>/emoji/{path:path}`  (served from `noto-emoji.zip`)
- `<prefix>/llming-com/{path:path}`  (served from the installed `llming-com` static dir)

`mount_assets()` raises `RuntimeError` at call time if `llming-com` is
not importable — the package does not function without it.

## `LIB_VERSION` and `__version__`

Two version stamps live on the `llming_stage` package, with on-purpose
distinct roles:

- **`llming_stage.__version__`** — the Python package version (from
  `pyproject.toml`). Read at import time via `importlib.metadata`.
  Bumps frequently for Python-side fixes. **Apps do not pin against
  this.**
- **`llming_stage.LIB_VERSION`** — the vendor-bundle version
  (calendar `YYYY-MM`). Bumps only when files under
  `llming_stage/{vendor, fonts, lang, assets}/` change. The same string
  is stamped at the top of `THIRD_PARTY.md` and a test enforces sync.

Apps pass `LIB_VERSION` to `Stage(app, lib_version=...)` when they want
to keep loading the vendor surface they were built against once the
shared host has refreshed. See [Assets → Shared hosting & bundle versioning](assets.md#shared-hosting-bundle-versioning).

## `export_package_assets(target, *, write_manifest=True)`

Dump the installed package's vendor bundle as a complete static tree
into *target*. Used by the `llming-stage export-assets` CLI to populate
a shared host:

```python
from pathlib import Path
from llming_stage import export_package_assets

export_package_assets(Path("/var/www/_stage"))
```

The result contains `vendor/`, `fonts/`, `lang/`, `llming-com/`,
`icons/`, `emoji/`, `tabler/`, `loader.js`, `router.js`, and
(when *write_manifest* is true) `manifest.json` with
`lib_version`, `pkg_version`, and the category list. Whole-snapshot only
— partial dumps are not supported.

The CLI is the operator-facing surface:

```bash
llming-stage export-assets --out /var/www/_stage
llming-stage export-assets --out /var/www/_stage/v2026-05 --no-manifest
```

## `mount_debug(app, *, asset_prefix="/_stage")`

Mount the opt-in process-introspection WebSocket at
`<asset_prefix>/debug/ws`. Idempotent per app+prefix. Side-effect:
installs the silent stdout/stderr ring-buffer capture (1000 lines each;
the original streams are unchanged).

`Stage(...)` calls this automatically when `is_debug_enabled()` returns
`True` (env var `LLMING_STAGE_DEBUG` is set). Callers using
`mount_assets()` directly can opt in themselves:

```python
from llming_stage import is_debug_enabled, mount_assets, mount_debug

mount_assets(app)
if is_debug_enabled():
    mount_debug(app)
```

See [Debug API](debug.md) for the full env-var, security, and protocol
description.

## `is_debug_enabled()`

Return `True` when `LLMING_STAGE_DEBUG` is set to anything other than
the obvious falsy spellings (`""`, `"0"`, `"false"`, `"no"`, `"off"`,
case-insensitive).

## `mount_shell(app, *, config=None, path="/", **kwargs)`

Register the SPA shell HTML at *path* and as a catch-all for unmatched
routes (so `/chat` still returns the shell on initial load).

```python
def mount_shell(
    app,
    *,
    config: ShellConfig | None = None,
    path: str = "/",
    **config_kwargs,
) -> None
```

Either pass a `ShellConfig` or the same fields as keyword arguments.

## `mount_dev_reload(app, *, config=None, **kwargs)`

Attach development-only reload routes and start a content-hash watcher
with the host Starlette/FastAPI app.

```python
from llming_stage import ShellConfig, mount_assets, mount_dev_reload, mount_shell

mount_assets(app)
mount_dev_reload(app, watch_paths=["."], poll_interval=0.15)
mount_shell(app, config=ShellConfig(dev_reload=True))
```

The mounted routes are:

- `/_stage/dev/client.js`
- `/_stage/dev/ws`
- `/_stage/dev/state`

The watcher scans only essential source/asset extensions (`.py`, `.css`,
`.js`, `.html`, `.svg`, `.png`, `.jpg`, `.webp`, `.json`, `.md`, and
similar). It compares file content hashes, so a timestamp-only touch does
not trigger reload.

Browser assets trigger a websocket message that reloads the configured
homepage in connected browsers. Python/config changes trigger the
`on_server_reload` hook when provided; otherwise they emit a
`server-reload` websocket diagnostic. Set `server_reload="exit"` only when
the process is supervised by a dev runner that will restart it.

For non-shell pages, add the client manually:

```python
from llming_stage import dev_reload_head

html = f"<html><head>{dev_reload_head()}</head><body>...</body></html>"
```

## `ShellConfig`

```python
@dataclass
class ShellConfig:
    title: str = "llming"
    asset_prefix: str = "/_stage"
    routes: list[tuple[str, str]] = []
    view_modules: dict[str, str] = {}
    extra_head: str = ""
    extra_body: str = ""
    preload_views: list[str] = []
    dev_reload: bool = False
    dev_reload_prefix: str = "/_stage/dev"
    lib_version_segment: str = ""
    lib_version: str = ""
```

| Field | Meaning |
|-------|---------|
| `title` | Document `<title>`. Escaped. |
| `asset_prefix` | URL prefix where assets are mounted. Must match `mount_assets()`. |
| `routes` | `(pattern, view_module_name)` entries registered with the SPA router at shell boot. |
| `view_modules` | Map of view names to JavaScript URLs. Each entry becomes a `window.__stage.register(name, { js: url })` call at shell boot. |
| `extra_head` | Raw HTML inserted into `<head>` after the shell's own tags. Use for favicons, theme-color tags, or CSP meta. Do not add external scripts, stylesheets, fonts, or analytics beacons; llming-stage's runtime must stay on the app's own origin. |
| `extra_body` | Raw HTML inserted at the end of `<body>`. |
| `preload_views` | View modules to `__stage.load()` immediately after the shell boots. Useful for the default landing view. |
| `dev_reload` | Include the development reload client script. Requires `mount_dev_reload(app)` in the host app. |
| `dev_reload_prefix` | URL prefix for the development reload client. Must match `DevReloadConfig.url_prefix`. |
| `lib_version_segment` | Pre-resolved version segment. When non-empty (e.g. `"2026-05"`), every asset URL is rewritten as `{asset_prefix}/v{segment}/...`. Set automatically by `Stage` when the app pinned an older bundle; rarely set by hand. |
| `lib_version` | The bundle string the page is actually loading. Emitted as `window.__stageLibVersion` for debug/self-reporting. `Stage` sets this to `LIB_VERSION` when there's no rewrite, or to the pinned string when there is. |

## `render_shell(config: ShellConfig) -> str`

Return the rendered HTML as a string. Useful for custom mounting where
you want to serve the shell from your own route handler (for example,
after applying per-request CSP nonces).

## JavaScript runtime surface

On the browser, the shell exposes:

| Global | Purpose |
|--------|---------|
| `window.__stage.load(name)` | Lazy-load a registered component. Returns a Promise that resolves once the lib has been parsed. **Idempotent and cached** — repeated calls return the same Promise instance with no new fetches and no allocation, so it's safe to put in front of every use (`await __stage.load('plotly')` before each chart render is essentially free after the first call). Concurrent calls during the first load share one in-flight Promise. |
| `window.__stage.isLoaded(name)` | Synchronous check — returns `true` after the named lib has finished loading. Useful for branching without awaiting. |
| `window.__stage.register(name, entry)` | Register a new component. |
| `window.__stage.connect()` | Open or reuse the llming-com session socket from `/api/session`. |
| `window.__stage.send(type, payload)` | Send a routed message such as `counter.inc` to Python. Vue views usually call this as `this.$stage.send(...)`. |
| `window.__stage.onReconnect(handler)` | Register a callback fired after a successful WebSocket auto-reconnect (network blip, server restart). Returns an unsubscribe function. Use it to re-send any "subscribe"-style messages so server-pushed state stays fresh. |
| `window.__stage.call(target, method, args, kwargs)` | Invoke a registered Vue component method. Used by Python `session.call("target.method", ...)` messages. |
| `window.__stage.loaded` | `Set<string>` of loaded names (introspection). |
| `window.__stageBase` | URL prefix the shell resolves vendor paths against. Equals `asset_prefix` for unversioned shells, or `{asset_prefix}/v{lib_version}` when the app pinned an older bundle. |
| `window.__stageLibVersion` | The vendor-bundle version this page is loading (e.g. `"2026-05"`). Debug/self-reporting; nothing in the runtime reads it. |
| `window.__stageRouter.register(pattern, view)` | Register a route. Called automatically for `ShellConfig.routes`. |
| `window.__stageRouter.navigate(path, {replace})` | Programmatic navigation. |
| `window.__stageRouter.start()` | Called automatically at shell boot. |
| `window.__stageRouter.current` | Name of the currently mounted view. |
| `window.__stageViews` | `{name: {mount, unmount?}}` — view modules register here. |
| `window.LlmingWebSocket` | WebSocket client class from llming-com — see [llming-com integration](llming-com.md). |
