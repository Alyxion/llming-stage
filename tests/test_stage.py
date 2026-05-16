"""Tests for the Stage OOP helper."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.testclient import TestClient

from llming_stage import Stage, StageSession, VueResponse
from llming_stage.cli import build_app


def test_stage_view_serves_vue_and_shell(tmp_path: Path) -> None:
    (tmp_path / "home.vue").write_text(
        "<template><main id='hello'>Hello stage</main></template>",
        encoding="utf-8",
    )
    app = Starlette()
    Stage(app, root=tmp_path).add_view("/", "home.vue")

    with TestClient(app) as client:
        shell = client.get("/")
        view = client.get("/_stage/app/home.js")

    assert shell.status_code == 200
    assert "__stageRouter.register('/', 'home')" in shell.text
    assert "/_stage/dev/client.js" in shell.text
    assert view.status_code == 200
    assert "Vue.createApp" in view.text
    assert "Hello stage" in view.text


def test_stage_can_create_default_fastapi_app(tmp_path: Path) -> None:
    (tmp_path / "hello.vue").write_text(
        "<template><main>Hello from default FastAPI</main></template>",
        encoding="utf-8",
    )
    stage = Stage(root=tmp_path, title="Hello default", openapi_url=None)

    stage.add_view("/", "hello.vue")

    with TestClient(stage.app) as client:
        shell = client.get("/")
        view = client.get("/_stage/app/home.js")

    assert getattr(stage.app, "title") == "Hello default"
    assert shell.status_code == 200
    assert view.status_code == 200
    assert "Hello from default FastAPI" in view.text


def test_stage_default_fastapi_rejects_unknown_kwargs(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="unknown FastAPI keyword"):
        Stage(root=tmp_path, definitely_not_fastapi=True)


def test_stage_view_uses_explicit_source_filename(tmp_path: Path) -> None:
    (tmp_path / "home.vue").write_text(
        "<template><main>Home by convention</main></template>",
        encoding="utf-8",
    )
    (tmp_path / "chat.vue").write_text(
        "<template><main>Chat by convention</main></template>",
        encoding="utf-8",
    )
    app = Starlette()
    stage = Stage(app, root=tmp_path)

    stage.add_view("/", "home.vue")
    stage.add_view("/chat", "chat.vue")

    with TestClient(app) as client:
        shell = client.get("/")
        home = client.get("/_stage/app/home.js")
        chat = client.get("/_stage/app/chat.js")

    assert shell.status_code == 200
    assert "__stageRouter.register('/', 'home')" in shell.text
    assert "__stageRouter.register('/chat', 'chat')" in shell.text
    assert home.status_code == 200
    assert "Home by convention" in home.text
    assert chat.status_code == 200
    assert "Chat by convention" in chat.text


def test_stage_add_view_requires_source_filename(tmp_path: Path) -> None:
    stage = Stage(root=tmp_path)

    with pytest.raises(TypeError):
        stage.add_view("/")  # type: ignore[call-arg]


def test_cli_build_app_maps_single_vue_file_to_home(tmp_path: Path) -> None:
    view = tmp_path / "hello.vue"
    view.write_text(
        "<template><main>Single Vue file</main></template>",
        encoding="utf-8",
    )

    app = build_app(view, dev=False)

    with TestClient(app) as client:
        shell = client.get("/")
        module = client.get("/_stage/app/home.js")

    assert shell.status_code == 200
    assert "__stageRouter.register('/', 'home')" in shell.text
    assert module.status_code == 200
    assert "Single Vue file" in module.text


def test_cli_build_app_maps_single_vue_directory_to_home(tmp_path: Path) -> None:
    (tmp_path / "hello.vue").write_text(
        "<template><main>Single Vue directory</main></template>",
        encoding="utf-8",
    )

    app = build_app(tmp_path, dev=False)

    with TestClient(app) as client:
        shell = client.get("/")
        module = client.get("/_stage/app/home.js")

    assert shell.status_code == 200
    assert "__stageRouter.register('/', 'home')" in shell.text
    assert module.status_code == 200
    assert "Single Vue directory" in module.text


def test_stage_view_decorator_registers_generated_html(tmp_path: Path) -> None:
    app = Starlette()
    stage = Stage(app, root=tmp_path)

    @stage.view("/")
    def home() -> HTMLResponse:
        return HTMLResponse("<main id='generated'>Generated content</main>")

    with TestClient(app) as client:
        shell = client.get("/")
        view = client.get("/_stage/app/home.js")

    assert shell.status_code == 200
    assert "__stageRouter.register('/', 'home')" in shell.text
    assert view.status_code == 200
    assert "Generated content" in view.text


def test_stage_view_decorator_registers_generated_vue_template(tmp_path: Path) -> None:
    app = Starlette()
    stage = Stage(app, root=tmp_path)

    @stage.view("/")
    def home() -> VueResponse:
        return VueResponse("<main id='generated'>Generated Vue template</main>")

    with TestClient(app) as client:
        view = client.get("/_stage/app/home.js")

    assert view.status_code == 200
    assert "Vue.createApp" in view.text
    assert "Generated Vue template" in view.text


def test_stage_view_decorator_registers_generated_vue_sfc(tmp_path: Path) -> None:
    app = Starlette()
    stage = Stage(app, root=tmp_path)

    @stage.view("/")
    def home() -> VueResponse:
        return VueResponse(
            """
