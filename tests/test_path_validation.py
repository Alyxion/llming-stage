"""Unit tests for path validation primitives.

These never touch the filesystem — they exercise the textual sanity
checks that run before a request is allowed to reach the asset store.
"""

from __future__ import annotations

import pytest

from llming_stage.asset_server import validate_relative_path


@pytest.mark.parametrize(
    "path",
    [
        "vue.global.prod.js",
        "a/b/c.svg",
        "sub-dir/file_name.woff2",
        "deep/nested/path/with-dashes.mjs",
    ],
)
def test_accepts_safe_paths(path: str) -> None:
    assert validate_relative_path(path) == path


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/",
        "..",
        "../secret",
        "a/../b",
        "a/./b",
        "./a",
        "a//b",
        "a/",
        "/absolute",
        "a\\b",
        "a\x00b",
        "a\nb",
        "a\tb",
        "a\x7fb",
        "a\x1fb",
    ],
)
def test_rejects_unsafe_paths(path: str) -> None:
    assert validate_relative_path(path) is None
