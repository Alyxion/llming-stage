"""Guard: ``LIB_VERSION`` in code and the Bundle-version stamp in
``THIRD_PARTY.md`` must agree.

Catches the foot-gun where a maintainer bumps one of the two stamps and
forgets the other — old apps then either get the wrong version segment or
the audit table goes stale.
"""

from __future__ import annotations

import re
from pathlib import Path

from llming_stage import LIB_VERSION

ROOT = Path(__file__).resolve().parent.parent
THIRD_PARTY = ROOT / "THIRD_PARTY.md"

_STAMP_RE = re.compile(r"\*\*Bundle version:\*\*\s+(\d{4}-\d{2}(?:-\d+)?)")


def test_third_party_bundle_version_matches_code() -> None:
    text = THIRD_PARTY.read_text(encoding="utf-8")
    match = _STAMP_RE.search(text)
    assert match, (
        "THIRD_PARTY.md must contain a `**Bundle version:** YYYY-MM` line near "
        "the top so the audit table and llming_stage.LIB_VERSION cannot drift."
    )
    assert match.group(1) == LIB_VERSION, (
        f"THIRD_PARTY.md says Bundle version {match.group(1)!r} but "
        f"llming_stage.LIB_VERSION is {LIB_VERSION!r}. Bump both together."
    )
