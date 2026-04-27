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
# static_shell — no WebSocket
# ---------------------------------------------------------------------------
@pytest.mark.sample("static_shell")
def test_static_shell(sample_server: str, page: Page) -> None:
    page.goto(sample_server)
    expect(page.locator(".text-h2")).to_contain_text("Static shell")
    expect(page.locator(".text-subtitle1")).to_contain_text("One Vue view")


# ---------------------------------------------------------------------------
# hello_world — minimal Vue app
# ---------------------------------------------------------------------------
@pytest.mark.sample("hello_world")
def test_hello_world(sample_server: str, page: Page) -> None:
    page.goto(sample_server)
    expect(page.locator("h1")).to_contain_text("Hello world")
    expect(page.locator("p.text-lg")).to_contain_text("Hot reload by default")
    page.wait_for_function(
        "() => getComputedStyle(document.querySelector('main')).display === 'flex'"
    )


# ---------------------------------------------------------------------------
# counter — server state + reactive push
# ---------------------------------------------------------------------------
@pytest.mark.sample("counter")
def test_counter(sample_server: str, page: Page) -> None:
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
# multi_view — shared socket across client-side navigation
# ---------------------------------------------------------------------------
@pytest.mark.sample("multi_view")
def test_multi_view(sample_server: str, page: Page) -> None:
    session = open_sample(page, sample_server)
    wait_controller_ready(page, sample_server, session["sessionId"])
    expect(page.locator(".text-h4")).to_contain_text("Multi-view")

    page.locator("#open-drawer").click()
    expect(page.locator("#drawer")).to_be_visible(timeout=5_000)
    expect(page.locator("#drawer-message")).to_contain_text("nested Vue component")
    page.locator("#drawer-close").click()
    expect(page.locator("#drawer")).to_have_count(0)

    page.locator("a[href='/timer']").click()
    expect(page.locator(".text-overline")).to_contain_text("countdown")

    # Kick a 3s countdown through debug and verify ticks arrive.
    debug_dispatch(page, session["sessionId"], {"type": "timer.start", "seconds": 3})
    expect(page.locator("#val")).to_contain_text("s", timeout=5_000)
    expect(page.locator("#val")).to_have_text("✓ done", timeout=8_000)


# ---------------------------------------------------------------------------
# file_upload — narrow HTTP + WS progress
# ---------------------------------------------------------------------------
@pytest.mark.sample("file_upload")
def test_file_upload(sample_server: str, page: Page) -> None:
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
# chat_stream — server-streamed deltas
# ---------------------------------------------------------------------------
@pytest.mark.sample("chat_stream")
def test_chat_stream(sample_server: str, page: Page) -> None:
    session = open_sample(page, sample_server)
    wait_controller_ready(page, sample_server, session["sessionId"])

    debug_dispatch(page, session["sessionId"],
                   {"type": "chat.ask", "text": "test prompt"})
    # Streaming completes after ~1.5s worth of chunks.
    assistant = page.locator(".msg.assistant").first
    expect(assistant).to_contain_text("llming-stage", timeout=8_000)


# ---------------------------------------------------------------------------
# three_scene — lazy Three.js, no WS
# ---------------------------------------------------------------------------
@pytest.mark.sample("three_scene")
def test_three_scene(sample_server: str, page: Page) -> None:
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
# analytics_dashboard — lazy ECharts dashboard
# ---------------------------------------------------------------------------
@pytest.mark.sample("analytics_dashboard")
def test_analytics_dashboard(sample_server: str, page: Page) -> None:
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
# markdown_render — lazy KaTeX + DOMPurify
# ---------------------------------------------------------------------------
@pytest.mark.sample("markdown_render")
def test_markdown_render(sample_server: str, page: Page) -> None:
    page.goto(sample_server)
    expect(page.locator(".text-h5")).to_contain_text("Math + sanitised HTML")

    page.locator("#render-math").click()
    expect(page.locator("#out .katex").first).to_be_visible(timeout=8_000)

    page.locator("#render-html").click()
    # DOMPurify strips <script>. The bold survives.
    expect(page.locator("#out b")).to_contain_text("Bold")
    expect(page.locator("#out script")).to_have_count(0)


