"""Sample 01 — a static shell served as one HTML document."""

from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from llming_stage import ShellConfig, mount_assets, mount_shell

HERE = Path(__file__).resolve().parent
_V = os.environ.get("STAGE_VIEW_VERSION", str(int(time.time() * 1000)))

app = FastAPI()
mount_assets(app)
app.mount("/app-static", StaticFiles(directory=str(HERE / "static")), name="app-static")
mount_shell(
    app,
    config=ShellConfig(
        title="Sample 01 — Static",
        routes=[("/", "home")],
        view_modules={"home": f"/app-static/home.js?v={_V}"},
        preload_views=["home"],
    ),
)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    reload = os.environ.get("STAGE_RELOAD", "1") != "0"
    if reload:
        uvicorn.run("main:app", host="127.0.0.1", port=port, reload=True,
                    reload_dirs=[str(HERE)], app_dir=str(HERE))
    else:
        uvicorn.run(app, host="127.0.0.1", port=port)
