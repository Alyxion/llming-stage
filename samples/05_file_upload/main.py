"""Sample 05 — file upload via cookie-authed HTTP + WebSocket progress.

HTTP ``POST /api/upload`` accepts multipart data, writes nothing to
disk (the communication model's "large-file transfer" carve-out is
strictly about the HTTP channel — the data still stays in memory).
While the upload streams in, the server pushes progress events over
the same WebSocket the user already has open.

This is the canonical "HTTP for bulk, WS for reactive" split.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from llming_com import SessionRouter

from samples._common import SampleSession, bootstrap, run

HERE = Path(__file__).resolve().parent

ws = SessionRouter(prefix="uploads")


@ws.handler("list")
async def list_uploads(session: SampleSession) -> dict:
    await session.call("home.setUploads", session.state.get("uploads", []))
    return {"ok": True}


app, registry, auth = bootstrap(
    app_name="sample05",
    title="Sample 05 — File upload",
    routes=[("/", "home")],
    view_sources={"home": "home.vue"},
    static_dir=HERE,
    ws_router=ws,
)


@app.post("/api/upload")
async def upload(request: Request, file: UploadFile) -> JSONResponse:
    """Cookie-authed multipart upload. Streams chunks, hashes in memory.

    Emits ``upload.progress`` + ``upload.done`` events on the session's
    WebSocket so the page updates reactively.
    """
    session_id = auth.get_auth_session_id(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="missing or invalid session cookie")
    entry = registry.get_session(session_id)
    if entry is None:
        raise HTTPException(status_code=401, detail="session not found")

    hasher = hashlib.sha256()
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        hasher.update(chunk)
        total += len(chunk)
        await entry.call("home.setProgress", file.filename, total)

    digest = hasher.hexdigest()
    record = {"name": file.filename, "bytes": total, "sha256": digest}
    uploads = entry.state.setdefault("uploads", [])
    uploads.append(record)
    await entry.call("home.finishUpload", record)
    return JSONResponse(record)


if __name__ == "__main__":
    run(app, sample_dir=HERE)
