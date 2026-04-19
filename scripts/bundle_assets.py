"""Bundle vendor libraries, fonts, and icon/emoji archives into the package.

Run this script once (and whenever upstream assets change) to populate
``llming_stage/vendor/``, ``llming_stage/fonts/``, ``llming_stage/lang/``,
and ``llming_stage/assets/*.zip``.

This script **never touches the network**. It only copies from local
source directories — sibling llming projects under ``~/projects`` and a
local NiceGUI install (for fonts, locale packs, and the ``dompurify``
module). Override any source path via the environment variables defined
at the top of the file when running outside the maintainer's local
layout.

Files that do not come from those sources — notably the two Three.js
module files (``three.module.min.js`` + ``three.core.min.js``) — are
downloaded by hand from an authoritative source, verified, and
committed into ``llming_stage/vendor/``. See ``THIRD_PARTY.md`` for the
pinned version and provenance.

The script is idempotent: it overwrites existing files and rebuilds the
zip archives from scratch.
"""

from __future__ import annotations

import os
import shutil
import sys
import zipfile
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent / "llming_stage"
VENDOR_DIR = PKG_ROOT / "vendor"
FONTS_DIR = PKG_ROOT / "fonts"
LANG_DIR = PKG_ROOT / "lang"
ASSETS_DIR = PKG_ROOT / "assets"


_HOME_PROJECTS = Path.home() / "projects"


def _first_match(pattern: str) -> Path | None:
    """Return the first sibling directory matching *pattern* under ~/projects."""
    for path in sorted(_HOME_PROJECTS.glob(pattern)):
        if path.is_dir():
            return path
    return None


def _source(env_name: str, pattern: str, marker: str) -> Path:
    """Resolve a local-dev source path from an env override or an autodetect glob.

    The env var wins if set. Otherwise the first sibling directory under
    ``~/projects`` whose glob match contains *marker* is used. Raises
    ``SystemExit`` with a clear message if nothing is found, so this
    maintainer script never silently fails.
    """
    raw = os.environ.get(env_name)
    if raw:
        return Path(raw).expanduser()
    for path in sorted(_HOME_PROJECTS.glob(pattern)):
        if (path / marker).exists():
            return path
    raise SystemExit(
        f"Could not autodetect source for {env_name}. "
        f"Set {env_name}=/absolute/path to override."
    )


# Local-dev source paths. Not shipped, not referenced at runtime.
VENDOR_SOURCE = _source(
    "STAGE_VENDOR_SOURCE",
    "*/samples/editor/vendor",
    "vue.global.prod.js",
)
EXTRA_VENDOR_SOURCE = _source(
    "STAGE_EXTRA_VENDOR_SOURCE",
    "*/*/static/chat/vendor",
    "katex.min.js",
)
ICONS_SOURCE = _source(
    "STAGE_ICONS_SOURCE",
    "*/*/static/icons",
    "phosphor",
)


def _find_nicegui_static() -> Path:
    """Locate a nicegui install with the static assets we need."""
    candidates = list(_HOME_PROJECTS.glob("*/.venv/lib/python*/site-packages/nicegui/static"))
    candidates += list(_HOME_PROJECTS.glob("*/*/.venv/lib/python*/site-packages/nicegui/static"))
    for c in candidates:
        if (c / "fonts.css").exists():
            return c
    raise SystemExit("Could not find a nicegui install. Bundle assets manually.")


def copy_vendor(nicegui_static: Path) -> None:
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    plan: list[tuple[Path, str]] = [
        (VENDOR_SOURCE / "vue.global.prod.js", "vue.global.prod.js"),
        (VENDOR_SOURCE / "quasar.umd.prod.js", "quasar.umd.prod.js"),
        (VENDOR_SOURCE / "quasar.prod.css", "quasar.prod.css"),
        (VENDOR_SOURCE / "plotly-basic.min.js", "plotly-basic.min.js"),
        (EXTRA_VENDOR_SOURCE / "katex.min.js", "katex.min.js"),
        (EXTRA_VENDOR_SOURCE / "katex.min.css", "katex.min.css"),
        (nicegui_static / "dompurify.mjs", "dompurify.min.js"),
    ]
    for src, dest_name in plan:
        if not src.exists():
            print(f"  skip: missing {src}")
            continue
        shutil.copy2(src, VENDOR_DIR / dest_name)
        print(f"  vendor/{dest_name}  ({src.stat().st_size:>9} bytes)")


def copy_fonts(nicegui_static: Path) -> None:
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    src_fonts = nicegui_static / "fonts"
    src_css = nicegui_static / "fonts.css"
    if not src_fonts.is_dir() or not src_css.is_file():
        print("  skip: nicegui fonts/ or fonts.css missing")
        return
    for entry in src_fonts.iterdir():
        if entry.is_file() and entry.suffix == ".woff2":
            shutil.copy2(entry, FONTS_DIR / entry.name)
    # NiceGUI serves fonts.css at a parent path and woff2 files under
    # a /fonts/ subdir. We keep both in the same directory, so strip
    # the subdir segment from every url(fonts/X) reference.
    css = src_css.read_text().replace("url(fonts/", "url(")
    (FONTS_DIR / "fonts.css").write_text(css)
    print(f"  fonts/  ({len(list(FONTS_DIR.glob('*.woff2')))} woff2 + fonts.css)")


def copy_lang(nicegui_static: Path) -> None:
    LANG_DIR.mkdir(parents=True, exist_ok=True)
    src_lang = nicegui_static / "lang"
    if not src_lang.is_dir():
        print("  skip: nicegui lang/ missing")
        return
    count = 0
    for entry in src_lang.iterdir():
        if entry.is_file() and entry.name.endswith(".umd.prod.js"):
            shutil.copy2(entry, LANG_DIR / entry.name)
            count += 1
    print(f"  lang/  ({count} locale packs)")


def _zip_dir(src_dir: Path, zip_path: Path, *, prefix: str = "") -> None:
    """Write *src_dir* into *zip_path*. Entries are stored uncompressed SVG
    text files benefit from DEFLATE, so we use it here.
    """
    if not src_dir.is_dir():
        print(f"  skip: {src_dir} does not exist")
        return
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(src_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(src_dir)
            if any(part.startswith(".") for part in rel.parts):
                continue
            if path.suffix.lower() != ".svg":
                continue
            arcname = f"{prefix}{rel.as_posix()}" if prefix else rel.as_posix()
            zf.write(path, arcname)
            count += 1
    size = zip_path.stat().st_size
    print(f"  assets/{zip_path.name}  ({count} SVGs, {size:>9} bytes)")


def build_icon_archives() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    phosphor_src = ICONS_SOURCE / "phosphor"
    emoji_src = ICONS_SOURCE / "noto-emoji" / "svg"
    _zip_dir(phosphor_src, ASSETS_DIR / "phosphor-icons.zip")
    _zip_dir(emoji_src, ASSETS_DIR / "noto-emoji.zip")


def main() -> int:
    print(f"Target package root: {PKG_ROOT}")
    try:
        nicegui_static = _find_nicegui_static()
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"Using NiceGUI static: {nicegui_static}")
    print("Vendor libraries:")
    copy_vendor(nicegui_static)
    print("Fonts:")
    copy_fonts(nicegui_static)
    print("Quasar locale packs:")
    copy_lang(nicegui_static)
    print("Icon & emoji archives:")
    build_icon_archives()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
