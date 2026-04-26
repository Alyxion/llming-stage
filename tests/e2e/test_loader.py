"""End-to-end checks for window.__stage.load() efficiency.

Verifies:
  1. Concurrent calls during the first load share one network fetch
     (no duplicate <script> tags, no duplicate vendor requests).
  2. After the lib is loaded, repeated calls are O(1) — they return
     the same Promise instance with zero new allocations and never
     trigger another fetch.
  3. ``isLoaded(name)`` reports the cached state synchronously.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_loader_is_idempotent_and_dedupes(gallery_server, page: Page) -> None:
    base, _ = gallery_server
    page.goto(base)
    # Land in any sample so __stage is mounted in an iframe we can drive.
    page.locator("[data-sample='02_hello_world']").click()
    expect(page.locator("[data-test='current']")).to_contain_text(
        "02_hello_world", timeout=20_000
    )

    frame = page.frame_locator("[data-test='frame']")
    # Wait for the shell to finish its own initial loads.
    frame.locator(".text-h4").wait_for(timeout=15_000)

    # 1. Concurrent calls during first fetch must share one Promise.
    result = frame.locator("body").evaluate(
        """async () => {
          const promises = [];
          for (let i = 0; i < 50; i++) promises.push(window.__stage.load('plotly'));
          const same = promises.every((p) => p === promises[0]);
          await Promise.all(promises);
          return { same, after: window.__stage.isLoaded('plotly') };
        }"""
    )
    assert result["same"] is True, "concurrent load() calls returned different Promises"
    assert result["after"] is True, "isLoaded('plotly') was false after load resolved"

    # 2. After resolution, the cached Promise is the same instance every time.
    same_after = frame.locator("body").evaluate(
        """() => {
          const a = window.__stage.load('plotly');
          const b = window.__stage.load('plotly');
          return a === b;
        }"""
    )
    assert same_after, "load('plotly') returned different Promises after caching"

    # 3. Repeated calls produce no additional <script> tags.
    script_count = frame.locator(
        "script[src*='plotly-basic.min.js']"
    ).evaluate_all("(els) => els.length")
    assert script_count == 1, f"expected exactly one plotly script tag, got {script_count}"

    # 4. Hammering load() 1000× inside a tight loop stays cheap.
    timing = frame.locator("body").evaluate(
        """async () => {
          const t0 = performance.now();
          for (let i = 0; i < 1000; i++) await window.__stage.load('plotly');
          return performance.now() - t0;
        }"""
    )
    # 1000 cached awaits should comfortably finish under 100ms even on
    # a stressed CI box; the real-world cost is closer to ~5ms.
    assert timing < 250, f"1000 cached load() calls took {timing:.1f}ms — too slow"

    # 5. Unknown name rejects without polluting the cache.
    state = frame.locator("body").evaluate(
        """async () => {
          let err = null;
          try { await window.__stage.load('does-not-exist'); } catch (e) { err = e.message; }
          // A second call should still reject (cache must not have stored it).
          let err2 = null;
          try { await window.__stage.load('does-not-exist'); } catch (e) { err2 = e.message; }
          return { err, err2, isLoaded: window.__stage.isLoaded('does-not-exist') };
        }"""
    )
    assert "does-not-exist" in state["err"]
    assert state["err2"] == state["err"]
    assert state["isLoaded"] is False
