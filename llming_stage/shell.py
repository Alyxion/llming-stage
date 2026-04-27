"""SPA app shell and asset mounting.

The shell is a single HTML document that boots Vue + Quasar once and hosts
whatever view the SPA router navigates to. Vendor libraries beyond the
critical shell (Mermaid, KaTeX, Plotly, ...) are loaded lazily by
``loader.js`` when a view first needs them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import Route

from .asset_server import make_dir_handler
from .dev_reload import dev_reload_head
from .zip_server import ZipArchive, make_zip_handler

_PACKAGE_ROOT = Path(__file__).resolve().parent
_STATIC_ROOT = _PACKAGE_ROOT / "static"
_VENDOR_ROOT = _PACKAGE_ROOT / "vendor"
_FONTS_ROOT = _PACKAGE_ROOT / "fonts"
_LANG_ROOT = _PACKAGE_ROOT / "lang"
_ASSETS_ROOT = _PACKAGE_ROOT / "assets"


def _llming_com_static_dir() -> Path:
    """Return the llming-com static directory.

    llming-com is a mandatory runtime dependency — it provides the
    WebSocket client (``LlmingWebSocket``) and the server-side session
    infrastructure that every llming-stage view relies on. If the
    dependency is missing, the package is broken; surface that loudly.
    """
    try:
        import llming_com  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "llming-stage requires llming-com to be installed. "
            "llming-com provides the WebSocket client that the SPA shell "
            "loads on every page. Install it with `pip install llming-com`."
        ) from exc
    static = Path(llming_com.__file__).resolve().parent / "static"
    if not static.is_dir():
        raise RuntimeError(
            f"llming-com static directory not found at {static}. "
            "This usually means the installed wheel is corrupted."
        )
    return static


@dataclass
class ShellConfig:
    """Configuration for the SPA shell HTML document.

    Attributes:
        title: Document ``<title>``.
        asset_prefix: URL prefix under which assets are served. Defaults to
            ``/_stage``.
        routes: Client-side routes to register with the SPA router. Each
            entry is ``(path_pattern, view_module_name)``. The view module
            must have been registered in ``loader.js`` (or via
            :func:`register_view_module`) with its JS path.
        extra_head: Raw HTML inserted into ``<head>`` after the shell's own
            tags. Use for favicons, theme-color meta tags, etc.
        extra_body: Raw HTML inserted at the end of ``<body>``.
        preload_views: View module names to preload after the shell boots
            (useful for the default landing view).
        dev_reload: Include the development reload client script.
        dev_reload_prefix: URL prefix passed to :func:`mount_dev_reload`.
    """

    title: str = "llming"
    asset_prefix: str = "/_stage"
    routes: list[tuple[str, str]] = field(default_factory=list)
    view_modules: dict[str, str] = field(default_factory=dict)
    extra_head: str = ""
    extra_body: str = ""
    preload_views: list[str] = field(default_factory=list)
    dev_reload: bool = False
    dev_reload_prefix: str = "/_stage/dev"


def render_shell(config: ShellConfig) -> str:
    """Render the SPA shell HTML document."""
    prefix = config.asset_prefix.rstrip("/")
    view_registrations_js = "\n".join(
        f"  window.__stage.register({_js_str(name)}, {{js: {_js_str(url)}}});"
        for name, url in config.view_modules.items()
    )
    routes_js = "\n".join(
        f"  window.__stageRouter.register({_js_str(p)}, {_js_str(v)});"
        for p, v in config.routes
    )
    preload_js = "\n".join(
        f"  window.__stage.load({_js_str(v)}).catch((e) => console.error(e));"
        for v in config.preload_views
    )
    dev_reload_html = dev_reload_head(config.dev_reload_prefix) if config.dev_reload else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_html_escape(config.title)}</title>
<link rel="stylesheet" href="{prefix}/fonts/fonts.css">
<link rel="stylesheet" href="{prefix}/vendor/quasar.prod.css">
<script>window.__stageBase = {_js_str(prefix)};</script>
<style type="text/tailwindcss">
@import "tailwindcss/theme";
@import "tailwindcss/utilities";
@custom-variant dark (&:where(.body--dark, .body--dark *));
</style>
<script type="importmap">
{{
  "imports": {{
    "three": "{prefix}/vendor/three.module.min.js",
    "three/addons/": "{prefix}/vendor/"
  }}
}}
</script>
{config.extra_head}
{dev_reload_html}
</head>
<body>
<div id="app-shell">
  <div id="app-shell-view"></div>
</div>
<script src="{prefix}/vendor/vue.global.prod.js"></script>
<script src="{prefix}/vendor/quasar.umd.prod.js"></script>
<script src="{prefix}/vendor/tailwindcss.browser.global.js"></script>
<script>
// Dark-mode bootstrap. Precedence:
//   1. `?stage_dark=1` / `?stage_dark=0` query param (host app / gallery).
//   2. OS preference via prefers-color-scheme.
// Calls Quasar.Dark.set() which toggles `body--dark` / `body--light`
// so every Quasar typography/component class recolors automatically.
(function () {{
  var p = new URLSearchParams(location.search);
  var dark = null;
  if (p.has('stage_dark')) dark = p.get('stage_dark') === '1';
  else if (window.matchMedia)
    dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  if (window.Quasar && Quasar.Dark) Quasar.Dark.set(!!dark);
}})();
</script>
<script src="{prefix}/llming-com/llming-ws.js"></script>
<script>window.LlmingWebSocket = LlmingWebSocket;</script>
<script src="{prefix}/loader.js"></script>
<script src="{prefix}/router.js"></script>
<script>
(function () {{
{view_registrations_js}
{routes_js}
  window.__stageRouter.start().then(() => {{
{preload_js}
  }});
}})();
</script>
{config.extra_body}
</body>
</html>
"""


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _js_str(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("<", "\\x3c")
        .replace(">", "\\x3e")
    )
    return f"'{escaped}'"


