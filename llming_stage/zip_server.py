"""Serve individual files from a zip archive.

Used for icon and emoji sets where thousands of small SVGs would bloat
the wheel's file listing. The archive is opened once at mount time and
kept as a process-resident :class:`zipfile.ZipFile`; requests read entry
bytes directly from memory via :meth:`ZipFile.read`. No file is ever
extracted to disk.

The same path-safety rules used by :mod:`asset_server` apply here.
"""

from __future__ import annotations

import threading
import zipfile
from pathlib import Path

from starlette.requests import Request
from starlette.responses import Response

from .asset_server import (
    ALLOWED_EXTENSIONS,
    _MIME_OVERRIDES,
    validate_relative_path,
)


class ZipArchive:
    """Thread-safe read-only view over a zip file, with an entry whitelist.

    Entry names are validated at open time: any entry whose name fails
    :func:`validate_relative_path` or whose extension is not in the allow
    list is silently excluded from the whitelist. Requests for excluded
    entries return 404.
    """

    def __init__(self, archive_path: Path) -> None:
        self._path = archive_path.resolve(strict=True)
        self._lock = threading.Lock()
        self._zip = zipfile.ZipFile(self._path, mode="r")
        self._entries: dict[str, zipfile.ZipInfo] = {}
        for info in self._zip.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if validate_relative_path(name) is None:
                continue
            if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
                continue
            self._entries[name] = info

    @property
    def path(self) -> Path:
        return self._path

    def read(self, name: str) -> bytes | None:
        info = self._entries.get(name)
        if info is None:
            return None
        with self._lock:
            return self._zip.read(info)

    def close(self) -> None:
        with self._lock:
            self._zip.close()

    def __len__(self) -> int:
        return len(self._entries)


def _media_type_for_entry(name: str) -> str:
    suffix = Path(name).suffix.lower()
    return _MIME_OVERRIDES.get(suffix, "application/octet-stream")


def make_zip_handler(archive: ZipArchive, cache_max_age: int = 31536000):
    """Build an async Starlette handler that serves entries from *archive*."""
    cache_control = f"public, max-age={cache_max_age}, immutable"

    async def handler(request: Request) -> Response:
        rel = validate_relative_path(request.path_params.get("path", ""))
        if rel is None:
            return Response(status_code=404)
        if Path(rel).suffix.lower() not in ALLOWED_EXTENSIONS:
            return Response(status_code=404)
        data = archive.read(rel)
        if data is None:
            return Response(status_code=404)
        return Response(
            content=data,
            media_type=_media_type_for_entry(rel),
            headers={"Cache-Control": cache_control},
        )

    return handler
