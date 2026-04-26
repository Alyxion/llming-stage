"""End-to-end check: every sample respects the gallery's dark/light theme.

For each sample, opens it in the gallery (defaults to dark), then toggles
to light. The sample's iframe ``body`` must carry ``body--dark`` / ``body--light``
correctly, and the *computed* background luminance must move accordingly so
hard-coded light backgrounds in dark mode (and vice versa) are caught.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

# Sample 07 deliberately renders an all-black 3D scene regardless of theme,
# so its body background never inverts. The rest must.
ALWAYS_DARK = {"07_3d_scene"}
SAMPLES = [
    "01_static", "02_hello_world", "03_counter_command", "04_multi_view",
    "05_file_upload", "06_chat_stream", "07_3d_scene", "08_plotly_dashboard",
    "09_markdown_render", "10_full_dashboard", "11_plotly_advanced",
]


def _luminance(rgb_str: str) -> float:
    """Parse ``rgb(r, g, b[, a])`` → relative luminance in [0, 1]."""
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", rgb_str)
    if not m:
        return 0.5
    r, g, b = (int(x) / 255.0 for x in m.groups())
    return 0.299 * r + 0.587 * g + 0.114 * b


def _body_color(frame) -> tuple[str, float]:
    """Resolve the iframe document's effective text color."""
    rgb = frame.locator("body").evaluate(
        "() => getComputedStyle(document.body).color"
    )
    return rgb, _luminance(rgb)


def _body_bg(frame) -> tuple[str, float]:
    """Resolve the iframe document's effective root background.

    Reads ``body``'s computed bg, then ``html``'s; if both are
    transparent, the browser paints white — return that. Semi-
    transparent values (e.g. nav overlays at alpha 0.02) are
    treated as transparent so they don't fool the test into
    thinking the page bg is black.
    """
    rgb = frame.locator("body").evaluate(
        """() => {
          const isOpaque = (c) => {
            const m = c && c.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)(?:,\\s*([0-9.]+))?\\)/);
            if (!m) return false;
            const a = m[4] === undefined ? 1 : parseFloat(m[4]);
            return a >= 0.5;
          };
          const styles = (e) => getComputedStyle(e).backgroundColor;
          const b = styles(document.body);
          if (isOpaque(b)) return b;
          const h = styles(document.documentElement);
          if (isOpaque(h)) return h;
          return 'rgb(255, 255, 255)';
        }"""
    )
    return rgb, _luminance(rgb)


@pytest.mark.parametrize("sample_name", SAMPLES)
def test_sample_theme(gallery_server, page: Page, sample_name: str) -> None:
    base, _ = gallery_server
    page.goto(base)
    page.locator(f"[data-sample='{sample_name}']").click()
    expect(page.locator("[data-test='current']")).to_contain_text(
        sample_name, timeout=25_000
    )

    frame = page.frame_locator("[data-test='frame']")
    body = frame.locator("body")

    # Gallery defaults to dark.
    expect(body).to_have_class(
        re.compile(r"\bbody--dark\b"), timeout=15_000
    )
    page.wait_for_timeout(400)
    rgb_dark, lum_dark = _body_bg(frame)

    # Toggle to light.
    page.locator("[data-test='btn-dark']").click()
    expect(body).to_have_class(
        re.compile(r"\bbody--light\b"), timeout=15_000
    )
    page.wait_for_timeout(400)
    rgb_light, lum_light = _body_bg(frame)

    # Foreground text colour also has to invert — otherwise we'd ship
    # dark-text-on-dark-bg or vice versa.
    page.locator(f"[data-sample='{sample_name}']").click()
    expect(body).to_have_class(re.compile(r"\bbody--light\b"), timeout=10_000)
    page.wait_for_timeout(200)
    fg_light_rgb, fg_light = _body_color(frame)
    page.locator("[data-test='btn-dark']").click()
    expect(body).to_have_class(re.compile(r"\bbody--dark\b"), timeout=10_000)
    page.wait_for_timeout(200)
    fg_dark_rgb, fg_dark = _body_color(frame)

    if sample_name in ALWAYS_DARK:
        return

    assert lum_dark < 0.4, (
        f"{sample_name}: body bg in dark mode is too bright "
        f"(rgb={rgb_dark}, lum={lum_dark:.2f})"
    )
    assert lum_light > 0.6, (
        f"{sample_name}: body bg in light mode is too dark "
        f"(rgb={rgb_light}, lum={lum_light:.2f})"
    )
    assert lum_light - lum_dark > 0.3, (
        f"{sample_name}: theme didn't actually flip "
        f"(dark={lum_dark:.2f}, light={lum_light:.2f})"
    )
    assert fg_dark > 0.6, (
        f"{sample_name}: text color in dark mode is too dark "
        f"(rgb={fg_dark_rgb}, lum={fg_dark:.2f})"
    )
    assert fg_light < 0.5, (
        f"{sample_name}: text color in light mode is too bright "
        f"(rgb={fg_light_rgb}, lum={fg_light:.2f})"
    )
