"""End-to-end test for the samples gallery.

Spawns ``samples/gallery.py`` on a free port with the gallery's sample
port also pinned to a free port, loads the UI in Chromium, clicks a
sample in the sidebar, and confirms the iframe loads that sample.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator

import pytest
from playwright.sync_api import Page, expect

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def _free_port() -> int:
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


@pytest.fixture
def gallery_server() -> Iterator[tuple[str, int]]:
    gallery_port = _free_port()
    sample_port = _free_port()
    env = {
        **os.environ,
        "GALLERY_PORT": str(gallery_port),
        "SAMPLE_PORT": str(sample_port),
    }
    proc = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "samples" / "gallery.py")],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            if _port_open(gallery_port):
                break
            time.sleep(0.2)
        else:
            proc.terminate()
            out = proc.stdout.read().decode(errors="replace") if proc.stdout else ""
            raise RuntimeError(f"gallery did not start:\n{out}")
        yield f"http://127.0.0.1:{gallery_port}", sample_port
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def test_gallery_lists_all_samples(gallery_server, page: Page) -> None:
    base, _ = gallery_server
    page.goto(base)
    expect(page.locator(".q-toolbar__title")).to_contain_text("llming-stage gallery")
    names = page.evaluate(
        "() => Array.from(document.querySelectorAll('[data-sample]'))"
        "         .map(e => e.getAttribute('data-sample'))"
    )
    assert len(names) == 10
    assert names[0] == "01_static"
    assert "10_full_dashboard" in names


def test_gallery_launches_sample_into_iframe(gallery_server, page: Page) -> None:
    base, _ = gallery_server
    page.goto(base)
    page.locator("[data-sample='02_hello_world']").click()
    expect(page.locator("[data-test='current']")).to_contain_text(
        "02_hello_world", timeout=20_000
    )
    expect(
        page.frame_locator("[data-test='frame']").locator("h1")
    ).to_contain_text("hello_world", timeout=15_000)


def test_gallery_switches_between_samples(gallery_server, page: Page) -> None:
    base, _ = gallery_server
    page.goto(base)

    page.locator("[data-sample='02_hello_world']").click()
    expect(page.locator("[data-test='current']")).to_contain_text(
        "02_hello_world", timeout=20_000
    )
    expect(
        page.frame_locator("[data-test='frame']").locator("h1")
    ).to_contain_text("hello_world", timeout=15_000)

    page.locator("[data-sample='03_counter_command']").click()
    expect(page.locator("[data-test='current']")).to_contain_text(
        "03_counter_command", timeout=20_000
    )
    expect(
        page.frame_locator("[data-test='frame']").locator("h1")
    ).to_contain_text("Counter", timeout=15_000)


def test_gallery_stop_button(gallery_server, page: Page) -> None:
    base, _ = gallery_server
    page.goto(base)
    page.locator("[data-sample='01_static']").click()
    expect(page.locator("[data-test='current']")).to_contain_text(
        "01_static", timeout=20_000
    )
    page.locator("[data-test='btn-stop']").click()
    expect(page.locator("[data-test='current']")).to_have_count(0, timeout=15_000)


def test_gallery_dark_mode_default(gallery_server, page: Page) -> None:
    base, _ = gallery_server
    page.goto(base)
    # Quasar sets body.body--dark when dark mode is active.
    expect(page.locator("body")).to_have_class(
        # regex — class list contains body--dark
        # pylint: disable=line-too-long
        __import__("re").compile(r"\bbody--dark\b"),
        timeout=5_000,
    )


def test_iframe_fills_content_area(gallery_server, page: Page) -> None:
    """Regression guard: iframes must fill the page, not collapse to 150 px."""
    base, _ = gallery_server
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(base)
    page.locator("[data-sample='02_hello_world']").click()
    expect(page.locator("[data-test='current']")).to_contain_text(
        "02_hello_world", timeout=20_000
    )
    box = page.locator("[data-test='frame']").bounding_box(timeout=15_000)
    assert box is not None
    # Viewport is 800px tall, header ~50px — iframe should be ~700px.
    assert box["height"] >= 600, f"iframe is too short: {box}"
    # And wide — drawer ~320, page ~960.
    assert box["width"] >= 700, f"iframe is too narrow: {box}"


def test_sample_inherits_dark_mode(gallery_server, page: Page) -> None:
    """Gallery's dark state must propagate into the iframe via stage_dark=."""
    import re
    base, _ = gallery_server
    page.goto(base)
    page.locator("[data-sample='02_hello_world']").click()
    expect(page.locator("[data-test='current']")).to_contain_text(
        "02_hello_world", timeout=20_000
    )
    frame = page.frame_locator("[data-test='frame']")
    expect(frame.locator("h1")).to_contain_text("hello_world", timeout=15_000)
    # Sample body must carry body--dark because the gallery defaults to dark.
    expect(frame.locator("body")).to_have_class(
        re.compile(r"\bbody--dark\b"), timeout=5_000
    )
    # Toggle to light — sample should flip too.
    page.locator("[data-test='btn-dark']").click()
    expect(frame.locator("body")).to_have_class(
        re.compile(r"\bbody--light\b"), timeout=10_000
    )


def test_gallery_dark_mode_toggle(gallery_server, page: Page) -> None:
    base, _ = gallery_server
    page.goto(base)
    page.locator("[data-test='btn-dark']").click()
    expect(page.locator("body")).to_have_class(
        __import__("re").compile(r"\bbody--light\b"),
        timeout=5_000,
    )
    page.locator("[data-test='btn-dark']").click()
    expect(page.locator("body")).to_have_class(
        __import__("re").compile(r"\bbody--dark\b"),
        timeout=5_000,
    )
