<template>
  <main class="min-h-screen p-6 text-slate-900 bg-gradient-to-br from-sky-50 to-slate-50 dark:text-slate-100 dark:from-sky-950 dark:to-slate-950">
    <section class="mx-auto flex max-w-6xl flex-col gap-5">
      <header>
        <div class="text-overline">lazy KaTeX + DOMPurify</div>
        <h1 class="text-h5 q-my-xs">Math + sanitised HTML</h1>
        <p class="text-caption q-mb-none">
          Heavy document tools load only when the matching button is clicked.
        </p>
      </header>

      <div class="grid gap-5 md:grid-cols-2">
        <section class="rounded-3xl border border-sky-600/20 bg-white/80 p-5 shadow-2xl shadow-sky-950/10 dark:bg-sky-950/40">
          <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div class="text-subtitle2">Source</div>
            <div class="flex gap-2">
              <button id="render-math" type="button" class="rounded-xl bg-sky-600 px-4 py-2 text-xs font-extrabold text-white" @click="renderMath">Render math</button>
              <button id="render-html" type="button" class="rounded-xl bg-teal-700 px-4 py-2 text-xs font-extrabold text-white" @click="renderHtml">
                Sanitise HTML
              </button>
            </div>
          </div>
          <textarea id="src" v-model="source" class="min-h-96 w-full resize-y rounded-2xl border border-slate-500/25 bg-slate-500/5 p-4 font-mono text-sm text-inherit outline-none" spellcheck="false"></textarea>
        </section>

        <section class="rounded-3xl border border-sky-600/20 bg-white/80 p-5 shadow-2xl shadow-sky-950/10 dark:bg-sky-950/40">
          <div class="text-subtitle2 q-mb-sm">Output</div>
          <div v-if="mode === 'html'" id="out" class="min-h-96 rounded-2xl bg-slate-500/5 p-4 leading-relaxed" v-html="htmlOutput"></div>
          <div v-else id="out" ref="mathOut" class="min-h-96 rounded-2xl bg-slate-500/5 p-4 leading-relaxed whitespace-pre-wrap"></div>
        </section>
      </div>
    </section>
  </main>
</template>

<script>
export default {
  data() {
    return {
      source: [
        "The quadratic formula:",
        "",
        "$$ x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a} $$",
        "",
        "Inline math: $e^{i\\pi} + 1 = 0$.",
        "",
        '<b>Bold HTML</b> and <scr' + 'ipt>alert("xss")</scr' + 'ipt> will be sanitised.',
      ].join("\n"),
      htmlOutput: "",
      mode: "math",
    };
  },
  methods: {
    async renderMath() {
      await window.__stage.load("katex");
      this.mode = "math";
      await this.$nextTick();
      const out = this.$refs.mathOut;
      const parts = this.source.split(/(\$\$[^$]+\$\$|\$[^$]+\$)/);
      out.replaceChildren();
      for (const part of parts) {
        if (part.startsWith("$$") && part.endsWith("$$")) {
          const div = document.createElement("div");
          window.katex.render(part.slice(2, -2), div, {
            displayMode: true,
            throwOnError: false,
          });
          out.appendChild(div);
        } else if (part.startsWith("$") && part.endsWith("$") && part.length > 1) {
          const span = document.createElement("span");
          window.katex.render(part.slice(1, -1), span, { throwOnError: false });
          out.appendChild(span);
        } else {
          out.appendChild(document.createTextNode(part));
        }
      }
    },
    async renderHtml() {
      await window.__stage.load("dompurify");
      this.htmlOutput = window.DOMPurify.sanitize(this.source);
      this.mode = "html";
    },
  },
};
</script>
