"""Tests for development reload watching."""

from __future__ import annotations

import os
from pathlib import Path

from starlette.applications import Starlette
from starlette.testclient import TestClient

from llming_stage import DevReloadConfig, ShellConfig, mount_dev_reload, render_shell


def test_shell_can_include_dev_reload_client() -> None:
    html = render_shell(ShellConfig(dev_reload=True))
    assert '<script src="/_stage/dev/client.js" defer></script>' in html


def test_dev_reload_serves_client_script(tmp_path: Path) -> None:
    app = Starlette()
    mount_dev_reload(app, watch_paths=[tmp_path], poll_interval=60)

    with TestClient(app) as client:
        r = client.get("/_stage/dev/client.js")

    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    assert "new WebSocket" in r.text


def test_content_hash_ignores_unchanged_touch(tmp_path: Path) -> None:
    watched = tmp_path / "home.js"
    watched.write_text("one", encoding="utf-8")
    reloader = mount_dev_reload(
        Starlette(),
        config=DevReloadConfig(watch_paths=[tmp_path], poll_interval=60),
    )
    reloader._snapshot.prime()

    os.utime(watched, None)
    changes = reloader._snapshot.changes()

    assert changes == ()


def test_browser_reload_change_is_broadcast_over_websocket(tmp_path: Path) -> None:
    watched = tmp_path / "home.css"
    watched.write_text("body { color: red; }", encoding="utf-8")
    app = Starlette()
    reloader = mount_dev_reload(app, watch_paths=[tmp_path], poll_interval=60)

    with TestClient(app) as client:
        with client.websocket_connect("/_stage/dev/ws") as ws:
            assert ws.receive_json()["type"] == "connected"
            watched.write_text("body { color: blue; }", encoding="utf-8")

            client.portal.call(reloader.scan_once)
            msg = ws.receive_json()

    assert msg["type"] == "reload"
    assert msg["path"] == "/"
    assert msg["files"][0]["kind"] == "modified"
    assert msg["files"][0]["path"].endswith("home.css")


def test_python_change_calls_server_reload_hook(tmp_path: Path) -> None:
    watched = tmp_path / "app.py"
    watched.write_text("VALUE = 1\n", encoding="utf-8")
    seen = []

    def on_server_reload(changes):
        seen.extend(changes)

    app = Starlette()
    reloader = mount_dev_reload(
        app,
        watch_paths=[tmp_path],
        poll_interval=60,
        on_server_reload=on_server_reload,
    )
    reloader._snapshot.prime()

    watched.write_text("VALUE = 2\n", encoding="utf-8")
    with TestClient(app) as client:
        changes = client.portal.call(reloader.scan_once)

    assert [c.kind for c in changes] == ["modified"]
    assert [c.path for c in seen] == [watched]
