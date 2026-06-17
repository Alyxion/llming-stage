"""Tests for the ETag-revalidated data-bundle routes and zip serving."""

from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from llming_stage import mount_bundle_builder, mount_bundles
from llming_stage.bundle_server import (
    BundleBuilder,
    compute_etag,
    make_bundle_handler,
    make_builder_handler,
)


def _make_demo_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("config.json", json.dumps({"title": "demo", "items": [1, 2, 3]}))
        zf.writestr("logo.svg", "<svg>logo</svg>")
        zf.writestr("README.txt", "extracted in the browser")
    return buf.getvalue()


@pytest.fixture
def bundle_dir(tmp_path: Path) -> Path:
    (tmp_path / "demo.zip").write_bytes(_make_demo_zip())
    (tmp_path / "meta.json").write_text('{"ok": true}', encoding="utf-8")
    (tmp_path / "secret.txt").write_text("not a bundle", encoding="utf-8")
    return tmp_path


@pytest.fixture
def client(bundle_dir: Path) -> TestClient:
    handler = make_bundle_handler(bundle_dir)
    app = Starlette(
        routes=[Route("/bundles/{path:path}", handler, methods=["GET", "HEAD"])]
    )
    return TestClient(app)


# ---- zip usage: the bundle is served intact and unzips correctly ----------


def test_serves_zip_with_content_type_and_etag(client: TestClient) -> None:
    r = client.get("/bundles/demo.zip")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert r.headers["etag"].startswith('"') and r.headers["etag"].endswith('"')
    assert r.headers["cache-control"] == "no-cache"


def test_served_zip_is_valid_and_entries_round_trip(client: TestClient) -> None:
    r = client.get("/bundles/demo.zip")
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert set(zf.namelist()) == {"config.json", "logo.svg", "README.txt"}
        cfg = json.loads(zf.read("config.json"))
        assert cfg == {"title": "demo", "items": [1, 2, 3]}
        assert zf.read("logo.svg") == b"<svg>logo</svg>"


def test_etag_is_quoted_sha256_of_bytes(client: TestClient, bundle_dir: Path) -> None:
    r = client.get("/bundles/demo.zip")
    expected = hashlib.sha256((bundle_dir / "demo.zip").read_bytes()).hexdigest()
    assert r.headers["etag"] == f'"{expected}"'


# ---- conditional revalidation (versioning without a manifest) -------------


def test_matching_if_none_match_returns_304_no_body(client: TestClient) -> None:
    etag = client.get("/bundles/demo.zip").headers["etag"]
    r = client.get("/bundles/demo.zip", headers={"If-None-Match": etag})
    assert r.status_code == 304
    assert r.content == b""
    assert r.headers["etag"] == etag


def test_stale_if_none_match_returns_200_with_new_bytes(client: TestClient) -> None:
    r = client.get("/bundles/demo.zip", headers={"If-None-Match": '"deadbeef"'})
    assert r.status_code == 200
    assert len(r.content) > 0


def test_if_none_match_star_returns_304(client: TestClient) -> None:
    r = client.get("/bundles/demo.zip", headers={"If-None-Match": "*"})
    assert r.status_code == 304


def test_etag_changes_when_bundle_reprepared(client: TestClient, bundle_dir: Path) -> None:
    first = client.get("/bundles/demo.zip").headers["etag"]
    # Re-prepare the bundle in place with different content (and bump mtime).
    path = bundle_dir / "demo.zip"
    new_bytes = _make_demo_zip() + b"\x00extra-changed-content"
    path.write_bytes(new_bytes)
    os.utime(path, (path.stat().st_atime + 5, path.stat().st_mtime + 5))
    second = client.get("/bundles/demo.zip").headers["etag"]
    assert second != first


# ---- HEAD --------------------------------------------------------------


def test_head_returns_etag_and_length_without_body(client: TestClient, bundle_dir: Path) -> None:
    r = client.head("/bundles/demo.zip")
    assert r.status_code == 200
    assert r.content == b""
    assert r.headers["etag"]
    assert int(r.headers["content-length"]) == (bundle_dir / "demo.zip").stat().st_size


def test_head_with_matching_etag_returns_304(client: TestClient) -> None:
    etag = client.get("/bundles/demo.zip").headers["etag"]
    r = client.head("/bundles/demo.zip", headers={"If-None-Match": etag})
    assert r.status_code == 304


# ---- json bundles ------------------------------------------------------


def test_serves_json_bundle(client: TestClient) -> None:
    r = client.get("/bundles/meta.json")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert r.json() == {"ok": True}


# ---- security: hardened like the other asset routes --------------------


def test_rejects_disallowed_extension(client: TestClient) -> None:
    assert client.get("/bundles/secret.txt").status_code == 404


def test_rejects_traversal(client: TestClient) -> None:
    assert client.get("/bundles/../conftest.py").status_code == 404


