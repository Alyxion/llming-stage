from fastapi import FastAPI

from llming_stage import Stage

app = FastAPI()
stage = Stage(app, root=__file__, title="Sample 09 — Math + sanitised HTML").view(
    "/", "home.vue", name="reader"
)

if __name__ == "__main__":
    stage.run()
