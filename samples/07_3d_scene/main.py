"""Sample 07 — lazy-loaded Three.js scene.

Demonstrates the loader: ``three.module.min.js`` is *not* in the
critical path. It loads only when the view calls ``__stage.load('three')``.
No WebSocket is opened — the sample is purely client-side.
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
            title="Sample 07 — Three.js",
            routes=[("/", "scene")],
            view_modules={"scene": f"/app-static/scene.js?v={_V}"},
            preload_views=["scene"],
        ),
    )
    return app


app = build_app()


if __name__ == "__main__":
    import os
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8080")), log_level="info")