def test_rejects_missing_bundle(client: TestClient) -> None:
    assert client.get("/bundles/ghost.zip").status_code == 404


# ---- compute_etag memoisation -----------------------------------------


def test_compute_etag_stable_then_changes_on_rewrite(tmp_path: Path) -> None:
    f = tmp_path / "b.bin"
    f.write_bytes(b"one")
    e1 = compute_etag(f)
    assert e1 == compute_etag(f)  # memoised, identical
    f.write_bytes(b"two-longer")  # different size → new stat key
    os.utime(f, (f.stat().st_atime + 5, f.stat().st_mtime + 5))
    assert compute_etag(f) != e1


# ---- mount_bundles helper ---------------------------------------------


def test_mount_bundles_serves_directory(bundle_dir: Path) -> None:
    app = Starlette()
    mount_bundles(app, bundle_dir)
    r = TestClient(app).get("/bundles/demo.zip")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"


def test_mount_bundles_is_idempotent(bundle_dir: Path) -> None:
    app = Starlette()
    mount_bundles(app, bundle_dir)
    before = len(app.router.routes)
    mount_bundles(app, bundle_dir)
    assert len(app.router.routes) == before


def test_mount_bundles_custom_prefix(bundle_dir: Path) -> None:
    app = Starlette()
    mount_bundles(app, bundle_dir, prefix="/assets/data")
    assert TestClient(app).get("/assets/data/demo.zip").status_code == 200


def test_mount_bundles_missing_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        mount_bundles(Starlette(), tmp_path / "nope")


# ---- self-building bundle (BundleBuilder) -----------------------------


@pytest.fixture
def src_dir(tmp_path: Path) -> Path:
    d = tmp_path / "src"
    (d / "img").mkdir(parents=True)
    (d / "config.json").write_text('{"v": 1}', encoding="utf-8")
    (d / "img" / "a.svg").write_text("<svg>a</svg>", encoding="utf-8")
    return d


def test_builder_zips_source_tree(src_dir: Path) -> None:
    etag, data = BundleBuilder(src_dir).build()
    assert etag.startswith('"')
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert set(zf.namelist()) == {"config.json", "img/a.svg"}
        assert zf.read("img/a.svg") == b"<svg>a</svg>"


def test_builder_caches_until_tree_changes(src_dir: Path) -> None:
    builder = BundleBuilder(src_dir)
    etag1, data1 = builder.build()
    etag2, data2 = builder.build()
    assert etag1 == etag2
    assert data1 is data2  # same object: no rebuild when unchanged


def test_builder_rebuilds_when_file_edited(src_dir: Path) -> None:
    builder = BundleBuilder(src_dir)
    etag1, _ = builder.build()
    f = src_dir / "config.json"
    f.write_text('{"v": 2, "more": true}', encoding="utf-8")  # different size
    os.utime(f, (f.stat().st_atime + 5, f.stat().st_mtime + 5))
    etag2, _ = builder.build()
    assert etag2 != etag1


def test_builder_rebuilds_when_file_added(src_dir: Path) -> None:
    builder = BundleBuilder(src_dir)
    etag1, _ = builder.build()
    (src_dir / "img" / "b.svg").write_text("<svg>b</svg>", encoding="utf-8")
    etag2, data2 = builder.build()
    assert etag2 != etag1
    with zipfile.ZipFile(io.BytesIO(data2)) as zf:
        assert "img/b.svg" in zf.namelist()


def test_builder_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        BundleBuilder(tmp_path / "missing")


def test_builder_source_not_dir_raises(tmp_path: Path) -> None:
    f = tmp_path / "file.txt"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        BundleBuilder(f)


def test_builder_handler_serves_and_revalidates(src_dir: Path) -> None:
    handler = make_builder_handler(BundleBuilder(src_dir))
    app = Starlette(routes=[Route("/b.zip", handler, methods=["GET", "HEAD"])])
    client = TestClient(app)
    r = client.get("/b.zip")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    etag = r.headers["etag"]
    assert client.get("/b.zip", headers={"If-None-Match": etag}).status_code == 304
    head = client.head("/b.zip")
    assert head.status_code == 200 and head.content == b""
    assert int(head.headers["content-length"]) > 0


def test_mount_bundle_builder_rebuilds_over_http(src_dir: Path) -> None:
    app = Starlette()
    mount_bundle_builder(app, src_dir, url="/bundles/media.zip")
    client = TestClient(app)
    etag1 = client.get("/bundles/media.zip").headers["etag"]
    # Edit the source → the served bundle's ETag changes with no rebuild call.
    new = src_dir / "img" / "c.svg"
    new.write_text("<svg>c</svg>", encoding="utf-8")
    etag2 = client.get("/bundles/media.zip").headers["etag"]
    assert etag2 != etag1
    with zipfile.ZipFile(io.BytesIO(client.get("/bundles/media.zip").content)) as zf:
        assert "img/c.svg" in zf.namelist()
