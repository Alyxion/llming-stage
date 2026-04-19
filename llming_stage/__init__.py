"""llming-stage — shared frontend foundation and SPA app shell.

Public API:
    - :func:`mount_assets` — attach path-hardened asset routes to any
      Starlette/FastAPI app.
    - :func:`mount_shell` — serve the SPA shell HTML document.
    - :class:`ShellConfig` — configuration dataclass for the shell.
    - :func:`render_shell` — render the shell HTML (for custom wiring).
"""

from __future__ import annotations

from .shell import ShellConfig, mount_assets, mount_shell, render_shell

__all__ = ["ShellConfig", "mount_assets", "mount_shell", "render_shell"]

__version__ = "0.1.0"
