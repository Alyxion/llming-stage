from fastapi import FastAPI

from llming_stage import Stage

app = FastAPI()
stage = Stage(app, title="Offline data bundle (zip)")

# Serve everything under ./data as ETag-revalidated bundles at /bundles/*.
# The browser downloads demo.zip once, caches it by content hash, and reads
# its entries locally — re-prepare the zip and the client picks it up.
stage.mount_bundles("data")

# Self-building bundle: ./live_src is zipped on demand and re-zipped
# automatically whenever its files change. Served at /bundles/live.zip.
stage.serve_bundle("live", "live_src")

stage.add_view("/", "home.js")

if __name__ == "__main__":
    stage.run()
