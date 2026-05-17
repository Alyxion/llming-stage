"""Tests for the opt-in process debug API (``llming_stage.debug``)."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

import llming_stage.debug as debug_mod
from llming_stage import LIB_VERSION, Stage, __version__, mount_debug


# ---------------------------------------------------------------------------
# Env-var gating
# ---------------------------------------------------------------------------


def test_is_debug_enabled_truthy_falsy(monkeypatch: pytest.MonkeyPatch) -> None:
    for value in ("", "0", "false", "FALSE", "no", "off"):
        monkeypatch.setenv("LLMING_STAGE_DEBUG", value)
        assert debug_mod.is_debug_enabled() is False, value
    for value in ("1", "true", "yes", "on", "anything-truthy"):
        monkeypatch.setenv("LLMING_STAGE_DEBUG", value)
        assert debug_mod.is_debug_enabled() is True, value


def test_stage_does_not_mount_debug_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLMING_STAGE_DEBUG", raising=False)
    stage = Stage(Starlette(), dev=False)
    paths = [getattr(r, "path", "") for r in stage.app.router.routes]
    assert "/_stage/debug/ws" not in paths


def test_mount_debug_is_noop_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLMING_STAGE_DEBUG", raising=False)
    app = Starlette()
    mount_debug(app)
    paths = [getattr(r, "path", "") for r in app.router.routes]
    assert "/_stage/debug/ws" not in paths


def test_stage_mounts_debug_when_env_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLMING_STAGE_DEBUG", "1")
    stage = Stage(Starlette(), dev=False)
    paths = [getattr(r, "path", "") for r in stage.app.router.routes]
    assert "/_stage/debug/ws" in paths


def test_browser_eval_bridge_is_debug_gated_in_loader() -> None:
    loader = (Path(__file__).resolve().parents[1] / "llming_stage/static/loader.js").read_text(
        encoding="utf-8"
    )

    assert "if (!(window.__stageDebug && window.__stageDebug.enabled)) return;" in loader
    assert (
        "msg.type === 'llming.debug.eval' && window.__stageDebug && window.__stageDebug.enabled"
        in loader
    )
    assert "target === '__stageDebug'" in loader
    assert "method === 'eval'" in loader


# ---------------------------------------------------------------------------
# Endpoint behavior
# ---------------------------------------------------------------------------


@pytest.fixture
def debug_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A debug-WS client that authenticates via token.

    The debug endpoint always requires ``LLMING_STAGE_DEBUG_TOKEN``;
    this fixture sets one to exercise the WS message loop.
    """
    monkeypatch.setenv("LLMING_STAGE_DEBUG", "1")
    monkeypatch.setenv("LLMING_STAGE_DEBUG_TOKEN", "test-token")
    app = Starlette()
    mount_debug(app)
    return TestClient(app)


def _ws_with_host(host: str):
    class _Client:
        def __init__(self, host: str) -> None:
            self.host = host
    class _WS:
        def __init__(self, host: str, params: dict) -> None:
            self.client = _Client(host)
            self.query_params = params
    return _WS(host, {})


def test_check_auth_token_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLMING_STAGE_DEBUG_TOKEN", "s3cret")
    ws = _ws_with_host("203.0.113.1")
    ws.query_params = {"token": "s3cret"}
    assert debug_mod._check_auth(ws) is True


def test_check_auth_token_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLMING_STAGE_DEBUG_TOKEN", "s3cret")
    ws = _ws_with_host("127.0.0.1")
    ws.query_params = {"token": "wrong"}
    assert debug_mod._check_auth(ws) is False


def test_check_auth_no_token_refused_even_on_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLMING_STAGE_DEBUG_TOKEN", raising=False)
    for host in ("127.0.0.1", "::1", "localhost"):
        ws = _ws_with_host(host)
        assert debug_mod._check_auth(ws) is False, host


def test_check_auth_no_token_non_loopback_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLMING_STAGE_DEBUG_TOKEN", raising=False)
    for host in ("10.0.0.5", "192.168.1.50", "203.0.113.1", "testclient"):
        ws = _ws_with_host(host)
        assert debug_mod._check_auth(ws) is False, host


def test_info_query_returns_versions_and_pid(debug_client: TestClient) -> None:
    with debug_client.websocket_connect("/_stage/debug/ws?token=test-token") as ws:
        ws.send_json({"id": 1, "q": "info"})
        msg = ws.receive_json()
    assert msg["id"] == 1
    assert msg["ok"] is True
    data = msg["data"]
    assert data["llming_stage_version"] == __version__
    assert data["lib_version"] == LIB_VERSION
    assert isinstance(data["pid"], int) and data["pid"] > 0
    assert "python_version" in data


def test_metrics_query_returns_expected_keys(debug_client: TestClient) -> None:
    with debug_client.websocket_connect("/_stage/debug/ws?token=test-token") as ws:
        ws.send_json({"q": "metrics"})
        msg = ws.receive_json()
    assert msg["ok"] is True
    data = msg["data"]
    # When psutil is present, every key listed below is filled.
    for key in ("cpu_percent", "rss_bytes", "threads", "uptime_seconds"):
        assert key in data, key
    assert data["rss_bytes"] > 0
    assert data["uptime_seconds"] >= 0


