"""Tests for the Stage OOP helper."""

from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
from starlette.testclient import TestClient

from llming_stage import Stage, StageSession


def test_stage_view_serves_vue_and_shell(tmp_path: Path) -> None:
    (tmp_path / "home.vue").write_text(
        "<template><main id='hello'>Hello stage</main></template>",
        encoding="utf-8",
    )
    app = Starlette()
    Stage(app, root=tmp_path).view("/", "home.vue")

    with TestClient(app) as client:
        shell = client.get("/")
        view = client.get("/_stage/app/home.js")

    assert shell.status_code == 200
    assert "__stageRouter.register('/', 'home')" in shell.text
    assert "/_stage/dev/client.js" in shell.text
    assert view.status_code == 200
    assert "Vue.createApp" in view.text
    assert "Hello stage" in view.text


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
    Stage(app, root=tmp_path).view("/", "home.vue")

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

    counter = session.router("counter")
    admin = session.app_router("admin")

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

    Stage(app, root=tmp_path).view("/", "home.vue")
    Stage(app, root=tmp_path).view("/other", "home.vue", name="other")

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
