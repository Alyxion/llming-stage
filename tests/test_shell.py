"""Integration tests for the shell and bundled-asset serving."""

from __future__ import annotations

from starlette.testclient import TestClient

from llming_stage import ShellConfig, render_shell


def test_loader_js_is_served(client: TestClient) -> None:
    r = client.get("/_stage/loader.js")
    assert r.status_code == 200
    assert "window.__stage" in r.text
    assert r.headers["content-type"].startswith("application/javascript")


def test_router_js_is_served(client: TestClient) -> None:
    r = client.get("/_stage/router.js")
    assert r.status_code == 200
    assert "window.__stageRouter" in r.text


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
