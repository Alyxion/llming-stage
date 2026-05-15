"""llming-stage — shared frontend foundation and SPA app shell.

Public API:
    - :func:`mount_assets` — attach path-hardened asset routes to any
      Starlette/FastAPI app.
    - :func:`mount_shell` — serve the SPA shell HTML document.
    - :func:`mount_dev_reload` — attach development-only reload routes.
    - :class:`Stage` — OOP helper for FastAPI-native stage apps.
    - :class:`StageSession` — Stage-owned llming-com session wiring.
    - :class:`VueResponse` — response type for generated Vue views.
    - :class:`ShellConfig` — configuration dataclass for the shell.
    - :func:`render_shell` — render the shell HTML (for custom wiring).
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version

from .debug import is_debug_enabled, mount_debug
from .dev_reload import DevReloadConfig, dev_reload_head, mount_dev_reload
from .shell import (
    ShellConfig,
    export_package_assets,
    mount_assets,
    mount_shell,
    render_shell,
)
from .stage import Stage, StageSession, VueResponse

__all__ = [
    "DevReloadConfig",
    "LIB_VERSION",
    "Stage",
    "StageSession",
    "ShellConfig",
    "VueResponse",
    "dev_reload_head",
    "export_package_assets",
    "is_debug_enabled",
    "mount_assets",
    "mount_debug",
    "mount_dev_reload",
    "mount_shell",
    "render_shell",
]

try:
    __version__ = _pkg_version("llming-stage")
except PackageNotFoundError:
    __version__ = "0.0.0+local"

# Vendor-bundle version. Bump this WHENEVER any file under
# llming_stage/{vendor, fonts, lang, assets}/ is swapped. Format YYYY-MM
# (with optional -NN suffix for in-month refreshes). Keep in sync with
# the same stamp at the top of THIRD_PARTY.md — a test enforces this.
LIB_VERSION = "2026-05"
