from fastapi import FastAPI

from llming_stage import Stage

app = FastAPI()
stage = Stage(app, root=__file__, title="Sample 08 — Analytics Dashboard").view(
    "/", "home.vue", name="dashboard"
)

if __name__ == "__main__":
    stage.run()
