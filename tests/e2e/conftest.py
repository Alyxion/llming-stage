"""Fixtures for Playwright end-to-end tests against the samples.

Each test is parameterised over one sample directory. The fixture
spawns ``python samples/<name>/main.py`` as a subprocess, waits for
port 8080 to accept connections, and tears the process down after
the test.

Tests run sequentially on a single port so the samples can use their
stock ``uvicorn.run(..., port=8080)`` configuration unchanged.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLES = REPO_ROOT / "samples"


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _wait_port_open(port: int, deadline: float) -> None:
    while time.time() < deadline:
        if _port_open("127.0.0.1", port):
            return
        time.sleep(0.2)
    raise RuntimeError(f"server never accepted connections on :{port}")


def _pick_free_port() -> int:
    """Ask the OS for a free ephemeral port, then release it."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


@pytest.fixture
def sample_server(request: pytest.FixtureRequest) -> Iterator[str]:
    """Start a sample server on a free port and yield its base URL.

    The sample name comes from a ``@pytest.mark.sample("01_static")``
    marker on the test, or — when parametrised indirectly — from
    ``request.param``.
    """
    mark = request.node.get_closest_marker("sample")
    if mark is None:
        sample = request.param  # type: ignore[attr-defined]
    else:
        sample = mark.args[0]

    main_py = SAMPLES / sample / "main.py"
    assert main_py.is_file(), f"{main_py} does not exist"

    port = _pick_free_port()
    env = {**os.environ, "PORT": str(port), "STAGE_RELOAD": "0"}
    proc = subprocess.Popen(
        [sys.executable, str(main_py)],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    try:
        try:
            _wait_port_open(port, time.time() + 30)
        except RuntimeError:
            proc.terminate()
            out = proc.stdout.read().decode(errors="replace") if proc.stdout else ""
            raise RuntimeError(
                f"server for {sample} did not start on :{port}. output:\n{out}"
            )
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Reduce Playwright noise. Each test spawns its own server."""
    return {**browser_context_args, "viewport": {"width": 1024, "height": 768}}


def open_sample(page, base: str) -> dict:
    """Navigate the page and return the session payload fetched by the view.

    Used by WebSocket-enabled samples. Returns ``{sessionId, wsUrl}``.
    """
    page.goto(base)
    return page.evaluate(
        "async () => {\n"
        "  const r = await fetch('/api/session', {credentials: 'include'});\n"
        "  return r.json();\n"
        "}"
    )


def wait_controller_ready(page, base: str, session_id: str, timeout: float = 10.0) -> None:
    """Poll ``debug.state`` until the session's controller is attached.

    The controller is only bound once the browser has opened the
    WebSocket and ``on_connect`` has run — at that point debug
    dispatch via HTTP works.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = page.evaluate(
            "async (sid) => {\n"
            "  const r = await fetch('/cmd/sessions/' + sid + '/debug.state',\n"
            "      {credentials: 'include'});\n"
            "  return r.json();\n"
            "}",
            session_id,
        )
        if state.get("controller_ready"):
            return
        time.sleep(0.1)
    raise RuntimeError(f"controller never became ready for {session_id}")


def debug_dispatch(page, session_id: str, msg: dict) -> dict:
    """Invoke a WS message through the session's router via HTTP."""
    return page.evaluate(
        "async ([sid, msg]) => {\n"
        "  const r = await fetch('/cmd/sessions/' + sid + '/debug.ws_dispatch',\n"
        "      {method: 'POST', credentials: 'include',\n"
        "       headers: {'content-type': 'application/json'},\n"
        "       body: JSON.stringify({msg})});\n"
        "  return r.json();\n"
        "}",
        [session_id, msg],
    )


def debug_state(page, session_id: str) -> dict:
    return page.evaluate(
        "async (sid) => (await fetch('/cmd/sessions/' + sid + '/debug.state',\n"
        "    {credentials: 'include'})).json()",
        session_id,
    )
