"""End-to-end checks for flexible asset-base resolution.

Builds static bundles with :meth:`Stage.build` in different layouts, serves
each with a plain static file server (no llming-com backend — the views are
pure templates), and drives a real browser to prove the shell boots and lazy
libraries load in every layout:

  1. Relative prefix + self-location — a relocatable bundle served from a
     sub-path still boots and lazy-loads (Steps 1 & 2).
  2. Deep route — a per-route ``index.html`` written several levels down
     resolves its depth-adjusted prefix (Step 2).
  3. Candidate fallback — a lazy lib missing from the primary base is fetched
     from a configured fallback base (Step 3).
  4. Single-file inline — one self-contained ``index.html`` boots and lazy-
     loads with zero network requests for the library (Step 4).
"""

from __future__ import annotations

import functools
import shutil
import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

import pytest
from playwright.sync_api import Page, expect

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HELLO_VUE = REPO_ROOT / "samples" / "hello_world" / "home.vue"


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


class _Served:
    def __init__(self, base: str, requests: list[tuple[str, int]]):
        self.base = base
        self.requests = requests


@pytest.fixture
def serve():
    """Factory: serve a directory over HTTP, recording every response."""
    servers: list[ThreadingHTTPServer] = []
    requests: list[tuple[str, int]] = []

    class _Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):  # silence
            pass

        def send_response(self, code, message=None):
            requests.append((self.path, code))
            super().send_response(code, message)

    def _start(directory: Path) -> _Served:
        port = _free_port()
        handler = functools.partial(_Handler, directory=str(directory))
        httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
        servers.append(httpd)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return _Served(f"http://127.0.0.1:{port}", requests)

    yield _start
    for httpd in servers:
        httpd.shutdown()


def _build(tmp: Path, name: str, **build_kwargs) -> Path:
    """Build a hello-world Stage bundle into ``tmp/name`` and return it."""
    # Late import: building pulls in llming-com (mandatory dependency).
    from llming_stage import Stage

    stage = Stage(title="probe", root=str(HELLO_VUE.parent), dev_reload=False)
    stage.add_view("/", HELLO_VUE)
    stage.add_view("/reports/summary", HELLO_VUE, name="summary")
    out = tmp / name
    stage.build(out, **build_kwargs)
    return out


def _wait_critical(page: Page) -> dict:
    """Wait until the critical shell libs have booted, then report state.

    Critical libs (Vue, Quasar) loading proves the shell resolved its primary
    asset base; the SPA view actually mounting additionally depends on the
    client router's base path, which is a separate concern from asset
    resolution and intentionally not asserted here.
    """
    page.wait_for_function(
        "() => window.Vue && window.Quasar && window.__stage", timeout=20_000
    )
    return page.evaluate(
        "() => ({ vue: !!window.Vue, quasar: !!window.Quasar, base: window.__stage.base })"
    )


def _load_lib(page: Page, name: str) -> dict:
    return page.evaluate(
        """async (lib) => {
          try {
            await window.__stage.load(lib);
            return { ok: true, base: window.__stage.base, hasMarked: !!window.marked };
          } catch (e) { return { ok: false, error: String(e), base: window.__stage.base }; }
        }""",
        name,
    )


def test_relative_prefix_at_root(tmp_path, serve, page: Page) -> None:
    """Step 1: a RELATIVE asset prefix boots the shell, mounts the view (route
    '/' matches at root), and lazy-loads — the base is resolved relative to the
    document, not hard-coded to the origin root."""
    bundle = _build(tmp_path, "rel", asset_prefix="_stage")
    served = serve(bundle)

    page.goto(f"{served.base}/")
    expect(page.locator("#app-shell-view h1")).to_have_text("Hello world", timeout=20_000)
    result = _load_lib(page, "marked")
    assert result["ok"], result
    assert result["hasMarked"] is True
    assert result["base"] == f"{served.base}/_stage", result["base"]


