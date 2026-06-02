"""SPA app shell and asset mounting.

The shell is a single HTML document that boots Vue + Quasar once and hosts
whatever view the SPA router navigates to. Vendor libraries beyond the
critical shell (Mermaid, KaTeX, Plotly, ...) are loaded lazily by
``loader.js`` when a view first needs them.
"""

from __future__ import annotations

import json
import shutil
import zipfile
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
    # Ordered FALLBACK bases tried (after ``asset_prefix``) when a *lazy*
    # asset fails to load from the primary base. Lets one artifact find its
    # vendor tree whether it sits far away on a shared host
    # (``../../../_stage``) or bundled right next to the shell (``.`` /
    # ``_stage``). Relative entries are self-located against loader.js's own
    # URL, so document depth never matters. Critical shell libs (Vue/Quasar)
    # always use ``asset_prefix`` directly — they load before loader.js and
    # cannot probe.
    asset_fallbacks: list[str] = field(default_factory=list)
    # The route this particular HTML document represents. Baked into static
    # per-route ``index.html`` files by ``Stage.build`` so the SPA router can
    # subtract it from the served path and learn the deployment base — letting
    # a relocated/sub-path static bundle still match and mount its views. Empty
    # on the live server (served at the origin root), where it is not needed.
    current_route: str = ""
    routes: list[tuple[str, str]] = field(default_factory=list)
    view_modules: dict[str, str | dict[str, str]] = field(default_factory=dict)
    extra_head: str = ""
    extra_body: str = ""
    preload_views: list[str] = field(default_factory=list)
    dev_reload: bool = False
    dev_reload_prefix: str = "/_stage/dev"
    # When set, every asset URL gets an extra `/v<segment>/` between the
    # prefix and the category (e.g. /_stage/v2025-11/vendor/...). When
    # empty (default), URLs stay unversioned — same as the current bundle.
    # Caller pre-resolves this in Stage by comparing the app's pinned
    # lib_version to the installed LIB_VERSION.
    lib_version_segment: str = ""
    # Stamped into window.__stageLibVersion for self-reporting / debug.
    # Always reflects the bundle the page is actually loading.
    lib_version: str = ""
    # When True, injects the iframe→parent debug bridge so a host runner
    # can mirror console.* output, eval JS, and introspect loaded
    # extensions. Stage flips this on when LLMING_STAGE_DEBUG is set.
    debug_bridge: bool = False
    # Enables client-side Debug Actions. Unlike the iframe bridge, this
    # does not require a parent origin; it is gated by server debug mode.
    debug_enabled: bool = False
    # Exact parent origin allowed to drive that bridge. Empty disables the
    # iframe bridge even when process debug mode is on.
    debug_parent_origin: str = ""


def render_shell(config: ShellConfig) -> str:
    """Render the SPA shell HTML document."""
    def _with_segment(p: str) -> str:
        p = p.rstrip("/")
        return f"{p}/v{config.lib_version_segment}" if config.lib_version_segment else p

    prefix = _with_segment(config.asset_prefix)
    fallback_prefixes = [_with_segment(p) for p in config.asset_fallbacks if p.strip()]
    runtime_cache_bust = config.dev_reload or config.debug_enabled
    loader_url = _static_runtime_url(prefix, "loader.js", cache_bust=runtime_cache_bust)
    router_url = _static_runtime_url(prefix, "router.js", cache_bust=runtime_cache_bust)
    # Lazy assets (and view modules) are registered as paths RELATIVE to the
    # asset base, so loader.js can re-anchor them via self-location / fallback
    # without double-prefixing. Strip the primary prefix here.
    view_registrations_js = "\n".join(
        _view_registration_js(name, entry, prefix)
        for name, entry in config.view_modules.items()
    )
    # When fallbacks are configured, hand loader.js the ordered candidate
    # list; otherwise keep the single-base form (back-compat, identical
    # output for the default /_stage deployment).
    bases_js = ""
    if fallback_prefixes:
        candidates = json.dumps([prefix, *fallback_prefixes])
        bases_js = f"\nwindow.__stageBases = {candidates};"
    if config.current_route:
        bases_js += f"\nwindow.__stageRoute = {_js_str(config.current_route)};"
    routes_js = "\n".join(
        f"  window.__stageRouter.register({_js_str(p)}, {_js_str(v)});"
        for p, v in config.routes
    )
    preload_js = "\n".join(
        f"  window.__stage.load({_js_str(v)}).catch((e) => console.error(e));"
        for v in config.preload_views
    )
    dev_reload_html = dev_reload_head(config.dev_reload_prefix) if config.dev_reload else ""
    debug_bridge_html = (
        _debug_bridge_script(config.debug_parent_origin)
        if config.debug_bridge and config.debug_parent_origin
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_html_escape(config.title)}</title>
<link rel="stylesheet" href="{prefix}/fonts/fonts.css">
<link rel="stylesheet" href="{prefix}/vendor/quasar.prod.css">
<script>window.__stageBase = {_js_str(prefix)};{bases_js}
window.__stageLibVersion = {_js_str(config.lib_version)};
window.__stageDebug = {{
  enabled: {str(bool(config.debug_enabled)).lower()},
  modules: {{}}
}};</script>
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
{debug_bridge_html}
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
<script src="{loader_url}"></script>
<script src="{router_url}"></script>
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


