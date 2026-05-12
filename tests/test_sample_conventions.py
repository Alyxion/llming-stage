"""Guards for the public sample-app authoring style."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
SAMPLE_VIEWS = sorted(
    path for path in SAMPLES.glob("*/*.vue") if path.parent.is_dir()
)
SAMPLE_MAINS = sorted(SAMPLES.glob("*/main.py"))
# Tailwind utilities whose plain (no-opacity, no-arbitrary-value) form collides
# with Quasar's `!important` color utilities — Quasar's rule wins, so paired
# `dark:` variants silently fail. Use opacity-suffixed variants (e.g. `bg-white/80`)
# or arbitrary values (`bg-[#ffffff]`) when a `dark:` partner is expected.
QUASAR_TAILWIND_COLLISIONS = {"bg-white", "bg-black", "text-white", "text-black"}


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
    assert not [
        path
        for path in SAMPLES.glob("*/static/*.js")
        if path.parent.parent.is_dir()
    ]


@pytest.mark.parametrize("path", SAMPLE_MAINS, ids=lambda p: str(p.relative_to(ROOT)))
def test_sample_main_files_use_public_apis(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    forbidden = {
        "samples._common": "samples must not import private shared helpers",
        "from _common": "samples must not import private shared helpers",
        "import _common": "samples must not import private shared helpers",
        "HERE =": "samples should not need explicit root variables",
        "ROOT =": "samples should not need explicit root variables",
        "from pathlib import Path": "samples should not need explicit root variables",
        "uvicorn.run(": "samples should use the public thin stage.run() helper",
        ".router(": "samples should use active add_router(...) names",
        ".app_router(": "samples should use active add_app_router(...) names",
        "def home() -> None:": "samples should not declare no-op view handlers",
        "pass\n": "samples should not contain no-op scaffolding",
    }
    offenders = [reason for needle, reason in forbidden.items() if needle in text]
    for line in text.splitlines():
        if "stage.view(" in line and not line.strip().startswith("@stage.view("):
            offenders.append("stage.view(...) is decorator-only; use stage.add_view(...)")
    if "@stage.view(" in text and "-> str:" in text:
        offenders.append("decorated views should return VueResponse or HTMLResponse, not raw str")
    assert not offenders, f"{path.relative_to(ROOT)} violates sample conventions: {sorted(set(offenders))}"


_SAMPLE_TEMPLATE_FILES = sorted(
    {*SAMPLE_VIEWS, *SAMPLES.glob("*/main.py")}
)


@pytest.mark.parametrize("path", _SAMPLE_TEMPLATE_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_quasar_component_class_on_plain_div(path: Path) -> None:
    # Quasar handles dark-mode switching inside its components, not via its
    # bare CSS classes. `<div class="q-card">` stays white in dark mode;
    # `<q-card>` automatically gains `q-card--dark`. Same for other components.
    text = path.read_text(encoding="utf-8")
    component_classes = {"q-card", "q-banner", "q-chip", "q-btn"}
    offenders: list[str] = []
    for match in re.finditer(r'<div\b[^>]*\bclass=["\']([^"\']+)["\']', text):
        hits = sorted(set(match.group(1).split()) & component_classes)
        if hits:
            offenders.append(f"<div class=\"…{hits[0]}…\"> — use <{hits[0]}> component")
    assert not offenders, (
        f"{path.relative_to(ROOT)}: Quasar component classes on a <div> skip dark-mode "
        f"handling. Hits: {offenders}"
    )


@pytest.mark.parametrize("path", _SAMPLE_TEMPLATE_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_quasar_tailwind_collision_with_dark_variant(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    offenders: list[str] = []
    for match in re.finditer(r'class=["\']([^"\']+)["\']', text):
        classes = match.group(1).split()
        if not any(c.startswith("dark:") for c in classes):
            continue
        collisions = sorted(set(classes) & QUASAR_TAILWIND_COLLISIONS)
        if collisions:
            offenders.append(f"{collisions} paired with dark: variant in: {match.group(1)[:120]}")
    assert not offenders, (
        f"{path.relative_to(ROOT)}: Quasar's !important {QUASAR_TAILWIND_COLLISIONS} "
        f"override Tailwind dark: variants. Use bg-white/100 / bg-[#ffffff] / text-slate-* "
        f"etc. Hits: {offenders}"
    )
