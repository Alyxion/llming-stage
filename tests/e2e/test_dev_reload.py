"""End-to-end browser test for the development reload client."""

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
def dev_reload_server(tmp_path: Path) -> Iterator[tuple[str, Path]]:
    watch_dir = tmp_path / "watched"
    watch_dir.mkdir()
    (watch_dir / "theme.css").write_text("body { color: red; }\n", encoding="utf-8")
    (tmp_path / "home.vue").write_text(
        """
<template>
  <main id="reload-count">{{ count }}</main>
</template>

<script>
export default {
  data() {
    return { count: 0 };
  },
  mounted() {
    const key = "llming-stage-dev-reload-count";
    this.count = Number(localStorage.getItem(key) || "0") + 1;
    localStorage.setItem(key, String(this.count));
  },
};
</script>
""",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        """
from fastapi import FastAPI
from llming_stage import Stage

app = FastAPI()
Stage(app, root=__file__, title="dev reload").view("/", "home.vue")
""",
        encoding="utf-8",
    )

    port = _pick_free_port()
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT),
    }
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app:app",
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
            raise RuntimeError(f"dev reload server did not start:\n{out}")
        yield f"http://127.0.0.1:{port}", watch_dir
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def test_dev_reload_reloads_browser_only_on_content_change(
    dev_reload_server: tuple[str, Path], page: Page
) -> None:
    console_messages: list[str] = []
    page.on("console", lambda msg: console_messages.append(msg.text))
    base, watch_dir = dev_reload_server
    page.goto(base)
    expect(page.locator("#reload-count")).to_have_text("1", timeout=15_000)
    page.wait_for_function("window.__llmingStageDevReload === true")
    page.wait_for_timeout(300)

    os.utime(watch_dir / "theme.css", None)
    page.wait_for_timeout(300)
    expect(page.locator("#reload-count")).to_have_text("1")

    (watch_dir / "theme.css").write_text("body { color: blue; }\n", encoding="utf-8")
    expect(page.locator("#reload-count")).to_have_text("2", timeout=10_000)
    assert any("[llming-stage] reload requested" in msg for msg in console_messages)
    assert any("[llming-stage] reloaded in" in msg for msg in console_messages)
