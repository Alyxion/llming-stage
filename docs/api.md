# API reference

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

## `ShellConfig`

```python
@dataclass
class ShellConfig:
    title: str = "llming"
    asset_prefix: str = "/_stage"
    routes: list[tuple[str, str]] = []
    extra_head: str = ""
    extra_body: str = ""
    preload_views: list[str] = []
```

| Field | Meaning |
|-------|---------|
| `title` | Document `<title>`. Escaped. |
| `asset_prefix` | URL prefix where assets are mounted. Must match `mount_assets()`. |
| `routes` | `(pattern, view_module_name)` entries registered with the SPA router at shell boot. |
| `extra_head` | Raw HTML inserted into `<head>` after the shell's own tags. Use for favicons, CSP meta, analytics snippets, etc. |
| `extra_body` | Raw HTML inserted at the end of `<body>`. |
| `preload_views` | View modules to `__stage.load()` immediately after the shell boots. Useful for the default landing view. |

## `render_shell(config: ShellConfig) -> str`

Return the rendered HTML as a string. Useful for custom mounting where
you want to serve the shell from your own route handler (for example,
after applying per-request CSP nonces).

## JavaScript runtime surface

On the browser, the shell exposes:

| Global | Purpose |
|--------|---------|
| `window.__stage.load(name)` | Lazy-load a registered component. Returns a promise. |
| `window.__stage.register(name, entry)` | Register a new component. |
| `window.__stage.loaded` | `Set<string>` of loaded names. |
| `window.__stageRouter.register(pattern, view)` | Register a route. Called automatically for `ShellConfig.routes`. |
| `window.__stageRouter.navigate(path, {replace})` | Programmatic navigation. |
| `window.__stageRouter.start()` | Called automatically at shell boot. |
| `window.__stageRouter.current` | Name of the currently mounted view. |
| `window.__stageViews` | `{name: {mount, unmount?}}` — view modules register here. |
| `window.LlmingWebSocket` | WebSocket client class from llming-com — see [llming-com integration](llming-com.md). |