def test_deep_route_depth_adjusted_and_self_located(tmp_path, serve, page: Page) -> None:
    """Steps 1+2: a per-route index.html two levels down loads its critical
    libs via the depth-adjusted prefix ('../../_stage'), loader.js self-locates,
    the SPA router subtracts the baked route to learn its base and MOUNTS the
    view, and lazy assets resolve — all without any asset 404."""
    bundle = _build(tmp_path, "deep", asset_prefix="_stage")
    deep = bundle / "reports" / "summary" / "index.html"
    assert deep.is_file()
    assert "../../_stage/vendor/vue.global.prod.js" in deep.read_text()
    assert "window.__stageRoute = '/reports/summary'" in deep.read_text()
    served = serve(bundle)

    # Directory URL (trailing slash) for a deep per-route file: the router must
    # normalize it and still mount the view.
    page.goto(f"{served.base}/reports/summary/")
    expect(page.locator("#app-shell-view h1")).to_have_text("Hello world", timeout=20_000)
    state = _wait_critical(page)
    assert state["vue"] and state["quasar"], state
    # Depth-adjusted '../../_stage' resolved back to the origin-root bundle.
    assert state["base"] == f"{served.base}/_stage", state["base"]
    result = _load_lib(page, "marked")
    assert result["ok"], result
    assert result["hasMarked"] is True
    # No asset 404s (tailwind's own bare @imports are unrelated).
    bad = [(p, c) for p, c in served.requests if c == 404 and "/_stage/" in p]
    assert not bad, bad


def test_relocated_subpath_mounts_view(tmp_path, serve, page: Page) -> None:
    """Static-shipping principle: a relative bundle served from an UNEXPECTED
    sub-path ('/app/') still resolves its assets (self-location) AND mounts its
    views — the router subtracts the baked route to learn the '/app' base."""
    bundle = _build(tmp_path, "reloc", asset_prefix="_stage")
    # Relocate the whole bundle under /app/ by serving from a parent dir.
    root = tmp_path / "site"
    (root / "app").mkdir(parents=True)
    for item in bundle.iterdir():
        shutil.move(str(item), str(root / "app" / item.name))
    served = serve(root)

    # Root route of the relocated app.
    page.goto(f"{served.base}/app/")
    expect(page.locator("#app-shell-view h1")).to_have_text("Hello world", timeout=20_000)
    base = page.evaluate("() => window.__stage.base")
    assert base == f"{served.base}/app/_stage", base

    # Deep route of the relocated app (sub-path + depth + trailing slash).
    page.goto(f"{served.base}/app/reports/summary/")
    expect(page.locator("#app-shell-view h1")).to_have_text("Hello world", timeout=20_000)
    result = _load_lib(page, "marked")
    assert result["ok"] and result["hasMarked"], result
    bad = [(p, c) for p, c in served.requests if c == 404 and "_stage" in p]
    assert not bad, bad


def test_candidate_fallback_for_lazy_lib(tmp_path, serve, page: Page) -> None:
    """Step 3: a lazy lib absent from the primary base is fetched from a
    configured fallback base."""
    bundle = _build(tmp_path, "fb", asset_prefix="_stage", asset_fallbacks=["_shared"])
    primary = bundle / "_stage" / "vendor" / "marked.umd.js"
    shared = bundle / "_shared" / "vendor"
    shared.mkdir(parents=True)
    shutil.move(str(primary), str(shared / "marked.umd.js"))  # only in fallback now
    served = serve(bundle)

    page.goto(f"{served.base}/")
    _wait_critical(page)
    result = _load_lib(page, "marked")
    assert result["ok"], result
    assert result["hasMarked"] is True
    # The primary 404'd and the fallback served it.
    paths = {p for p, _ in served.requests}
    assert ("/_stage/vendor/marked.umd.js", 404) in served.requests, served.requests
    assert any(p == "/_shared/vendor/marked.umd.js" for p in paths), served.requests


def test_single_file_inline(tmp_path, serve, page: Page) -> None:
    """Step 4: one self-contained index.html boots, mounts the view, and
    lazy-loads with zero network requests for the library."""
    bundle = _build(tmp_path, "inline", inline=True, inline_max_bytes=200_000)
    assert [p.name for p in bundle.rglob("*") if p.is_file()] == ["index.html"]
    served = serve(bundle)

    page.goto(f"{served.base}/")
    expect(page.locator("#app-shell-view h1")).to_have_text("Hello world", timeout=20_000)
    # Any script[src] present is a blob: URL minted from an inlined payload —
    # never a network reference.
    srcs = page.eval_on_selector_all(
        "script[src]", "els => els.map(e => e.getAttribute('src'))"
    )
    assert all(s.startswith("blob:") for s in srcs), srcs
    result = _load_lib(page, "marked")
    assert result["ok"], result
    assert result["hasMarked"] is True
    # The library resolved from an inlined blob — nothing hit the network for it.
    assert not any("/vendor/" in p for p, _ in served.requests), served.requests
    # Only the document itself was fetched (plus tailwind's unrelated bare imports).
    asset_hits = [p for p, _ in served.requests if "/_stage/" in p or "/app/" in p]
    assert not asset_hits, asset_hits
