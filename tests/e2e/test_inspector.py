"""End-to-end checks for the standalone inspector proxy."""

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
def inspected_stage_app(tmp_path: Path) -> Iterator[str]:
    (tmp_path / "home.vue").write_text(
        """
<template>
  <main class="q-pa-xl">
    <h1 id="title">Debuggable stage</h1>
  </main>
</template>
<script>
export default {
  mounted() {
    this.$stage.connect();
  },
};
</script>
""",
        encoding="utf-8",
    )
    (tmp_path / "home.debug.js").write_text(
        """
export default function debug(ctx) {
  ctx.action("demo.fill", {
    label: "Fill demo state",
    group: "Demo",
  }, () => {
    document.getElementById("title").textContent = "Debug action ran";
    return { ok: true };
  });
}
""",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        """
from fastapi import FastAPI
from llming_stage import Stage

app = FastAPI()
stage = Stage(app, root=".", dev=False)
stage.add_view("/", "home.vue")
stage.session()
""",
        encoding="utf-8",
    )
    port = _pick_free_port()
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT),
        "LLMING_STAGE_DEBUG": "1",
        "LLMING_STAGE_DEBUG_TOKEN": "test-token",
        "STAGE_RELOAD": "0",
    }
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
            raise RuntimeError(f"target app did not start:\n{out}")
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


@pytest.fixture
def inspector_server(inspected_stage_app: str) -> Iterator[str]:
    port = _pick_free_port()
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "llming_stage.cli",
            "inspect",
            inspected_stage_app,
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--token",
            "test-token",
        ],
        cwd=str(REPO_ROOT),
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
            raise RuntimeError(f"inspector did not start:\n{out}")
        yield f"http://127.0.0.1:{port}/"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def test_inspector_attaches_without_injecting_app_chrome(
    inspector_server: str, page: Page
) -> None:
    page.goto(inspector_server)
    expect(page.locator(".rn-title-main")).to_have_text("llming-stage inspector")
    expect(page.locator("[data-test='inspector-frame']")).to_be_visible()

    frame = page.frame_locator("[data-test='inspector-frame']")
    expect(frame.locator("#title")).to_have_text("Debuggable stage", timeout=15_000)
    expect(frame.locator("#stage-controls")).to_have_count(0)
    expect(frame.locator("[data-test='stage-restart']")).to_have_count(0)

    page.locator("[data-test='btn-debug']").click()
    expect(page.locator(".rn-debug")).to_be_visible()
    page.locator(".rn-tab", has_text="Console").click()
    expect(page.locator(".rn-console-input")).to_have_count(0)
    expect(page.locator(".rn-console-bar")).to_contain_text("Python process stdout")
    page.locator(".rn-tab", has_text="Sessions").click()
    expect(page.locator(".rn-session-row")).to_have_count(1, timeout=15_000)
    session_box = page.locator(".rn-sessions-list").bounding_box()
    action_box = page.locator(".rn-action-tile", has_text="Fill demo state").bounding_box()
    assert session_box is not None
    assert action_box is not None
    assert action_box["x"] >= session_box["x"] + session_box["width"]

    page.locator(".rn-tab", has_text="Metrics").click()
    expect(page.locator(".rn-stat-label", has_text="PID")).to_be_visible()
    expect(page.locator(".rn-stat-value").first).not_to_have_text("-")
    page.locator(".rn-tab", has_text="Sessions").click()

    page.locator(".rn-session-tab", has_text="JS").click()
    expect(page.locator(".rn-console-input input")).to_be_enabled()
    page.locator(".rn-console-input input").fill("document.getElementById('title').textContent")
    page.locator(".rn-console-input input").press("Enter")
    expect(page.locator(".rn-console").last).to_contain_text("Debuggable stage")

    other = page.context.new_page()
    try:
        other.goto(inspector_server + "?_llming_inspector_target=1")
        expect(other.locator("#title")).to_have_text("Debuggable stage", timeout=15_000)
        other.wait_for_function("sessionStorage.getItem('__llming_session')")
        other_session = other.evaluate("sessionStorage.getItem('__llming_session')")

        expect(page.locator(".rn-session-row")).to_have_count(2, timeout=15_000)
        page.locator(".rn-session-row", has_text=other_session[:12]).click()
        page.locator(".rn-session-tab", has_text="JS").click()
        expect(page.locator(".rn-console-input input")).to_be_enabled(timeout=10_000)
        page.locator(".rn-console-input input").fill(
            "document.getElementById('title').textContent = 'Other session JS'; "
            "document.getElementById('title').textContent"
        )
        page.locator(".rn-console-input input").press("Enter")
        expect(other.locator("#title")).to_have_text("Other session JS", timeout=5_000)
        expect(frame.locator("#title")).to_have_text("Debuggable stage")
        expect(page.locator(".rn-console").last).to_contain_text("Other session JS")
    finally:
        other.close()

    page.locator(".rn-session-tab", has_text="Actions").click()
    first_session = frame.locator("body").evaluate("sessionStorage.getItem('__llming_session')")
    page.locator(".rn-session-row", has_text=first_session[:12]).click()
    page.locator(".rn-action-tile", has_text="Fill demo state").click()

    expect(frame.locator("#title")).to_have_text("Debug action ran", timeout=5_000)