# When ``LLMING_STAGE_DEBUG=1`` and ``LLMING_STAGE_DEBUG_PARENT_ORIGIN``
# are both set, this script ships inside every shell render. It activates
# only when the page is loaded inside an iframe by that exact parent
# origin. The bridge mirrors console.* calls and accepts eval/extensions
# queries from the configured runner.
def _debug_bridge_script(parent_origin: str) -> str:
    return """<script>
(function () {
  if (window.parent === window.self) return;
  var SRC = 'llming-stage-bridge';
  var ALLOWED = __PARENT_ORIGIN__.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
  var TGT = '';
  try {
    var refOrigin = new URL(document.referrer).origin;
    if (ALLOWED.indexOf(refOrigin) >= 0) TGT = refOrigin;
  } catch (_) {}
  if (!TGT) return;
  ['log','info','warn','error','debug'].forEach(function (level) {
    var orig = console[level].bind(console);
    console[level] = function () {
      var args = Array.prototype.slice.call(arguments);
      orig.apply(null, args);
      try {
        var text = args.map(function (a) {
          if (typeof a === 'string') return a;
          try { return JSON.stringify(a); } catch (_) { return String(a); }
        }).join(' ');
        window.parent.postMessage({source: SRC, type: 'console',
          level: level, text: text, ts: Date.now()}, TGT);
      } catch (_) {}
    };
  });
  window.addEventListener('error', function (ev) {
    try {
      window.parent.postMessage({source: SRC, type: 'console',
        level: 'error',
        text: (ev.message || 'error') + ' @ ' + (ev.filename || '?') + ':' + (ev.lineno || 0),
        ts: Date.now()}, TGT);
    } catch (_) {}
  });
  window.addEventListener('message', function (ev) {
    // Only accept messages from the actual parent window and from the
    // exact origin configured by LLMING_STAGE_DEBUG_PARENT_ORIGIN.
    if (ev.source !== window.parent) return;
    if (ev.origin !== TGT) return;
    var m = ev.data;
    if (!m || m.source !== 'llming-stage-runner') return;
    if (m.type === 'eval') {
      var ok = true, result, error;
      try {
        var f = new Function('return (' + m.code + ');');
        result = f();
        if (result && typeof result.then === 'function') {
          result.then(function (r) {
            var stringify;
            try { stringify = (r && typeof r === 'object') ? JSON.stringify(r) : String(r); }
            catch (_) { stringify = String(r); }
            window.parent.postMessage({source: SRC, type: 'eval-result',
              id: m.id, ok: true, result: stringify}, TGT);
          }, function (e) {
            window.parent.postMessage({source: SRC, type: 'eval-result',
              id: m.id, ok: false, error: String(e)}, TGT);
          });
          return;
        }
        var stringify;
        try { stringify = (result && typeof result === 'object') ? JSON.stringify(result) : String(result); }
        catch (_) { stringify = String(result); }
        result = stringify;
      } catch (e) { ok = false; error = String(e); }
      window.parent.postMessage({source: SRC, type: 'eval-result',
        id: m.id, ok: ok, result: result, error: error}, TGT);
      return;
    }
    if (m.type === 'extensions') {
      var loaded = (window.__stage && window.__stage.loaded)
        ? Array.from(window.__stage.loaded) : [];
      var versions = {};
      if (window.Vue) versions.vue = window.Vue.version;
      if (window.Quasar) versions.quasar = window.Quasar.version;
      if (window.echarts) versions.echarts = window.echarts.version;
      if (window.Plotly) versions.plotly = window.Plotly.version;
      if (window.mermaid) versions.mermaid = window.mermaid.version;
      if (window.marked) versions.marked = window.marked.version;
      if (window.THREE) versions.three = 'r' + window.THREE.REVISION;
      if (window.DOMPurify) versions.dompurify = window.DOMPurify.version;
      if (window.katex) versions.katex = window.katex.version;
      window.parent.postMessage({source: SRC, type: 'extensions-result',
        id: m.id, loaded: loaded, versions: versions,
        stage_base: window.__stageBase, stage_lib_version: window.__stageLibVersion}, TGT);
      return;
    }
    if (m.type === 'debug-actions') {
      var debug = window.__stage && window.__stage.debug;
      var snapshot = debug && debug.snapshot ? debug.snapshot() : {
        enabled: false, actions: [], flows: [], pinned: [], runOnce: [], runAlways: [], recent: []
      };
      Promise.resolve(snapshot).then(function (value) {
        window.parent.postMessage({source: SRC, type: 'debug-actions-result',
          id: m.id, snapshot: value}, TGT);
      }, function (err) {
        window.parent.postMessage({source: SRC, type: 'debug-actions-result',
          id: m.id, snapshot: {enabled: false, actions: [], flows: [], pinned: [],
            runOnce: [], runAlways: [], recent: [], error: String(err && err.message || err)}}, TGT);
      });
      return;
    }
    if (m.type === 'debug-run') {
      var dbg = window.__stage && window.__stage.debug;
      if (!dbg || !dbg.runRequest) {
        window.parent.postMessage({source: SRC, type: 'debug-run-result',
          id: m.id, ok: false, error: 'debug actions unavailable'}, TGT);
        return;
      }
      dbg.runRequest(m.request).then(function (result) {
        window.parent.postMessage({source: SRC, type: 'debug-run-result',
          id: m.id, ok: true, result: result || {}}, TGT);
      }, function (err) {
        window.parent.postMessage({source: SRC, type: 'debug-run-result',
          id: m.id, ok: false, error: String(err && err.message || err)}, TGT);
      });
      return;
    }
    if (m.type === 'debug-config') {
      var d = window.__stage && window.__stage.debug;
      if (!d || !d.configure) {
        window.parent.postMessage({source: SRC, type: 'debug-config-result',
          id: m.id, ok: false, error: 'debug actions unavailable'}, TGT);
        return;
      }
      d.configure(m.request).then(function (snapshot) {
        window.parent.postMessage({source: SRC, type: 'debug-config-result',
          id: m.id, ok: true, snapshot: snapshot}, TGT);
      }, function (err) {
        window.parent.postMessage({source: SRC, type: 'debug-config-result',
          id: m.id, ok: false, error: String(err && err.message || err)}, TGT);
      });
      return;
    }
  });
  try {
    window.parent.postMessage({source: SRC, type: 'ready',
      stage_base: window.__stageBase, stage_lib_version: window.__stageLibVersion}, TGT);
  } catch (_) {}
})();
</script>""".replace("__PARENT_ORIGIN__", _js_str(parent_origin))


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