<template><main id="generated">{{ message }}</main></template>
<script>
export default {
  data() {
    return { message: "Generated Vue SFC" };
  },
};
</script>
"""
        )

    with TestClient(app) as client:
        view = client.get("/_stage/app/home.js")

    assert view.status_code == 200
    assert "Generated Vue SFC" in view.text
    assert "{{ message }}" in view.text


def test_stage_view_decorator_composes_vue_template_and_script(tmp_path: Path) -> None:
    app = Starlette()
    stage = Stage(app, root=tmp_path)

    @stage.view("/")
    def home() -> VueResponse:
        return VueResponse(
            template="<main>{{ message }}</main>",
            script='export default { data() { return { message: "Split Vue" }; } };',
        )

    with TestClient(app) as client:
        view = client.get("/_stage/app/home.js")

    assert view.status_code == 200
    assert "{{ message }}" in view.text
    assert "Split Vue" in view.text


def test_stage_view_decorator_composes_vue_template_and_script_paths(tmp_path: Path) -> None:
    template_path = tmp_path / "generated.html"
    script_path = tmp_path / "generated.js"
    template_path.write_text("<main>{{ message }}</main>", encoding="utf-8")
    script_path.write_text(
        'export default { data() { return { message: "Path Vue" }; } };',
        encoding="utf-8",
    )
    app = Starlette()
    stage = Stage(app, root=tmp_path)

    @stage.view("/")
    def home() -> VueResponse:
        return VueResponse(template_path=template_path, script_path=script_path)

    with TestClient(app) as client:
        view = client.get("/_stage/app/home.js")

    assert view.status_code == 200
    assert "{{ message }}" in view.text
    assert "Path Vue" in view.text


def test_stage_view_decorator_requires_returned_content(tmp_path: Path) -> None:
    app = Starlette()
    stage = Stage(app, root=tmp_path)

    @stage.view("/")
    def home() -> None:
        return None

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/_stage/app/home.js")

    assert response.status_code == 500


def test_stage_view_decorator_rejects_raw_string_return(tmp_path: Path) -> None:
    app = Starlette()
    stage = Stage(app, root=tmp_path)

    @stage.view("/")
    def home() -> str:
        return "<main>Raw string</main>"

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/_stage/app/home.js")

    assert response.status_code == 500


def test_stage_view_inlines_relative_vue_components(tmp_path: Path) -> None:
    (tmp_path / "Drawer.vue").write_text(
        """
<template><aside>{{ title }}</aside></template>
<script>
export default {
  name: "drawer",
  data() { return { title: "Drawer" }; },
  methods: { open() { this.title = "Open"; } },
};
</script>
""",
        encoding="utf-8",
    )
    (tmp_path / "home.vue").write_text(
        """