def _asset_routes(
    asset_prefix: str,
    *,
    vendor_dir: Path,
    fonts_dir: Path,
    lang_dir: Path,
    static_dir: Path,
    icons_archive: ZipArchive | None,
    emoji_archive: ZipArchive | None,
    tabler_archive: ZipArchive | None,
) -> list[Route]:
    prefix = asset_prefix.rstrip("/")
    routes: list[Route] = []

    async def loader_js(request: Request) -> Response:
        handler = make_dir_handler(static_dir)
        request.path_params["path"] = "loader.js"
        return await handler(request)

    async def router_js(request: Request) -> Response:
        handler = make_dir_handler(static_dir)
        request.path_params["path"] = "router.js"
        return await handler(request)

    routes.append(Route(f"{prefix}/loader.js", loader_js))
    routes.append(Route(f"{prefix}/router.js", router_js))

    if vendor_dir.exists():
        routes.append(
            Route(f"{prefix}/vendor/{{path:path}}", make_dir_handler(vendor_dir))
        )
    if fonts_dir.exists():
        routes.append(
            Route(f"{prefix}/fonts/{{path:path}}", make_dir_handler(fonts_dir))
        )
    if lang_dir.exists():
        routes.append(
            Route(f"{prefix}/lang/{{path:path}}", make_dir_handler(lang_dir))
        )
    if icons_archive is not None:
        routes.append(
            Route(f"{prefix}/icons/{{path:path}}", make_zip_handler(icons_archive))
        )
    if emoji_archive is not None:
        routes.append(
            Route(f"{prefix}/emoji/{{path:path}}", make_zip_handler(emoji_archive))
        )
    if tabler_archive is not None:
        routes.append(
            Route(f"{prefix}/tabler/{{path:path}}", make_zip_handler(tabler_archive))
        )
    llming_com_dir = _llming_com_static_dir()
    routes.append(
        Route(
            f"{prefix}/llming-com/{{path:path}}",
            make_dir_handler(llming_com_dir),
        )
    )
    return routes


def mount_assets(
    app: Any,
    *,
    asset_prefix: str = "/_stage",
    vendor_dir: Path | None = None,
    fonts_dir: Path | None = None,
    lang_dir: Path | None = None,
    static_dir: Path | None = None,
    icons_zip: Path | None = None,
    emoji_zip: Path | None = None,
    tabler_zip: Path | None = None,
) -> None:
    """Mount the llming-stage asset routes onto *app*.

    Works with any app exposing ``app.router.routes`` (Starlette, FastAPI).
    By default, serves the bundled vendor libs, fonts, locale packs, and
    icon/emoji archives from the installed package. Override paths for
    development or to swap in alternate asset sets.
    """
    icons_path  = icons_zip  if icons_zip  is not None else _ASSETS_ROOT / "phosphor-icons.zip"
    emoji_path  = emoji_zip  if emoji_zip  is not None else _ASSETS_ROOT / "noto-emoji.zip"
    tabler_path = tabler_zip if tabler_zip is not None else _ASSETS_ROOT / "tabler-icons.zip"
    icons_archive  = ZipArchive(icons_path)  if icons_path.exists()  else None
    emoji_archive  = ZipArchive(emoji_path)  if emoji_path.exists()  else None
    tabler_archive = ZipArchive(tabler_path) if tabler_path.exists() else None

    routes = _asset_routes(
        asset_prefix,
        vendor_dir=vendor_dir or _VENDOR_ROOT,
        fonts_dir=fonts_dir or _FONTS_ROOT,
        lang_dir=lang_dir or _LANG_ROOT,
        static_dir=static_dir or _STATIC_ROOT,
        icons_archive=icons_archive,
        emoji_archive=emoji_archive,
        tabler_archive=tabler_archive,
    )
    for route in routes:
        app.router.routes.append(route)


def mount_shell(
    app: Any,
    *,
    config: ShellConfig | None = None,
    path: str = "/",
    **config_kwargs: Any,
) -> None:
    """Register the SPA shell HTML as a catch-all route at *path*.

    The shell is served for the exact *path* and for any path not otherwise
    routed (so client-side navigation to ``/chat`` still returns the shell
    on initial load). Call ``mount_assets`` first so the asset routes take
    precedence over the catch-all.
    """
    if config is None:
        config = ShellConfig(**config_kwargs)
    elif config_kwargs:
        raise TypeError("pass either config= or keyword args, not both")
    html = render_shell(config)

    async def shell_handler(request: Request) -> Response:
        return HTMLResponse(html)

    app.router.routes.append(Route(path, shell_handler))
    if path != "/{path:path}":
        app.router.routes.append(Route("/{path:path}", shell_handler))
