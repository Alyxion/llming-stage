"""Path-hardened static asset serving.

Each asset group (vendor, fonts, lang) is a separate whitelist-scoped
handler. No generic file serving, no catch-all static mount.

Security guarantees
-------------------
1. **Whitelist-only routing** — each route maps to one fixed root directory.
2. **Path canonicalization** — requested paths are resolved against the root;
   requests that escape the root (via ``..``, absolute paths, or symlinks)
   return 403/404.
3. **Dangerous pattern rejection** — ``..``, backslashes, null bytes, and
   non-ASCII control characters are rejected before the filesystem is touched.
4. **Extension whitelist** — only ``.js``, ``.css``, ``.woff2``, ``.svg``,
   ``.json``, ``.mjs`` are served. Anything else is 404.
5. **No directory listing** — directory requests return 404.
6. **Symlink rejection** — any path component that is a symlink pointing
   outside the root is rejected.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, Response

ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {".js", ".mjs", ".css", ".woff2", ".svg", ".json"}
)

_MIME_OVERRIDES: dict[str, str] = {
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".woff2": "font/woff2",
    ".svg": "image/svg+xml; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}

_FORBIDDEN_SUBSTRINGS: tuple[str, ...] = ("..", "\\", "\x00")


def validate_relative_path(path: str) -> str | None:
    """Return the cleaned path, or ``None`` if the input is unsafe.

    Applies only textual checks — the caller must still resolve against a
    root and verify containment (see :func:`resolve_under_root`).
    """
    if not path:
        return None
    if path.startswith("/"):
        return None
    for bad in _FORBIDDEN_SUBSTRINGS:
        if bad in path:
            return None
    for ch in path:
        code = ord(ch)
        if code < 0x20 or code == 0x7F:
            return None
    for segment in path.split("/"):
        if not segment or segment in (".", ".."):
            return None
    return path


def resolve_under_root(root: Path, rel: str) -> Path | None:
    """Resolve *rel* against *root*, ensuring the result stays inside.

    Returns ``None`` if containment cannot be verified, if any component
    is a symlink pointing outside *root*, or if the resolved path does not
    exist as a regular file.
    """
    root_resolved = root.resolve(strict=True)
    candidate = (root_resolved / rel).resolve(strict=False)
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None
    if not candidate.exists():
        return None
    if not candidate.is_file():
        return None
    current = root_resolved
    for part in Path(rel).parts:
        current = current / part
        try:
            if current.is_symlink():
                real = current.resolve(strict=True)
                real.relative_to(root_resolved)
        except (OSError, ValueError):
            return None
    return candidate


def _media_type_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in _MIME_OVERRIDES:
        return _MIME_OVERRIDES[suffix]
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def make_dir_handler(root: Path, cache_max_age: int = 31536000):
    """Build an async Starlette handler that serves files under *root*.

    The handler reads the relative path from the ``path`` route parameter,
    validates it, resolves it under *root*, and returns the file — or 404
    on any failure. Never returns 403: "not found" is the single observable
    outcome for every rejection path, to avoid leaking structure.
    """
    root = root.resolve(strict=True)
    cache_control = f"public, max-age={cache_max_age}, immutable"

    async def handler(request: Request) -> Response:
        rel = validate_relative_path(request.path_params.get("path", ""))
        if rel is None:
            return Response(status_code=404)
        if Path(rel).suffix.lower() not in ALLOWED_EXTENSIONS:
            return Response(status_code=404)
        resolved = resolve_under_root(root, rel)
        if resolved is None:
            return Response(status_code=404)
        return FileResponse(
            resolved,
            media_type=_media_type_for(resolved),
            headers={"Cache-Control": cache_control},
        )

    return handler
