"""Integration tests for the shell and bundled-asset serving."""

from __future__ import annotations

from starlette.testclient import TestClient

from llming_stage import ShellConfig, render_shell


def test_loader_js_is_served(client: TestClient) -> None:
    r = client.get("/_stage/loader.js")
    assert r.status_code == 200
    assert "window.__stage" in r.text
    assert r.headers["content-type"].startswith("application/javascript")
    assert r.headers["cache-control"] == "no-store"


def test_router_js_is_served(client: TestClient) -> None:
    r = client.get("/_stage/router.js")
    assert r.status_code == 200
    assert "window.__stageRouter" in r.text
    assert r.headers["cache-control"] == "no-store"


def test_vue_is_served(client: TestClient) -> None:
    r = client.get("/_stage/vendor/vue.global.prod.js")
    assert r.status_code == 200
    assert int(r.headers["content-length"]) > 10_000


def test_quasar_css_is_served(client: TestClient) -> None:
    r = client.get("/_stage/vendor/quasar.prod.css")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/css")


def test_tailwind_browser_bundle_is_served(client: TestClient) -> None:
    r = client.get("/_stage/vendor/tailwindcss.browser.global.js")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript")
    assert "@tailwind utilities" in r.text


def test_fonts_css_is_served(client: TestClient) -> None:
    r = client.get("/_stage/fonts/fonts.css")
    assert r.status_code == 200
    assert "Roboto" in r.text


