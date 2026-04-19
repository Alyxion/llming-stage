"""Integration tests for the path-hardened asset routes."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from llming_stage.asset_server import make_dir_handler


@pytest.fixture
def mini_root(tmp_path: Path) -> Path:
    root = tmp_path / "assets"
    root.mkdir()
    (root / "hello.js").write_text("console.log('hi');\n")
    (root / "style.css").write_text("body{}\n")
    (root / "data.json").write_text('{"ok":1}\n')
    (root / "evil.exe").write_text("MZ\x00\x00")
    sub = root / "sub"
    sub.mkdir()
    (sub / "nested.svg").write_text("<svg/>")
    secret = tmp_path / "secret.txt"
    secret.write_text("top-secret")
    return root


@pytest.fixture
def mini_app(mini_root: Path) -> Starlette:
    app = Starlette()
    app.router.routes.append(Route("/a/{path:path}", make_dir_handler(mini_root)))
    return app


@pytest.fixture
def mini_client(mini_app: Starlette) -> TestClient:
    return TestClient(mini_app)


def test_serves_allowed_file(mini_client: TestClient) -> None:
    r = mini_client.get("/a/hello.js")
    assert r.status_code == 200
    assert r.text.startswith("console.log")
    assert r.headers["content-type"].startswith("application/javascript")
    assert "immutable" in r.headers["cache-control"]


def test_serves_css_with_correct_mime(mini_client: TestClient) -> None:
    r = mini_client.get("/a/style.css")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/css")


def test_serves_nested_file(mini_client: TestClient) -> None:
    r = mini_client.get("/a/sub/nested.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")


def test_rejects_disallowed_extension(mini_client: TestClient) -> None:
    r = mini_client.get("/a/evil.exe")
    assert r.status_code == 404


def test_rejects_missing_file(mini_client: TestClient) -> None:
    r = mini_client.get("/a/does-not-exist.js")
    assert r.status_code == 404


def test_rejects_directory_request(mini_client: TestClient) -> None:
    r = mini_client.get("/a/sub")
    assert r.status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/a/../secret.txt",
        "/a/..%2Fsecret.txt",
        "/a/sub/../../secret.txt",
        "/a/%00.js",
    ],
)
def test_rejects_traversal_attempts(mini_client: TestClient, path: str) -> None:
    r = mini_client.get(path)
    assert r.status_code == 404


def test_rejects_symlink_escape(tmp_path: Path, mini_root: Path) -> None:
    target = tmp_path / "outside.js"
    target.write_text("outside")
    link = mini_root / "link.js"
    link.symlink_to(target)
    app = Starlette()
    app.router.routes.append(Route("/a/{path:path}", make_dir_handler(mini_root)))
    client = TestClient(app)
    r = client.get("/a/link.js")
    assert r.status_code == 404
