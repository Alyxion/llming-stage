# API reference

## `Stage(app, **kwargs)`

FastAPI/Starlette-native OOP helper for new apps. It keeps the host app
owned by FastAPI while ensuring llming-stage internals are mounted once.
Development reload is enabled by default.

```python
from fastapi import FastAPI
from llming_stage import Stage

app = FastAPI()
Stage(app).view("/", "home.vue")
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
counter = sessions.router("counter")
admin = sessions.app_router("admin")
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
llming-stage serve .
llming-stage build . --out dist
```

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
) -> None
```

All directory/archive arguments default to the files bundled in the
installed package. Pass explicit paths to override individual assets.

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
| `window.__stage.call(target, method, args, kwargs)` | Invoke a registered Vue component method. Used by Python `session.call("target.method", ...)` messages. |
| `window.__stage.loaded` | `Set<string>` of loaded names (introspection). |
| `window.__stageRouter.register(pattern, view)` | Register a route. Called automatically for `ShellConfig.routes`. |
| `window.__stageRouter.navigate(path, {replace})` | Programmatic navigation. |
| `window.__stageRouter.start()` | Called automatically at shell boot. |
| `window.__stageRouter.current` | Name of the currently mounted view. |
| `window.__stageViews` | `{name: {mount, unmount?}}` — view modules register here. |
| `window.LlmingWebSocket` | WebSocket client class from llming-com — see [llming-com integration](llming-com.md). |
