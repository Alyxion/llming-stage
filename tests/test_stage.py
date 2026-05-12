"""Tests for the Stage OOP helper."""

from __future__ import annotations

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
