"""Sample 09 — lazy KaTeX + DOMPurify.

No server reactivity needed — purely static. Demonstrates the
on-demand vendor load pattern: KaTeX (math rendering) and
DOMPurify (HTML sanitisation) are not in the critical path. Each
loads on its first use via ``window.__stage.load()``.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from llming_stage import ShellConfig, mount_assets, mount_shell

HERE = Path(__file__).resolve().parent
_V = os.environ.get("STAGE_VIEW_VERSION", str(int(time.time() * 1000)))


def build_app() -> FastAPI:
    app = FastAPI()
    mount_assets(app)
    app.mount("/app-static", StaticFiles(directory=str(HERE / "static")), name="app-static")
    mount_shell(
        app,
        config=ShellConfig(
            title="Sample 09 — KaTeX + DOMPurify",
            routes=[("/", "reader")],
            view_modules={"reader": f"/app-static/reader.js?v={_V}"},
            preload_views=["reader"],
        ),
    )
    return app


app = build_app()


if __name__ == "__main__":
    import os
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8080")), log_level="info")
