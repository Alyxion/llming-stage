from fastapi import FastAPI

from llming_stage import Stage

app = FastAPI()
stage = Stage(app, title="Static shell")

stage.add_view("/", "home.vue")

if __name__ == "__main__":
    stage.run()
