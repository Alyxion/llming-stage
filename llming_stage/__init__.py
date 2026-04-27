"""llming-stage — shared frontend foundation and SPA app shell.

Public API:
    - :func:`mount_assets` — attach path-hardened asset routes to any
      Starlette/FastAPI app.
    - :func:`mount_shell` — serve the SPA shell HTML document.
    - :func:`mount_dev_reload` — attach development-only reload routes.
    - :class:`Stage` — OOP helper for FastAPI-native stage apps.
    - :class:`StageSession` — Stage-owned llming-com session wiring.
    - :class:`ShellConfig` — configuration dataclass for the shell.
    - :func:`render_shell` — render the shell HTML (for custom wiring).
"""

from __future__ import annotations

from .dev_reload import DevReloadConfig, dev_reload_head, mount_dev_reload
from .shell import ShellConfig, mount_assets, mount_shell, render_shell
from .stage import Stage, StageSession

__all__ = [
    "DevReloadConfig",
    "Stage",
    "StageSession",
    "ShellConfig",
    "dev_reload_head",
    "mount_assets",
    "mount_dev_reload",
    "mount_shell",
    "render_shell",
]

__version__ = "0.1.0"
