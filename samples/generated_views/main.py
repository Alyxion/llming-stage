from fastapi import FastAPI

from llming_stage import Stage, VueResponse

app = FastAPI()
stage = Stage(app, title="Generated views")


@stage.view("/")
def home() -> VueResponse:
    return VueResponse(
        template="""
<main class="min-h-screen bg-slate-50 text-slate-900 flex items-center justify-center p-10 dark:bg-slate-950 dark:text-slate-100">
  <section class="max-w-2xl space-y-6">
    <p class="uppercase tracking-[0.3em] text-cyan-300 text-sm">decorator view</p>
    <h1 class="text-5xl font-black tracking-tight">Generated views</h1>
    <p class="text-xl text-slate-600 dark:text-slate-300">
      This page is returned by a Python function instead of a Vue file.
    </p>
    <a class="inline-flex rounded-full bg-cyan-300 px-5 py-3 font-bold text-slate-950"
       href="/status">Open status route</a>
  </section>
</main>
""".strip()
    )


@stage.view("/status")
def status() -> VueResponse:
    return VueResponse(
        template="""
<main class="min-h-screen bg-cyan-50 text-slate-950 flex items-center justify-center p-10 dark:bg-slate-950 dark:text-slate-100">
  <section class="max-w-xl rounded-3xl bg-[#ffffff] p-8 shadow-2xl space-y-4 dark:bg-slate-900">
    <p class="uppercase tracking-[0.3em] text-cyan-700 text-sm dark:text-cyan-300">second route</p>
    <h1 class="text-4xl font-black tracking-tight">Status: {{ status }}</h1>
    <p class="text-lg text-slate-600 dark:text-slate-300">
      The template is inline; the Vue script is loaded from a relative file.
    </p>
    <a class="font-bold text-cyan-700" href="/">Back home</a>
  </section>
</main>
""".strip(),
        script_path="status.js",
    )


if __name__ == "__main__":
    stage.run()