<template><Drawer stage-id="drawer" /></template>
<script>
import Drawer from "./Drawer.vue";
export default { components: { Drawer } };
</script>
""",
        encoding="utf-8",
    )
    app = Starlette()
    Stage(app, root=tmp_path).add_view("/", "home.vue")

    with TestClient(app) as client:
        view = client.get("/_stage/app/home.js")

    assert view.status_code == 200
    assert "const Drawer = Object.assign" in view.text
    assert "stage-id" in view.text
    assert "open() { this.title = \"Open\"; }" in view.text


def test_stage_session_mounts_default_routes(tmp_path: Path) -> None:
    app = Starlette()
    session = Stage(app, root=tmp_path).session(command_prefix=None)

    paths = {getattr(route, "path", "") for route in app.router.routes}
    assert "/api/session" in paths
    assert "/ws/{session_id}" in paths
    assert isinstance(session, StageSession)


def test_stage_session_creates_namespaced_routers(tmp_path: Path) -> None:
    app = Starlette()
    session = Stage(app, root=tmp_path).session(command_prefix=None)

    counter = session.add_router("counter")
    admin = session.add_app_router("admin")

    @counter.handler("inc")
    async def inc(session) -> dict:
        return {"ok": True}

    @admin.handler("broadcast")
    async def broadcast(app) -> dict:
        return {"ok": True}

    assert counter.prefix == "counter"
    assert admin.prefix == "admin"
    assert "counter.inc" in session.session_router.build_dispatch_table()
    assert "admin.broadcast" in session.application_router.build_dispatch_table()


def test_stage_discover_maps_conventional_routes(tmp_path: Path) -> None:
    views = tmp_path / "views"
    views.mkdir()
    (views / "home.vue").write_text("<template>Home</template>", encoding="utf-8")
    (views / "chat.html").write_text("<main>Chat</main>", encoding="utf-8")
    users = views / "users"
    users.mkdir()
    (users / "[id].vue").write_text("<template>User</template>", encoding="utf-8")

    stage = Stage(Starlette(), root=tmp_path).discover()

    routes = {view.route for view in stage._views}
    assert routes == {"/", "/chat", "/users/:id"}


def test_stage_ensures_assets_once_for_same_app(tmp_path: Path) -> None:
    (tmp_path / "home.vue").write_text("<template>Home</template>", encoding="utf-8")
    app = Starlette()

    Stage(app, root=tmp_path).add_view("/", "home.vue")
    Stage(app, root=tmp_path).add_view("/other", "home.vue", name="other")

    asset_loader_routes = [
        route for route in app.router.routes if getattr(route, "path", "") == "/_stage/loader.js"
    ]
    dev_client_routes = [
        route for route in app.router.routes if getattr(route, "path", "") == "/_stage/dev/client.js"
    ]
    assert len(asset_loader_routes) == 1
    assert len(dev_client_routes) == 1


def test_stage_build_writes_static_shell_and_view(tmp_path: Path) -> None:
    (tmp_path / "views").mkdir()
    (tmp_path / "views" / "home.vue").write_text(
        "<template><main>Built</main></template>",
        encoding="utf-8",
    )
    stage = Stage(Starlette(), root=tmp_path, dev=False).discover()

    out = stage.build(tmp_path / "dist")

    assert (out / "index.html").is_file()
    assert (out / "_stage" / "app" / "home.js").is_file()
    assert (out / "_stage" / "loader.js").is_file()
    assert "/_stage/dev/client.js" not in (out / "index.html").read_text(encoding="utf-8")


def test_stage_root_accepts_file_path(tmp_path: Path) -> None:
    main_py = tmp_path / "main.py"
    main_py.write_text("", encoding="utf-8")

    stage = Stage(Starlette(), root=main_py)

    assert stage.root == tmp_path


# --- Vendor-bundle version pinning ---------------------------------------


def test_stage_unpinned_emits_unversioned_urls() -> None:
    import re

    from llming_stage import LIB_VERSION

    stage = Stage(Starlette(), dev=False)
    html = stage._render_shell(dev_reload=False)
    assert re.search(r"/_stage/v\d{4}-\d{2}", html) is None
    assert f"window.__stageLibVersion = '{LIB_VERSION}'" in html


def test_stage_pinned_to_current_lib_version_does_not_rewrite() -> None:
    """Pinning to the installed bundle is a no-op — URLs stay unversioned."""
    import re

    from llming_stage import LIB_VERSION

    stage = Stage(Starlette(), dev=False, lib_version=LIB_VERSION)
    assert stage._lib_version_segment == ""
    html = stage._render_shell(dev_reload=False)
    assert re.search(r"/_stage/v\d{4}-\d{2}", html) is None
    assert f"window.__stageLibVersion = '{LIB_VERSION}'" in html


def test_stage_pinned_older_lib_version_rewrites_urls() -> None:
    stage = Stage(Starlette(), dev=False, lib_version="2024-01")
    assert stage._lib_version_segment == "2024-01"
    html = stage._render_shell(dev_reload=False)
    assert 'src="/_stage/v2024-01/vendor/vue.global.prod.js"' in html
    assert 'src="/_stage/v2024-01/loader.js"' in html
    assert '"three": "/_stage/v2024-01/vendor/three.module.min.js"' in html
    assert '"three/addons/": "/_stage/v2024-01/vendor/"' in html
    assert "window.__stageBase = '/_stage/v2024-01'" in html
    assert "window.__stageLibVersion = '2024-01'" in html


def test_stage_rejects_malformed_lib_version() -> None:
    import pytest

    with pytest.raises(ValueError, match="calendar format"):
        Stage(Starlette(), lib_version="../etc/passwd")
    with pytest.raises(ValueError, match="calendar format"):
        Stage(Starlette(), lib_version="0.1.1")  # semver, not calendar
    with pytest.raises(ValueError, match="calendar format"):
        Stage(Starlette(), lib_version="2026/05")


def test_stage_accepts_in_month_refresh_suffix() -> None:
    stage = Stage(Starlette(), dev=False, lib_version="2024-01-02")
    assert stage._lib_version_segment == "2024-01-02"


def test_stage_build_refuses_pinned_older_bundle(tmp_path: Path) -> None:
    import pytest

    (tmp_path / "views").mkdir()
    (tmp_path / "views" / "home.vue").write_text(
        "<template><main>x</main></template>",
        encoding="utf-8",
    )
    stage = Stage(Starlette(), root=tmp_path, dev=False, lib_version="2024-01").discover()
    with pytest.raises(RuntimeError, match="pinned older bundle"):
        stage.build(tmp_path / "dist")


def test_stage_pinned_older_bundle_does_not_mount_current_bytes_under_old_path() -> None:
    stage = Stage(Starlette(), dev=False, lib_version="2024-01")
    paths = [getattr(r, "path", "") for r in stage.app.router.routes]
    assert "/_stage/v2024-01/vendor/{path:path}" not in paths
    assert "/_stage/v2024-01/loader.js" not in paths
    assert "/_stage/v2024-01/llming-com/{path:path}" not in paths


def test_pinned_and_current_stages_can_share_one_app() -> None:
    app = Starlette()
    Stage(app, dev=False, lib_version="2024-01")
    Stage(app, dev=False)
    paths = [getattr(r, "path", "") for r in app.router.routes]
    assert "/_stage/v2024-01/vendor/{path:path}" not in paths
    assert "/_stage/vendor/{path:path}" in paths


def test_stage_session_debug_routes_not_mounted_without_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import FastAPI

    monkeypatch.delenv("LLMING_STAGE_DEBUG", raising=False)
    app = FastAPI()
    Stage(app, dev=False).session()

    paths = [getattr(r, "path", "") for r in app.router.routes]
    assert "/cmd/sessions/{session_id}/debug.state" not in paths
    assert "/cmd/sessions/{session_id}/debug.ws_dispatch" not in paths


def test_stage_session_debug_routes_require_matching_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import FastAPI

    monkeypatch.setenv("LLMING_STAGE_DEBUG", "1")
    app = FastAPI()
    Stage(app, dev=False).session()

    owner = TestClient(app)
    session_id = owner.get("/api/session").json()["sessionId"]

    assert owner.get(f"/cmd/sessions/{session_id}/debug.state").status_code == 200
    assert (
        TestClient(app).get(f"/cmd/sessions/{session_id}/debug.state").status_code
        == 401
    )


def test_stage_session_hint_cannot_mint_cookie_for_existing_session() -> None:
    from fastapi import FastAPI

    app = FastAPI()
    Stage(app, dev=False).session()

    owner = TestClient(app)
    session_id = owner.get("/api/session").json()["sessionId"]

    attacker = TestClient(app)
    stolen = attacker.get(f"/api/session?session={session_id}").json()["sessionId"]
    assert stolen != session_id

    reloaded = owner.get(f"/api/session?session={session_id}").json()["sessionId"]
    assert reloaded == session_id


def test_stage_session_does_not_install_known_auth_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import FastAPI

    monkeypatch.delenv("LLMING_AUTH_SECRET", raising=False)
    app = FastAPI()
    Stage(app, dev=False).session()

    assert os.environ.get("LLMING_AUTH_SECRET") is None


def test_stage_session_websocket_requires_matching_cookie() -> None:
    from fastapi import FastAPI

    app = FastAPI()
    Stage(app, dev=False).session()

    owner = TestClient(app)
    session_id = owner.get("/api/session").json()["sessionId"]

    attacker = TestClient(app)
    with pytest.raises(Exception):
        with attacker.websocket_connect(f"/ws/{session_id}") as ws:
            ws.receive_json()


def test_stage_session_auth_cookie_secure_on_https() -> None:
    from fastapi import FastAPI

    app = FastAPI()
    Stage(app, dev=False).session()

    with TestClient(app, base_url="https://example.test") as client:
        response = client.get("/api/session")

    cookie = response.headers["set-cookie"]
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie


def test_stage_session_auth_cookie_not_secure_on_http() -> None:
    from fastapi import FastAPI

    app = FastAPI()
    Stage(app, dev=False).session()

    with TestClient(app, base_url="http://example.test") as client:
        response = client.get("/api/session")

    assert "Secure" not in response.headers["set-cookie"]


def test_legacy_sample_bootstrap_websocket_requires_matching_cookie(tmp_path: Path) -> None:
    from samples._common import bootstrap

    (tmp_path / "home.vue").write_text(
        "<template><main>legacy</main></template>",
        encoding="utf-8",
    )
    app, _, _ = bootstrap(
        app_name="legacy_auth_test",
        title="legacy",
        routes=[("/", "home")],
        view_sources={"home": "home.vue"},
        static_dir=tmp_path,
    )

    owner = TestClient(app)
    session_id = owner.get("/api/session").json()["sessionId"]

    attacker = TestClient(app)
    with pytest.raises(Exception):
        with attacker.websocket_connect(f"/ws/{session_id}") as ws:
            ws.receive_json()


def test_legacy_sample_bootstrap_auth_cookie_secure_on_https(tmp_path: Path) -> None:
    from samples._common import bootstrap

    (tmp_path / "home.vue").write_text(
        "<template><main>legacy</main></template>",
        encoding="utf-8",
    )
    app, _, _ = bootstrap(
        app_name="legacy_secure_cookie_test",
        title="legacy",
        routes=[("/", "home")],
        view_sources={"home": "home.vue"},
        static_dir=tmp_path,
    )

    with TestClient(app, base_url="https://example.test") as client:
        response = client.get("/api/session")

    assert "Secure" in response.headers["set-cookie"]


def test_stage_session_rejects_second_websocket_for_same_session() -> None:
    from fastapi import FastAPI

    app = FastAPI()
    stage_session = Stage(app, dev=False).session()

    with TestClient(app) as client:
        session_id = client.get("/api/session").json()["sessionId"]
        with client.websocket_connect(f"/ws/{session_id}") as first:
            assert first.receive_json()["type"] == "welcome"
            with pytest.raises(Exception):
                with client.websocket_connect(f"/ws/{session_id}") as second:
                    second.receive_json()
            assert stage_session.registry.get_session(session_id) is not None
