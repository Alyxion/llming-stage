"""File upload via cookie-authed HTTP + WebSocket progress.

HTTP ``POST /api/upload`` accepts multipart data, writes nothing to
disk (the communication model's "large-file transfer" carve-out is
strictly about the HTTP channel — the data still stays in memory).
While the upload streams in, the server pushes progress events over
the same WebSocket the user already has open.

This is the canonical "HTTP for bulk, WS for reactive" split.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from fastapi import Depends, FastAPI, UploadFile
from fastapi.responses import JSONResponse
from llming_com import BaseSessionEntry
from llming_stage import Stage


@dataclass
class Session(BaseSessionEntry):
    state: dict[str, Any] = field(default_factory=dict)


app = FastAPI()
stage = Stage(app, title="File upload")
sessions = stage.session(app_name="file_upload", session_cls=Session)
uploads = sessions.add_router("uploads")


@uploads.handler("list")
async def list_uploads(session: Session) -> dict:
    await session.call("home.setUploads", session.state.get("uploads", []))
    return {"ok": True}


@app.post("/api/upload")
async def upload(
    file: UploadFile,
    session: Session = Depends(sessions.require_session),
) -> JSONResponse:
    """Cookie-authed multipart upload. Streams chunks, hashes in memory.

    Emits ``upload.progress`` + ``upload.done`` events on the session's
    WebSocket so the page updates reactively.
    """
    hasher = hashlib.sha256()
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        hasher.update(chunk)
        total += len(chunk)
        await session.call("home.setProgress", file.filename, total)

    digest = hasher.hexdigest()
    record = {"name": file.filename, "bytes": total, "sha256": digest}
    uploaded = session.state.setdefault("uploads", [])
    uploaded.append(record)
    await session.call("home.finishUpload", record)
    return JSONResponse(record)


stage.add_view("/", "home.vue")

if __name__ == "__main__":
    stage.run()