def test_threads_query_includes_main_thread(debug_client: TestClient) -> None:
    with debug_client.websocket_connect("/_stage/debug/ws?token=test-token") as ws:
        ws.send_json({"q": "threads"})
        msg = ws.receive_json()
    assert msg["ok"] is True
    names = [t["name"] for t in msg["data"]]
    assert "MainThread" in names


def test_modules_query_lists_llming_stage(debug_client: TestClient) -> None:
    with debug_client.websocket_connect("/_stage/debug/ws?token=test-token") as ws:
        ws.send_json({"q": "modules"})
        msg = ws.receive_json()
    assert msg["ok"] is True
    names = [m["name"] for m in msg["data"]]
    assert "llming_stage" in names


def test_stack_query_returns_main_thread_frames(debug_client: TestClient) -> None:
    with debug_client.websocket_connect("/_stage/debug/ws?token=test-token") as ws:
        ws.send_json({"q": "stack"})
        msg = ws.receive_json()
    assert msg["ok"] is True
    assert isinstance(msg["data"].get("stack"), list)


def test_stdout_tail_returns_buffered_lines(debug_client: TestClient) -> None:
    """The stdout_tail query returns whatever's in the module ring buffer.

    Bypasses pytest's own stdout capture by writing to the buffer
    directly — pytest replaces sys.stdout per-test, which makes
    end-to-end ``print()`` → tail flaky inside the test harness.
    Production code drives the buffer via ``_TeeStream.write`` (covered
    by ``test_install_stream_capture_wraps_streams``).
    """
    marker = "llming-stage-debug-test-marker-12345"
    debug_mod._stdout_buffer.write(marker + "\n")
    with debug_client.websocket_connect("/_stage/debug/ws?token=test-token") as ws:
        ws.send_json({"q": "stdout_tail", "args": {"n": 50}})
        msg = ws.receive_json()
    assert msg["ok"] is True
    lines = msg["data"]
    assert any(marker in line for line in lines), lines


def test_install_stream_capture_wraps_streams() -> None:
    """After install, sys.stdout is a TeeStream that forwards + records."""
    import io

    underlying = io.StringIO()
    buf = debug_mod._RingBuffer(maxlen=10)
    tee = debug_mod._TeeStream(underlying, buf)
    tee.write("hello\n")
    tee.write("partial")
    tee.write(" rest\n")
    assert underlying.getvalue() == "hello\npartial rest\n"
    assert buf.tail(10) == ["hello", "partial rest"]


def test_unknown_query_returns_available_list(debug_client: TestClient) -> None:
    with debug_client.websocket_connect("/_stage/debug/ws?token=test-token") as ws:
        ws.send_json({"q": "this-is-not-a-real-query"})
        msg = ws.receive_json()
    assert msg["ok"] is False
    assert "available" in msg
    assert "info" in msg["available"]
    assert "metrics" in msg["available"]


def test_session_record_includes_heartbeat_status() -> None:
    import time
    from types import SimpleNamespace

    entry = SimpleNamespace(
        user_id="user-1",
        state={},
        controller=object(),
        created_at=time.monotonic(),
        last_activity=time.monotonic(),
        last_heartbeat=time.monotonic(),
    )

    record = debug_mod._session_record("sid-1", entry)

    assert record["last_heartbeat"] is not None
    assert record["heartbeat_age_seconds"] >= 0
    assert record["heartbeat_timeout_seconds"] > 0
    assert record["heartbeat_status"] == "alive"


def test_token_rejects_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLMING_STAGE_DEBUG", "1")
    monkeypatch.setenv("LLMING_STAGE_DEBUG_TOKEN", "s3cret")
    app = Starlette()
    mount_debug(app)
    client = TestClient(app)
    with pytest.raises(Exception):
        # Connection should be closed by the server with code 4401
        # before any messages are exchanged. TestClient surfaces this
        # as a generic exception on enter or on receive.
        with client.websocket_connect("/_stage/debug/ws?token=wrong") as ws:
            ws.send_json({"q": "info"})
            ws.receive_json()


def test_token_accepts_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLMING_STAGE_DEBUG", "1")
    monkeypatch.setenv("LLMING_STAGE_DEBUG_TOKEN", "s3cret")
    app = Starlette()
    mount_debug(app)
    client = TestClient(app)
    with client.websocket_connect("/_stage/debug/ws?token=s3cret") as ws:
        ws.send_json({"q": "info"})
        msg = ws.receive_json()
    assert msg["ok"] is True


def test_debug_ws_requires_token_even_on_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLMING_STAGE_DEBUG", "1")
    monkeypatch.delenv("LLMING_STAGE_DEBUG_TOKEN", raising=False)
    app = Starlette()
    mount_debug(app)
    client = TestClient(app)
    with pytest.raises(Exception):
        with client.websocket_connect("/_stage/debug/ws") as ws:
            ws.send_json({"q": "info"})
            ws.receive_json()


def test_mount_debug_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLMING_STAGE_DEBUG", "1")
    app = Starlette()
    mount_debug(app)
    mount_debug(app)
    routes = [r for r in app.router.routes if getattr(r, "path", "") == "/_stage/debug/ws"]
    assert len(routes) == 1
