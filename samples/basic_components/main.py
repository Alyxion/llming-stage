from fastapi import FastAPI
from llming_stage import Stage

app = FastAPI()
stage = Stage(app, root=__file__, title="Basic components").view("/", "home.vue")

if __name__ == "__main__":
    stage.run()
