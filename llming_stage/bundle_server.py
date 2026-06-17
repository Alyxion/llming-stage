"""Serve whole data bundles with ETag-based revalidation.

This is the third asset-serving flavour, distinct from its siblings:

- :mod:`asset_server` serves immutable, cache-forever vendor libs.
- :mod:`zip_server` serves individual entries *out of* an archive (the
  server unzips; the client only ever sees one small file at a time).
- :mod:`bundle_server` (this module) serves a **whole data file** — a
  ``.zip``, ``.json`` or binary blob — that the client downloads **once**
  and then reads from locally (in the browser, via fflate for zips). This
  is what makes complex *offline* apps possible: fetch a bundle, cache it,
  and run with no further server round-trips.

Versioning without a manifest
-----------------------------
There is deliberately **no manifest**. Each bundle answers for itself: its
``ETag`` is the SHA-256 of its bytes. A client holding a cached copy asks
about exactly that file with ``If-None-Match``:

- the file is unchanged  → ``304 Not Modified`` (no body) → keep the cache;
- the file was re-prepared → ``200 OK`` with the new bytes and a new ``ETag``;
- the file is gone        → ``404``.

Re-preparing a bundle *in place* is detected automatically: the ETag is
keyed by ``(path, mtime, size)``, so overwriting the file yields a fresh
hash with zero manual version bookkeeping. ``Cache-Control: no-cache`` lets
the browser cache the body but always revalidate, so a plain
``fetch(url)`` performs the conditional dance for free.

The same path-safety rules as :mod:`asset_server` apply.
"""

from __future__ import annotations

import hashlib
import io
import threading
import zipfile
from pathlib import Path

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import FileResponse, Response

from .asset_server import resolve_under_root, validate_relative_path

# Data-bundle extension whitelist. Wider than the vendor-asset list (which is
# JS/CSS/font/svg only) because bundles carry app data, but still a closed set
# — never a catch-all. ``.zip`` is the headline case; ``.json``/``.bin`` cover
# metadata sidecars and raw blobs.
BUNDLE_EXTENSIONS: frozenset[str] = frozenset({".zip", ".json", ".bin"})

_MIME_BY_SUFFIX: dict[str, str] = {
    ".zip": "application/zip",
    ".json": "application/json; charset=utf-8",
    ".bin": "application/octet-stream",
}

# (resolved path, mtime_ns, size) -> sha256 hex. Bounded by the number of
# distinct bundle files; a re-prepared file changes mtime/size and so gets a
# fresh key (the stale entry is simply never read again).
_etag_cache: dict[tuple[str, int, int], str] = {}
_etag_lock = threading.Lock()


def compute_etag(path: Path) -> str:
    """Return the strong ETag (quoted SHA-256) for *path*, memoised by stat.

    The cache key includes mtime and size, so re-preparing a bundle in place
    transparently produces a new ETag without any cache invalidation call.
    """
    st = path.stat()
    key = (str(path), st.st_mtime_ns, st.st_size)
    with _etag_lock:
        cached = _etag_cache.get(key)
    if cached is not None:
        return cached
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    etag = f'"{digest}"'
    with _etag_lock:
        _etag_cache[key] = etag
    return etag


def _media_type_for(path: Path) -> str:
    return _MIME_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")


def _if_none_match_satisfied(header: str | None, etag: str) -> bool:
    """True when an ``If-None-Match`` header matches *etag* (or is ``*``)."""
    if not header:
        return False
    candidates = [token.strip() for token in header.split(",")]
    if "*" in candidates:
        return True
    # Compare ignoring a weak-validator prefix on either side.
    target = etag.lstrip("W/")
    return any(token.lstrip("W/") == target for token in candidates)


