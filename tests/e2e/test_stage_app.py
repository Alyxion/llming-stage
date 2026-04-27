"""End-to-end checks for the high-level Stage API."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator

import pytest
from playwright.sync_api import Page, expect

from .conftest import REPO_ROOT, _pick_free_port, _wait_port_open

pytestmark = pytest.mark.timeout(60)


@pytest.fixture
def stage_vue_server(tmp_path: Path) -> Iterator[tuple[str, Path]]:
    home = tmp_path / "home.vue"
    home.write_text(
        """
<template>
  <main class="q-pa-xl">
    <h1 id="title">Hello stage</h1>
    <q-btn id="button" color="primary" label="It works" />
  </main>
</template>
""",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        """
from fastapi import FastAPI
from llming_stage import Stage

app = FastAPI()
Stage(app, root=".").view("/", "home.vue")
""",
        encoding="utf-8",
    )
    port = _pick_free_port()
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(tmp_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    try:
        try:
            _wait_port_open(port, time.time() + 20)
        except RuntimeError:
            proc.terminate()
            out = proc.stdout.read().decode(errors="replace") if proc.stdout else ""
            raise RuntimeError(f"Stage app did not start:\n{out}")
        yield f"http://127.0.0.1:{port}", home
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def test_stage_vue_app_renders_and_autoreloads(
    stage_vue_server: tuple[str, Path], page: Page
) -> None:
    base, home = stage_vue_server
    page.goto(base)
    expect(page.locator("#title")).to_have_text("Hello stage", timeout=15_000)
    expect(page.locator("#button")).to_contain_text("It works")
    page.wait_for_function("window.__llmingStageDevReload === true")

    home.write_text(
        """
<template>
  <main class="q-pa-xl">
    <h1 id="title">Reloaded stage</h1>
    <q-btn id="button" color="primary" label="It still works" />
  </main>
</template>
""",
        encoding="utf-8",
    )

    expect(page.locator("#title")).to_have_text("Reloaded stage", timeout=10_000)
    expect(page.locator("#button")).to_contain_text("It still works")
