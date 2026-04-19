"""Integration tests for the zip-backed asset routes."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from llming_stage.zip_server import ZipArchive, make_zip_handler


@pytest.fixture
def mini_zip(tmp_path: Path) -> Path:
    path = tmp_path / "icons.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("regular/house.svg", "<svg>house</svg>")
        zf.writestr("bold/house.svg", "<svg>bold house</svg>")
        zf.writestr("regular/evil.exe", "bad")
        zf.writestr("../escape.svg", "<svg>escape</svg>")
        zf.writestr("a\\b.svg", "<svg>backslash</svg>")
    return path


@pytest.fixture
def mini_app(mini_zip: Path) -> Starlette:
    archive = ZipArchive(mini_zip)
    app = Starlette()
    app.router.routes.append(Route("/i/{path:path}", make_zip_handler(archive)))
    return app


@pytest.fixture
def mini_client(mini_app: Starlette) -> TestClient:
    return TestClient(mini_app)


def test_archive_only_admits_safe_entries(mini_zip: Path) -> None:
    archive = ZipArchive(mini_zip)
    assert len(archive) == 2  # the two .svg files with safe names


def test_serves_valid_entry(mini_client: TestClient) -> None:
    r = mini_client.get("/i/regular/house.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert r.text == "<svg>house</svg>"


def test_second_weight_works(mini_client: TestClient) -> None:
    r = mini_client.get("/i/bold/house.svg")
    assert r.status_code == 200
    assert r.text == "<svg>bold house</svg>"


def test_rejects_disallowed_extension_in_zip(mini_client: TestClient) -> None:
    r = mini_client.get("/i/regular/evil.exe")
    assert r.status_code == 404


def test_rejects_traversal_in_zip(mini_client: TestClient) -> None:
    r = mini_client.get("/i/../escape.svg")
    assert r.status_code == 404


def test_rejects_missing_entry(mini_client: TestClient) -> None:
    r = mini_client.get("/i/regular/ghost.svg")
    assert r.status_code == 404
