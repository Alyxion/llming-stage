from fastapi import FastAPI

from llming_stage import Stage

app = FastAPI()
stage = Stage(app, root=__file__, title="Sample 01 — Static").view("/", "home.vue")

if __name__ == "__main__":
    stage.run()