class BundleBuilder:
    """Zip a source directory on demand, rebuilding only when it changes.

    The headache with serving a directory as a single downloadable bundle is
    keeping the zip fresh. ``BundleBuilder`` removes it: every call to
    :meth:`build` takes a cheap *signature* of the tree — the sorted
    ``(relpath, mtime_ns, size)`` of every file — and only re-zips when that
    signature differs from the last build. So editing, adding, or removing a
    file under *source* transparently produces a new bundle (and a new
    ETag) on the next request; an unchanged tree returns the cached bytes
    without touching the zip machinery.

    Thread-safe: the rebuild is guarded by a lock so concurrent requests
    don't zip the same tree twice.
    """

    def __init__(
        self,
        source: Path,
        *,
        compression: int = zipfile.ZIP_DEFLATED,
        follow_symlinks: bool = False,
    ) -> None:
        self.source = Path(source).resolve(strict=True)
        if not self.source.is_dir():
            raise NotADirectoryError(f"bundle source is not a directory: {self.source}")
        self._compression = compression
        self._follow_symlinks = follow_symlinks
        self._lock = threading.Lock()
        self._signature: tuple[tuple[str, int, int], ...] | None = None
        self._etag: str | None = None
        self._bytes: bytes | None = None

    def _scan(self) -> tuple[tuple[str, int, int], ...]:
        entries: list[tuple[str, int, int]] = []
        for path in sorted(self.source.rglob("*")):
            if path.is_symlink() and not self._follow_symlinks:
                continue
            if not path.is_file():
                continue
            st = path.stat()
            rel = path.relative_to(self.source).as_posix()
            entries.append((rel, st.st_mtime_ns, st.st_size))
        return tuple(entries)

    def build(self) -> tuple[str, bytes]:
        """Return ``(etag, zip_bytes)``, rebuilding only if the tree changed."""
        signature = self._scan()
        with self._lock:
            if signature == self._signature and self._bytes is not None:
                return self._etag, self._bytes  # type: ignore[return-value]
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", self._compression) as zf:
                for rel, _mtime, _size in signature:
                    zf.write(self.source / rel, rel)
            data = buf.getvalue()
            etag = f'"{hashlib.sha256(data).hexdigest()}"'
            self._signature, self._etag, self._bytes = signature, etag, data
            return etag, data


def make_builder_handler(builder: BundleBuilder, *, cache_control: str = "no-cache"):
    """Build an async handler serving a :class:`BundleBuilder`'s zip.

    Same ETag / ``If-None-Match`` → ``304`` / ``HEAD`` semantics as
    :func:`make_bundle_handler`, but the bytes come from re-zipping the
    source directory whenever it changes. The (possibly blocking) rebuild
    runs in a threadpool so the event loop stays free.
    """

    async def handler(request: Request) -> Response:
        etag, data = await run_in_threadpool(builder.build)
        headers = {"ETag": etag, "Cache-Control": cache_control}
        if _if_none_match_satisfied(request.headers.get("if-none-match"), etag):
            return Response(status_code=304, headers=headers)
        if request.method == "HEAD":
            headers["Content-Length"] = str(len(data))
            return Response(status_code=200, headers=headers, media_type="application/zip")
        return Response(content=data, media_type="application/zip", headers=headers)

    return handler


def make_bundle_handler(
    root: Path,
    *,
    allowed_extensions: frozenset[str] = BUNDLE_EXTENSIONS,
    cache_control: str = "no-cache",
):
    """Build an async Starlette handler that serves data bundles under *root*.

    Handles ``GET`` and ``HEAD``. Sets ``ETag`` (content hash) and
    ``Cache-Control`` on every response, and answers ``304`` to a matching
    ``If-None-Match`` so a cached client revalidates in one round trip.
    Returns ``404`` for any unsafe path, disallowed extension, or missing
    file — "not found" is the single observable rejection outcome.
    """
    root = root.resolve(strict=True)

    async def handler(request: Request) -> Response:
        rel = validate_relative_path(request.path_params.get("path", ""))
        if rel is None:
            return Response(status_code=404)
        if Path(rel).suffix.lower() not in allowed_extensions:
            return Response(status_code=404)
        resolved = resolve_under_root(root, rel)
        if resolved is None:
            return Response(status_code=404)

        etag = compute_etag(resolved)
        headers = {"ETag": etag, "Cache-Control": cache_control}

        if _if_none_match_satisfied(request.headers.get("if-none-match"), etag):
            return Response(status_code=304, headers=headers)

        media_type = _media_type_for(resolved)
        if request.method == "HEAD":
            headers["Content-Length"] = str(resolved.stat().st_size)
            return Response(status_code=200, headers=headers, media_type=media_type)

        return FileResponse(resolved, media_type=media_type, headers=headers)

    return handler
