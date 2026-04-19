"""End-to-end Playwright tests for every sample.

Each test runs the sample in a subprocess (see ``conftest.py``),
opens it in Chromium via Playwright, verifies the page renders, and
— for WebSocket-enabled samples — drives the session through the
``debug.ws_dispatch`` HTTP command so the test validates the full
reactive loop (AI-invoke → server dispatch → WS push → DOM update).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .conftest import debug_dispatch, debug_state, open_sample, wait_controller_ready

pytestmark = pytest.mark.timeout(60)


# ---------------------------------------------------------------------------
# 01 — static (no WebSocket)
# ---------------------------------------------------------------------------
@pytest.mark.sample("01_static")
def test_01_static(sample_server: str, page: Page) -> None:
    page.goto(sample_server)
    expect(page.locator("h1")).to_contain_text("Static")
    expect(page.locator("p")).to_contain_text("No WebSocket")


# ---------------------------------------------------------------------------
# 02 — hello_world (FE→BE call + BE→FE timer)
# ---------------------------------------------------------------------------
@pytest.mark.sample("02_hello_world")
def test_02_hello_world(sample_server: str, page: Page) -> None:
    session = open_sample(page, sample_server)
    expect(page.locator("h1")).to_contain_text("hello_world")
    wait_controller_ready(page, sample_server, session["sessionId"])

    # UI-driven FE→BE call.
    page.locator("#name").fill("Michael")
    page.locator("#say").click()
    expect(page.locator("#reply")).to_contain_text("Hello, Michael!")

    # Debug-command-driven FE→BE call — same handler, same DOM update.
    result = debug_dispatch(page, session["sessionId"],
                            {"type": "hello.say", "name": "Agent"})
    assert result["ok"] is True
    expect(page.locator("#reply")).to_contain_text("Hello, Agent!")

    # BE→FE timer should have pushed at least one tick by now.
    expect(page.locator("#tick")).to_contain_text("tick")


# ---------------------------------------------------------------------------
# 03 — counter (server state + reactive push)
# ---------------------------------------------------------------------------
@pytest.mark.sample("03_counter_command")
def test_03_counter(sample_server: str, page: Page) -> None:
    session = open_sample(page, sample_server)
    wait_controller_ready(page, sample_server, session["sessionId"])

    # Drive the counter entirely through the debug HTTP surface.
    debug_dispatch(page, session["sessionId"], {"type": "counter.inc", "by": 3})
    debug_dispatch(page, session["sessionId"], {"type": "counter.inc", "by": 2})

    expect(page.locator("#val")).to_have_text("5")
    state = debug_state(page, session["sessionId"])
    assert state["state"].get("count") == 5

    # Reset via debug and verify.
    debug_dispatch(page, session["sessionId"], {"type": "counter.reset"})
    expect(page.locator("#val")).to_have_text("0")


# ---------------------------------------------------------------------------
# 04 — multi_view (shared socket across client-side navigation)
# ---------------------------------------------------------------------------
@pytest.mark.sample("04_multi_view")
def test_04_multi_view(sample_server: str, page: Page) -> None:
    session = open_sample(page, sample_server)
    wait_controller_ready(page, sample_server, session["sessionId"])
    expect(page.locator("h1")).to_contain_text("Home")

    # Navigate to /timer via the SPA router (data-stage-link handling).
    page.locator("a[href='/timer']").click()
    expect(page.locator("h1")).to_contain_text("Timer")

    # Kick a 3s countdown through debug and verify ticks arrive.
    debug_dispatch(page, session["sessionId"], {"type": "timer.start", "seconds": 3})
    expect(page.locator("#val")).to_contain_text("s", timeout=5_000)
    expect(page.locator("#val")).to_have_text("✓ done", timeout=8_000)


# ---------------------------------------------------------------------------
# 05 — file_upload (narrow HTTP + WS progress)
# ---------------------------------------------------------------------------
@pytest.mark.sample("05_file_upload")
def test_05_file_upload(sample_server: str, page: Page) -> None:
    session = open_sample(page, sample_server)
    wait_controller_ready(page, sample_server, session["sessionId"])

    page.set_input_files("#file", {
        "name": "hello.txt",
        "mimeType": "text/plain",
        "buffer": b"Hello, stage!",
    })
    page.locator("#go").click()
    expect(page.locator("#progress")).to_contain_text("done", timeout=10_000)
    expect(page.locator("#history li").first).to_contain_text("hello.txt")

    state = debug_state(page, session["sessionId"])
    uploads = state["state"].get("uploads", [])
    assert uploads and uploads[0]["name"] == "hello.txt"
    assert uploads[0]["bytes"] == len(b"Hello, stage!")


# ---------------------------------------------------------------------------
# 06 — chat_stream (server-streamed deltas)
# ---------------------------------------------------------------------------
@pytest.mark.sample("06_chat_stream")
def test_06_chat_stream(sample_server: str, page: Page) -> None:
    session = open_sample(page, sample_server)
    wait_controller_ready(page, sample_server, session["sessionId"])

    debug_dispatch(page, session["sessionId"],
                   {"type": "chat.ask", "text": "test prompt"})
    # Streaming completes after ~1.5s worth of chunks.
    assistant = page.locator(".msg.assistant").first
    expect(assistant).to_contain_text("llming-stage", timeout=8_000)


# ---------------------------------------------------------------------------
# 07 — 3d_scene (lazy Three.js, no WS)
# ---------------------------------------------------------------------------
@pytest.mark.sample("07_3d_scene")
def test_07_3d_scene(sample_server: str, page: Page) -> None:
    page.goto(sample_server)
    expect(page.locator("h1")).to_contain_text("Three.js")
    # The lazy load imports three.module.min.js, which imports
    # three.core.min.js; once both resolve, the view inserts a
    # WebGL canvas into #canvas-holder.
    expect(page.locator("#canvas-holder canvas")).to_be_visible(timeout=10_000)
    # And the canvas should have real dimensions (proof the renderer
    # attached, not just a stray element).
    size = page.evaluate(
        "() => { const c = document.querySelector('#canvas-holder canvas');"
        "  return c && {w: c.width, h: c.height}; }"
    )
    assert size and size["w"] > 0 and size["h"] > 0


# ---------------------------------------------------------------------------
# 08 — plotly_dashboard (lazy Plotly + streamed samples)
# ---------------------------------------------------------------------------
@pytest.mark.sample("08_plotly_dashboard")
def test_08_plotly_dashboard(sample_server: str, page: Page) -> None:
    session = open_sample(page, sample_server)
    wait_controller_ready(page, sample_server, session["sessionId"])
    # Chart element should materialise after Plotly lazy-loads.
    expect(page.locator("#chart")).to_be_visible()

    debug_dispatch(page, session["sessionId"], {"type": "metric.start"})
    # After ~1s the chart should have at least one sample.
    page.wait_for_timeout(1500)
    n = page.evaluate("() => document.querySelectorAll('#chart .trace').length")
    assert n >= 1

    debug_dispatch(page, session["sessionId"], {"type": "metric.stop"})


# ---------------------------------------------------------------------------
# 09 — markdown_render (lazy KaTeX + DOMPurify)
# ---------------------------------------------------------------------------
@pytest.mark.sample("09_markdown_render")
def test_09_markdown_render(sample_server: str, page: Page) -> None:
    page.goto(sample_server)
    expect(page.locator("h1").first).to_contain_text("Source")

    page.locator("#render-math").click()
    expect(page.locator("#out .katex").first).to_be_visible(timeout=8_000)

    page.locator("#render-html").click()
    # DOMPurify strips <script>. The bold survives.
    expect(page.locator("#out b")).to_contain_text("Bold")
    expect(page.locator("#out script")).to_have_count(0)


# ---------------------------------------------------------------------------
# 10 — full_dashboard (everything composed)
# ---------------------------------------------------------------------------
@pytest.mark.sample("10_full_dashboard")
def test_10_full_dashboard(sample_server: str, page: Page) -> None:
    session = open_sample(page, sample_server)
    wait_controller_ready(page, sample_server, session["sessionId"])
    expect(page.locator("h1")).to_contain_text("Capstone")

    # Drive a chat message entirely through debug.
    debug_dispatch(page, session["sessionId"], {"type": "chat.ask", "text": "hi"})

    # Now navigate to /chat and confirm history is visible server-side.
    page.locator("a[href='/chat']").click()
    expect(page.locator("h1")).to_contain_text("Chat", timeout=5_000)
    state = debug_state(page, session["sessionId"])
    chat = state["state"].get("chat", [])
    assert any(m["role"] == "user" and m["text"] == "hi" for m in chat)
    assert any(m["role"] == "assistant" for m in chat)

    # Trigger an upload from the uploads view via navigation + real UI.
    page.locator("a[href='/uploads']").click()
    expect(page.locator("h1")).to_contain_text("Uploads", timeout=5_000)
    page.set_input_files("#file", {
        "name": "note.txt",
        "mimeType": "text/plain",
        "buffer": b"capstone",
    })
    page.locator("#go").click()
    expect(page.locator("#progress")).to_contain_text("done", timeout=10_000)
