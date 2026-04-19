"""Pytest fixtures for llming-stage."""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from llming_stage import ShellConfig, mount_assets, mount_shell


@pytest.fixture
def app() -> Starlette:
    app = Starlette()
    mount_assets(app)
    mount_shell(
        app,
        config=ShellConfig(
            title="test",
            routes=[("/", "home"), ("/chat", "chat")],
            preload_views=["home"],
        ),
    )
    return app


@pytest.fixture
def client(app: Starlette) -> TestClient:
    return TestClient(app)