# ---------------------------------------------------------------------------
@pytest.mark.sample("plotly_advanced")
def test_plotly_advanced(sample_server: str, page: Page) -> None:
    requests: list[str] = []
    console_messages: list[str] = []
    page.on("request", lambda r: requests.append(r.url))
    page.on("console", lambda msg: console_messages.append(msg.text))
    page.goto(sample_server)
    expect(page.locator(".text-h5")).to_contain_text("advanced bundle", timeout=15_000)
    for cid in ("#chart-surface", "#chart-heat", "#chart-candle", "#chart-sankey"):
        expect(page.locator(cid)).to_have_count(1, timeout=10_000)
    page.wait_for_selector("#chart-surface canvas, #chart-surface svg", timeout=15_000)
    assert any("plotly-full.min.js" in u for u in requests), requests[-10:]
    assert not any("willReadFrequently" in msg for msg in console_messages)


# ---------------------------------------------------------------------------
# capstone_dashboard — everything composed
# ---------------------------------------------------------------------------
@pytest.mark.sample("capstone_dashboard")
def test_capstone_dashboard(sample_server: str, page: Page) -> None:
    session = open_sample(page, sample_server)
    wait_controller_ready(page, sample_server, session["sessionId"])
    expect(page.locator(".cap-brand-name")).to_contain_text("Capstone")
    page.get_by_role("button", name="App broadcast").click()
    expect(page.locator("text=Hello from AppRouter")).to_be_visible(timeout=5_000)

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


# ---------------------------------------------------------------------------
# extension_workbench — all optional lazy extensions
# ---------------------------------------------------------------------------
@pytest.mark.sample("extension_workbench")
def test_extension_workbench(sample_server: str, page: Page) -> None:
    requests: list[str] = []
    page.on("request", lambda r: requests.append(r.url))
    page.goto(sample_server)

    expect(page.locator("#workbench-title")).to_contain_text(
        "Extension workbench", timeout=15_000
    )
    expect(page.locator("#markdown-out h2")).to_contain_text(
        "Professional sample brief", timeout=10_000
    )
    page.wait_for_selector("#mermaid-out svg", timeout=15_000)
    page.wait_for_selector(".CodeMirror", timeout=10_000)
    page.wait_for_selector("#flow-editor .drawflow-node", timeout=10_000)
    page.wait_for_selector("#terminal .xterm", timeout=10_000)

    expected_assets = [
        "marked.umd.js",
        "dompurify.min.js",
        "mermaid.min.js",
        "codemirror.js",
        "drawflow.min.js",
        "xterm.js",
        "xterm-addon-fit.js",
        "xterm-addon-web-links.js",
        "xterm-addon-webgl.js",
    ]
    for asset in expected_assets:
        assert any(asset in url for url in requests), asset


# ---------------------------------------------------------------------------
# basic_components — Tailwind + core Quasar UI surface
# ---------------------------------------------------------------------------
@pytest.mark.sample("basic_components")
def test_basic_components(sample_server: str, page: Page) -> None:
    requests: list[str] = []
    page.on("request", lambda r: requests.append(r.url))
    page.goto(sample_server)

    expect(page.locator("h1")).to_contain_text("Basic components", timeout=10_000)
    page.wait_for_function(
        "() => getComputedStyle(document.querySelector('main')).minHeight !== '0px'"
    )
    page.locator("button", has_text="Notify").click()
    expect(page.locator(".q-notification")).to_contain_text("Notification sent")

    page.locator("button", has_text="Dialog").click()
    expect(page.locator(".q-dialog .text-h6")).to_contain_text("Review workflow")
    page.keyboard.press("Escape")

    page.locator(".q-tab", has_text="Tree").click()
    expect(page.locator(".q-tree")).to_contain_text("Qualified")
    assert any("tailwindcss.browser.global.js" in url for url in requests)


@pytest.mark.parametrize(
    "sample_server,title",
    [
        ("static_shell", "Static shell"),
        ("hello_world", "Hello world"),
        ("counter", "Counter"),
        ("multi_view", "Multi-view"),
        ("file_upload", "File upload"),
        ("chat_stream", "Streaming chat"),
        ("three_scene", "Three.js"),
        ("analytics_dashboard", "Analytics Dashboard"),
        ("markdown_render", "Math + sanitised HTML"),
        ("capstone_dashboard", "Capstone dashboard"),
        ("plotly_advanced", "Advanced Plotly"),
        ("extension_workbench", "Extension workbench"),
        ("basic_components", "Basic components"),
    ],
    indirect=["sample_server"],
)
def test_sample_document_titles(sample_server: str, page: Page, title: str) -> None:
    page.goto(sample_server)
    assert page.title() == title
    assert page.title() != "llming"
