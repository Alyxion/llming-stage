from fastapi import FastAPI

from llming_stage import Stage

app = FastAPI()
stage = Stage(app, root=__file__, title="Sample 07 — Three.js").view(
    "/", "home.vue", name="scene"
)

if __name__ == "__main__":
    stage.run()
