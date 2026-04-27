from __future__ import annotations

import asyncio
import threading
from typing import Any

from llming_com import SessionRouter

from samples._common import SampleController, SampleSession


class RecordingController(SampleController):
    def __init__(self) -> None:
        super().__init__("sid")
        self.sent: list[dict[str, Any]] = []

    async def send(self, msg: dict[str, Any]) -> bool:
        self.sent.append(msg)
        return True


def _run_async(coro: Any) -> None:
    error: list[BaseException] = []

    def runner() -> None:
        try:
            asyncio.run(coro)
        except BaseException as exc:
            error.append(exc)

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if error:
        raise error[0]


def test_sample_ws_handlers_can_receive_session() -> None:
    async def scenario() -> None:
        await controller.handle_message(
            {"type": "counter.inc", "by": 2, "_req_id": "r1"}
        )

    ws = SessionRouter(prefix="counter")

    @ws.handler("inc")
    async def inc(session: SampleSession, by: int = 1) -> dict[str, Any]:
        session.state["count"] = int(session.state.get("count", 0)) + by
        await session.send({"type": "counter.update", "value": session.state["count"]})
        return {"ok": True}

    session = SampleSession(user_id="user")
    controller = RecordingController()
    controller.attach_session(session)
    controller.mount_router(ws)

    _run_async(scenario())

    assert session.state["count"] == 2
    assert controller.sent == [
        {"type": "counter.update", "value": 2},
        {"type": "counter.inc", "ok": True, "_req_id": "r1"},
    ]


def test_sample_ws_handlers_can_receive_session_in_multiple_handlers() -> None:
    async def scenario() -> None:
        await controller.handle_message({"type": "counter.set"})

    ws = SessionRouter(prefix="counter")

    @ws.handler("set")
    async def set_flag(session: SampleSession) -> dict[str, Any]:
        session.state["flag"] = True
        return {"ok": True}

    session = SampleSession(user_id="user")
    controller = RecordingController()
    controller.attach_session(session)
    controller.mount_router(ws)

    _run_async(scenario())

    assert session.state["flag"] is True
    assert controller.sent == [{"type": "counter.set", "ok": True}]