def _static_runtime_url(prefix: str, name: str, *, cache_bust: bool) -> str:
    url = f"{prefix}/{name}"
    if not cache_bust:
        return url
    try:
        stamp = int((_STATIC_ROOT / name).stat().st_mtime)
    except OSError:
        stamp = 0
    return f"{url}?v={stamp}"


def _rebase_under_prefix(url: str, prefix: str) -> str:
    """Make *url* relative to the asset base by stripping a leading *prefix*.

    A view module served at ``{prefix}/app/home.js`` is registered as
    ``app/home.js`` so loader.js can re-anchor it (self-location / fallback).
    URLs on other mounts (absolute or a different prefix) pass through.
    """
    if not url or not prefix:
        return url
    head = prefix.rstrip("/") + "/"
    return url[len(head):] if url.startswith(head) else url


def _view_registration_js(name: str, entry: str | dict[str, str], prefix: str = "") -> str:
    if isinstance(entry, str):
        js_url = entry
        debug_url = ""
    else:
        js_url = entry.get("js", "")
        debug_url = entry.get("debug", "")
    js_url = _rebase_under_prefix(js_url, prefix)
    debug_url = _rebase_under_prefix(debug_url, prefix)
    lines = [f"  window.__stage.register({_js_str(name)}, {{js: {_js_str(js_url)}}});"]
    if debug_url:
        lines.append(
            f"  if (window.__stageDebug && window.__stageDebug.enabled) "
            f"window.__stageDebug.modules[{_js_str(name)}] = {_js_str(debug_url)};"
        )
    return "\n".join(lines)


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
    lib_version_segment: str = "",
) -> list[Route]:
    prefix = asset_prefix.rstrip("/")
    if lib_version_segment:
        prefix = f"{prefix}/v{lib_version_segment}"
    routes: list[Route] = []

    async def loader_js(request: Request) -> Response:
        handler = make_dir_handler(static_dir, cache_max_age=0)
        request.path_params["path"] = "loader.js"
        return await handler(request)

    async def router_js(request: Request) -> Response:
        handler = make_dir_handler(static_dir, cache_max_age=0)
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
    lib_version_segment: str = "",
) -> None:
    """Mount the llming-stage asset routes onto *app*.

    Works with any app exposing ``app.router.routes`` (Starlette, FastAPI).
    By default, serves the bundled vendor libs, fonts, locale packs, and
    icon/emoji archives from the installed package. Override paths for
    development or to swap in alternate asset sets.

    When ``lib_version_segment`` is non-empty, routes are registered under
    ``{asset_prefix}/v{lib_version_segment}/...`` instead of the default
    unversioned tree — used by ``Stage`` when the app pins an older bundle.
    """
    # Per-app+prefix+version dedupe so multiple mount_assets() callers
    # (e.g. one direct + one via Stage) don't double-register routes.
    state = getattr(app, "state", None)
    flag = f"llming_stage_assets_mounted_{asset_prefix}_v{lib_version_segment}"
    if state is not None and getattr(state, flag, False):
        return
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
        lib_version_segment=lib_version_segment,
    )
    for route in routes:
        app.router.routes.append(route)
    if state is not None:
        setattr(state, flag, True)


