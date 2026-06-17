from fastapi import FastAPI

from llming_stage import Stage

app = FastAPI()
stage = Stage(app, title="Media bundle gallery")

# Zip ./media_src on demand (re-built automatically when it changes) and serve
# it at /bundles/media.zip. The browser downloads it once and reads every
# image / video / audio entry locally.
stage.serve_bundle("media", "media_src")
stage.add_view("/", "home.js")

if __name__ == "__main__":
    stage.run()
