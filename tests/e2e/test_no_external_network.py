"""Runtime guard: a live gallery session must make zero off-host requests.

Opens the gallery, walks through several samples (including the heavy
ones — Three.js tornado, Plotly full, ECharts dashboard), and asserts
every network request the browser issued stayed on 127.0.0.1 /
localhost. This is the EU-privacy commitment from CLAUDE.md.
"""

from __future__ import annotations

import urllib.parse

import pytest
from playwright.sync_api import Page, expect


SAMPLES_TO_VISIT = [
    "01_static",         # static-only path
    "07_3d_scene",       # tornado — three + addons + shaders
    "08_plotly_dashboard",  # echarts
    "09_markdown_render",   # katex + dompurify lazy load
    "11_plotly_advanced",   # plotly-full (4.8 MB)
]


@pytest.mark.parametrize("sample", SAMPLES_TO_VISIT)
def test_sample_makes_no_external_requests(
    gallery_server, page: Page, sample: str
) -> None:
    base, _ = gallery_server
    base_host = urllib.parse.urlparse(base).hostname

    requests: list[str] = []
    page.on("request", lambda r: requests.append(r.url))

    page.goto(base)
    page.locator(f"[data-sample='{sample}']").click()
    expect(page.locator("[data-test='current']")).to_contain_text(
        sample, timeout=30_000
    )
    # Give the iframe a moment to finish lazy loads.
    page.wait_for_timeout(2_500)

    offenders = []
    for url in requests:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        scheme = parsed.scheme
        # ``data:`` / ``blob:`` / ``about:`` carry no network traffic.
        if scheme in ("data", "blob", "about", "file", "chrome-extension", ""):
            continue
        if host in (base_host, "127.0.0.1", "localhost", None):
            continue
        offenders.append(url)

    assert not offenders, (
        f"{sample} triggered off-host network requests: "
        + "\n  ".join(offenders[:20])
    )