_ASSET_CATEGORIES = ("vendor", "fonts", "lang", "icons", "emoji", "tabler", "llming-com")


def export_package_assets(
    target: Path,
    *,
    write_manifest: bool = True,
) -> None:
    """Dump the installed package's vendor bundle into *target*.

    Whole-snapshot dump (vendor + fonts + lang + llming-com client + extracted
    icon/emoji/tabler archives + loader.js + router.js). Partial dumps are
    not supported — the operator places the result wherever they want it on
    the shared host (e.g. ``/var/www/_stage/`` for the current bundle or
    ``/var/www/_stage/v2026-05/`` to archive an older one).

    When *write_manifest* is true, a ``manifest.json`` is written alongside
    the assets containing ``lib_version``, ``pkg_version``, and the list of
    categories present. The manifest is purely for operator-side auditing;
    nothing at runtime reads it.
    """
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(_STATIC_ROOT, target, dirs_exist_ok=True)
    shutil.copytree(_VENDOR_ROOT, target / "vendor", dirs_exist_ok=True)
    shutil.copytree(_FONTS_ROOT, target / "fonts", dirs_exist_ok=True)
    shutil.copytree(_LANG_ROOT, target / "lang", dirs_exist_ok=True)
    shutil.copytree(_llming_com_static_dir(), target / "llming-com", dirs_exist_ok=True)
    archives = {
        "icons": _ASSETS_ROOT / "phosphor-icons.zip",
        "emoji": _ASSETS_ROOT / "noto-emoji.zip",
        "tabler": _ASSETS_ROOT / "tabler-icons.zip",
    }
    for dirname, archive in archives.items():
        if archive.exists():
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(target / dirname)
    if write_manifest:
        # Late import to avoid a circular reference at package init time.
        from . import LIB_VERSION, __version__

        manifest = {
            "lib_version": LIB_VERSION,
            "pkg_version": __version__,
            "categories": list(_ASSET_CATEGORIES),
        }
        (target / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )


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
