"""Static guard: our own code must not reference any external CDN host.

Scans every non-vendor source file for known third-party CDN hostnames.
The rule is documented in CLAUDE.md ("No External Network — STRICTLY
ENFORCED"). Vendored library files in ``llming_stage/vendor/`` are
exempt because they contain attribution URLs in license comments, not
active fetches.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# Hosts forbidden in our own code. Comments inside upstream library
# distributions (vendor/) are exempt — those are attribution text.
FORBIDDEN_HOSTS = [
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "ajax.googleapis.com",
    "www.google-analytics.com",
    "www.googletagmanager.com",
    "cdn.jsdelivr.net",
    "unpkg.com",
    "cdnjs.cloudflare.com",
    "stackpath.bootstrapcdn.com",
    "use.fontawesome.com",
    "platform.twitter.com",
    "connect.facebook.net",
]

# We only scan files we author. The vendor directory is upstream code
# whose license-comment URLs do not represent runtime fetches; the
# runtime scan in ``tests/e2e/test_no_external_network.py`` covers
# whether they're ever actually hit.
SCAN_GLOBS = (
    "llming_stage/*.py",
    "llming_stage/static/*.js",
    "samples/**/*.py",
    "samples/**/*.vue",
    "samples/**/*.js",
    "samples/**/*.md",
    "samples/**/*.html",
    "scripts/*.py",
    "docs/content/*.md",
    "README.md",
    "CLAUDE.md",
)

_PATTERN = re.compile(
    r"https?://(" + "|".join(re.escape(h) for h in FORBIDDEN_HOSTS) + r")",
    re.IGNORECASE,
)


def _scan_targets() -> list[Path]:
    paths: list[Path] = []
    for pat in SCAN_GLOBS:
        paths.extend(REPO.glob(pat))
    # Skip the file you're currently reading — its FORBIDDEN_HOSTS
    # list contains the very strings we're searching for.
    me = Path(__file__).resolve()
    return [p for p in paths if p.resolve() != me]


@pytest.mark.parametrize("path", _scan_targets(), ids=lambda p: str(p.relative_to(REPO)))
def test_file_has_no_external_cdn_reference(path: Path) -> None:
    text = path.read_text(errors="ignore")
    matches = _PATTERN.findall(text)
    assert not matches, (
        f"{path.relative_to(REPO)} references forbidden CDN host(s): {set(matches)} — "
        "vendor any external asset locally; see CLAUDE.md "
        '"No External Network — STRICTLY ENFORCED".'
    )