def test_phosphor_icon_served_from_zip(client: TestClient) -> None:
    # `acorn` is a stable real phosphor icon in the regular weight.
    r = client.get("/_stage/icons/regular/acorn.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert r.text.lstrip().startswith("<svg")


def test_tabler_icon_served_from_zip(client: TestClient) -> None:
    r = client.get("/_stage/tabler/outline/home.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert r.text.lstrip().startswith("<svg")


def test_katex_font_served_with_woff2_mime(client: TestClient) -> None:
    r = client.get("/_stage/fonts/katex/KaTeX_Main-Regular.woff2")
    assert r.status_code == 200
    assert r.headers["content-type"] == "font/woff2"
    # Real woff2 file, not a stub.
    assert int(r.headers["content-length"]) > 5000


def test_katex_css_uses_relative_path_to_unified_fonts(client: TestClient) -> None:
    r = client.get("/_stage/vendor/katex.min.css")
    assert r.status_code == 200
    # CSS at /_stage/vendor/katex.min.css references /_stage/fonts/katex/...
    # via a relative `url(../fonts/katex/...)`.
    assert "url(../fonts/katex/" in r.text
    assert "url(fonts/" not in r.text


def test_llming_com_client_served(client: TestClient) -> None:
    r = client.get("/_stage/llming-com/llming-ws.js")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript")
    assert "LlmingWebSocket" in r.text


def test_shell_includes_llming_com_client(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "/_stage/llming-com/llming-ws.js" in r.text


def test_shell_is_served_at_root(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "<!doctype html>" in r.text
    assert "loader.js" in r.text
    assert "quasar.prod.css" in r.text
    assert "tailwindcss.browser.global.js" in r.text
    assert 'type="text/tailwindcss"' in r.text


def test_shell_is_served_for_unknown_paths(client: TestClient) -> None:
    r = client.get("/chat")
    assert r.status_code == 200
    assert "<!doctype html>" in r.text


def test_shell_renders_route_registrations() -> None:
    html = render_shell(
        ShellConfig(
            title="X",
            routes=[("/", "home"), ("/chat", "chat")],
            preload_views=["home"],
        )
    )
    assert "__stageRouter.register('/', 'home')" in html
    assert "__stageRouter.register('/chat', 'chat')" in html
    assert "__stage.load('home')" in html


def test_shell_escapes_title_html() -> None:
    html = render_shell(ShellConfig(title="<script>bad</script>"))
    assert "<script>bad</script>" not in html
    assert "&lt;script&gt;bad&lt;/script&gt;" in html


def test_shell_escapes_js_route_value() -> None:
    html = render_shell(ShellConfig(routes=[("/</script>", "home")]))
    # The injected `<` in the route value must be escaped as `\x3c` — that
    # way the HTML parser does not see a real `</script>` tag and close the
    # script block prematurely. (Real `</script>` tags that actually close
    # the shell's own script blocks are still expected in the document.)
    assert "register('/</script>'" not in html
    assert "register('/\\x3c/script\\x3e'" in html


def test_shell_never_renders_visible_debug_chrome() -> None:
    html = render_shell(ShellConfig(dev_reload=True, debug_enabled=True))

    assert 'id="stage-controls"' not in html
    assert 'id="stage-debug-toggle"' not in html
    assert 'data-test="stage-restart"' not in html
    assert "window.__stageDebug" in html
    assert 'src="/_stage/loader.js?v=' in html
    assert 'src="/_stage/router.js?v=' in html


def test_debug_bridge_requires_configured_parent_origin() -> None:
    without_origin = render_shell(ShellConfig(debug_bridge=True))
    assert "llming-stage-bridge" not in without_origin

    html = render_shell(
        ShellConfig(
            debug_bridge=True,
            debug_parent_origin="http://127.0.0.1:8000",
        )
    )
    assert "llming-stage-bridge" in html
    assert "http://127.0.0.1:8000" in html
    assert "postMessage({source: SRC, type: 'ready'" in html
    assert "var TGT = '*'" not in html
    assert "ev.origin !== TGT" in html


# --- Vendor-bundle version pinning ---------------------------------------


def test_shell_unversioned_when_no_segment() -> None:
    """No lib_version_segment → URLs identical to today (regression)."""
    import re

    html = render_shell(ShellConfig(lib_version="2026-05"))
    # asset_prefix default is "/_stage"; no /v<YYYY-MM>/ segment in any URL.
    assert re.search(r"/_stage/v\d{4}-\d{2}", html) is None
    assert 'href="/_stage/fonts/fonts.css"' in html
    assert 'src="/_stage/vendor/vue.global.prod.js"' in html
    assert 'src="/_stage/llming-com/llming-ws.js"' in html
    assert '"three": "/_stage/vendor/three.module.min.js"' in html
    assert '"three/addons/": "/_stage/vendor/"' in html
    assert "window.__stageBase = '/_stage'" in html
    assert "window.__stageLibVersion = '2026-05'" in html


def test_shell_versioned_when_segment_set() -> None:
    """lib_version_segment='2024-01' → /v2024-01/ between prefix and category."""
    html = render_shell(
        ShellConfig(lib_version_segment="2024-01", lib_version="2024-01")
    )
    assert 'href="/_stage/v2024-01/fonts/fonts.css"' in html
    assert 'href="/_stage/v2024-01/vendor/quasar.prod.css"' in html
    assert 'src="/_stage/v2024-01/vendor/vue.global.prod.js"' in html
    assert 'src="/_stage/v2024-01/vendor/quasar.umd.prod.js"' in html
    assert 'src="/_stage/v2024-01/vendor/tailwindcss.browser.global.js"' in html
    assert 'src="/_stage/v2024-01/llming-com/llming-ws.js"' in html
    assert 'src="/_stage/v2024-01/loader.js"' in html
    assert 'src="/_stage/v2024-01/router.js"' in html
    assert '"three": "/_stage/v2024-01/vendor/three.module.min.js"' in html
    assert '"three/addons/": "/_stage/v2024-01/vendor/"' in html
    assert "window.__stageBase = '/_stage/v2024-01'" in html
    assert "window.__stageLibVersion = '2024-01'" in html


def test_shell_versioned_with_custom_asset_prefix() -> None:
    """Combining asset_prefix and lib_version_segment composes correctly."""
    html = render_shell(
        ShellConfig(
            asset_prefix="/shared/_stage",
            lib_version_segment="2024-01",
            lib_version="2024-01",
        )
    )
    assert 'src="/shared/_stage/v2024-01/loader.js"' in html
    assert "window.__stageBase = '/shared/_stage/v2024-01'" in html


def test_export_package_assets_writes_full_tree(tmp_path) -> None:
    from llming_stage import LIB_VERSION, __version__
    from llming_stage.shell import export_package_assets

    target = tmp_path / "_stage_dump"
    export_package_assets(target)

    # Per-category dirs exist
    for cat in ("vendor", "fonts", "lang", "llming-com", "icons", "emoji", "tabler"):
        assert (target / cat).is_dir(), f"missing category: {cat}"
    # Loader + router copied from static root
    assert (target / "loader.js").is_file()
    assert (target / "router.js").is_file()
    # Manifest written
    manifest_path = target / "manifest.json"
    assert manifest_path.is_file()
    import json

    manifest = json.loads(manifest_path.read_text())
    assert manifest["lib_version"] == LIB_VERSION
    assert manifest["pkg_version"] == __version__
    assert set(manifest["categories"]) == {
        "vendor", "fonts", "lang", "icons", "emoji", "tabler", "llming-com",
    }


def test_export_package_assets_no_manifest(tmp_path) -> None:
    from llming_stage.shell import export_package_assets

    target = tmp_path / "_stage_no_manifest"
    export_package_assets(target, write_manifest=False)
    assert not (target / "manifest.json").exists()
    assert (target / "vendor").is_dir()
