"""Sample 01 — static.

The minimum llming-stage server. No llming-com, no session, no
WebSocket. Every byte that leaves the server is a static file —
this directory could be rebuilt into a static export and hosted on
GitHub Pages.
"""

import os
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from llming_stage import ShellConfig, mount_assets, mount_shell

HERE = Path(__file__).resolve().parent
# Cache-bust per process so successive launches on the same port don't
# re-use the previous sample's view JS (see samples/_common.py).
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
    import os
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8080")))
