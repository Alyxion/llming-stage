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
    expect(page.locator(".text-h2")).to_contain_text("Static shell")
    expect(page.locator(".text-subtitle1")).to_contain_text("HTML document")


# ---------------------------------------------------------------------------
# 02 — hello_world (FE→BE call + BE→FE timer)
# ---------------------------------------------------------------------------
@pytest.mark.sample("02_hello_world")
def test_02_hello_world(sample_server: str, page: Page) -> None:
    session = open_sample(page, sample_server)
    expect(page.locator(".text-h4")).to_contain_text("hello_world")
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
    expect(page.locator(".text-h4")).to_contain_text("Multi-view")

    page.locator("a[href='/timer']").click()
    expect(page.locator(".text-overline")).to_contain_text("countdown")

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
    requests: list[str] = []
    page.on("request", lambda r: requests.append(r.url))
    page.goto(sample_server)
    expect(page.locator(".scene-title-line")).to_contain_text("Tornado", timeout=15_000)
    canvas = page.locator("#scene-canvas")
    expect(canvas).to_be_visible(timeout=10_000)
    box = canvas.bounding_box()
    assert box and box["width"] > 200 and box["height"] > 200, box
    assert any("three.module.min.js" in u for u in requests), requests[-10:]


# ---------------------------------------------------------------------------
# 08 — plotly_dashboard (lazy Plotly + streamed samples)
# ---------------------------------------------------------------------------
@pytest.mark.sample("08_plotly_dashboard")
def test_08_plotly_dashboard(sample_server: str, page: Page) -> None:
    page.goto(sample_server)
    expect(page.locator(".dash-title")).to_contain_text(
        "Analytics Dashboard", timeout=15_000
    )
    for cid in ("#chart-line", "#chart-bar", "#chart-pie", "#chart-radar",
                "#chart-cpu", "#chart-mem", "#chart-heat", "#chart-scatter",
                "#chart-candle"):
        expect(page.locator(cid)).to_have_count(1, timeout=10_000)
    # Wait for ECharts to render a canvas into at least one chart box.
    page.wait_for_selector("#chart-line canvas", timeout=10_000)
    # KPI populated with concrete values.
    kpi = page.locator("#kpi-revenue").inner_text()
    assert kpi and kpi != "—" and kpi.startswith("$"), kpi
    # Toggle a product chip and confirm the redraw didn't throw.
    page.locator(".chip", has_text="Laptops").click()
    page.wait_for_timeout(200)


# ---------------------------------------------------------------------------
# 09 — markdown_render (lazy KaTeX + DOMPurify)
# ---------------------------------------------------------------------------
@pytest.mark.sample("09_markdown_render")
def test_09_markdown_render(sample_server: str, page: Page) -> None:
    page.goto(sample_server)
    expect(page.locator(".text-h5")).to_contain_text("Math + sanitised HTML")

    page.locator("#render-math").click()
    expect(page.locator("#out .katex").first).to_be_visible(timeout=8_000)

    page.locator("#render-html").click()
    # DOMPurify strips <script>. The bold survives.
    expect(page.locator("#out b")).to_contain_text("Bold")
    expect(page.locator("#out script")).to_have_count(0)


# ---------------------------------------------------------------------------
# 10 — full_dashboard (everything composed)
# ---------------------------------------------------------------------------
@pytest.mark.sample("11_plotly_advanced")
def test_11_plotly_advanced(sample_server: str, page: Page) -> None:
    requests: list[str] = []
    page.on("request", lambda r: requests.append(r.url))
    page.goto(sample_server)
    expect(page.locator(".text-h5")).to_contain_text("advanced bundle", timeout=15_000)
    for cid in ("#chart-surface", "#chart-heat", "#chart-candle", "#chart-sankey"):
        expect(page.locator(cid)).to_have_count(1, timeout=10_000)
    page.wait_for_selector("#chart-surface canvas, #chart-surface svg", timeout=15_000)
    assert any("plotly-full.min.js" in u for u in requests), requests[-10:]


@pytest.mark.sample("10_full_dashboard")
def test_10_full_dashboard(sample_server: str, page: Page) -> None:
    session = open_sample(page, sample_server)
    wait_controller_ready(page, sample_server, session["sessionId"])
    expect(page.locator(".cap-brand-name")).to_contain_text("Capstone")

    debug_dispatch(page, session["sessionId"], {"type": "chat.ask", "text": "hi"})

    page.locator(".cap-nav-item[href='/chat']").click()
    expect(page.locator(".text-h5")).to_contain_text("Chat", timeout=5_000)
    state = debug_state(page, session["sessionId"])
    chat = state["state"].get("chat", [])
    assert any(m["role"] == "user" and m["text"] == "hi" for m in chat)
    assert any(m["role"] == "assistant" for m in chat)

    page.locator(".cap-nav-item[href='/uploads']").click()
    expect(page.locator(".text-h5")).to_contain_text("Uploads", timeout=5_000)
    page.set_input_files("#file", {
        "name": "note.txt",
        "mimeType": "text/plain",
        "buffer": b"capstone",
    })
    page.locator("#go").click()
    expect(page.locator("#progress")).to_contain_text("done", timeout=10_000)
