"""Guards for the public sample-app authoring style."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
SAMPLE_VIEWS = sorted(SAMPLES.glob("[0-9][0-9]_*/*.vue"))


@pytest.mark.parametrize("path", SAMPLE_VIEWS, ids=lambda p: str(p.relative_to(ROOT)))
def test_sample_views_are_declarative_vue(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    forbidden = {
        "<style": "use Tailwind/Quasar classes instead of sample-local CSS",
        "style=\"": "use Tailwind/Quasar classes instead of inline CSS",
        "style='": "use Tailwind/Quasar classes instead of inline CSS",
        "innerHTML": "do not build sample UI with imperative HTML strings",
        "insertAdjacentHTML": "do not build sample UI with imperative HTML strings",
        "onMessage": "use $stage method dispatch instead of app-level message parsers",
        "new window.LlmingWebSocket": "use this.$stage.connect() in samples",
    }
    offenders = [reason for needle, reason in forbidden.items() if needle in text]
    assert not offenders, f"{path.relative_to(ROOT)} violates sample conventions: {sorted(set(offenders))}"


def test_sample_views_are_not_hidden_in_static_dirs() -> None:
    assert not list(SAMPLES.glob("[0-9][0-9]_*/static/*.js"))
