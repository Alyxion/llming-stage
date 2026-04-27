<template>
  <main class="min-h-screen bg-gradient-to-br from-emerald-50 via-teal-50 to-amber-50 p-6 text-slate-900 dark:from-slate-950 dark:via-teal-950 dark:to-amber-950 dark:text-slate-100">
    <section class="mb-6 flex flex-wrap items-start justify-between gap-6 rounded-[28px] border border-teal-700/20 bg-white/80 p-6 shadow-2xl shadow-teal-950/10 backdrop-blur-xl dark:border-teal-200/20 dark:bg-teal-950/40">
      <div>
        <div class="text-overline">optional extension stack</div>
        <h1 id="workbench-title" class="text-h4 text-md-h3 q-my-sm">
          Extension workbench
        </h1>
        <p class="text-subtitle1 q-mb-none">
          Markdown, diagrams, code editing, node graphs, and a terminal are
          all lazy-loaded from the local stage bundle.
        </p>
      </div>
      <q-chip square color="teal-7" text-color="white">
        zero external requests
      </q-chip>
    </section>

    <section class="grid gap-5 xl:grid-cols-12">
      <q-card flat bordered class="overflow-hidden rounded-3xl bg-white/80 backdrop-blur-xl dark:bg-teal-950/40 xl:col-span-6">
        <q-card-section>
          <div class="row items-center justify-between q-mb-md">
            <div>
              <div class="text-overline">marked + dompurify</div>
              <h2 class="text-h6 q-my-none">Sanitized product brief</h2>
            </div>
            <q-badge color="green-7">safe HTML</q-badge>
          </div>
          <div id="markdown-out" class="leading-relaxed" v-html="markdownHtml"></div>
        </q-card-section>
      </q-card>

      <q-card flat bordered class="overflow-hidden rounded-3xl bg-white/80 backdrop-blur-xl dark:bg-teal-950/40 xl:col-span-6">
        <q-card-section>
          <div class="text-overline">mermaid</div>
          <h2 class="text-h6 q-my-none q-mb-md">Release pipeline</h2>
          <div id="mermaid-out" class="grid min-h-56 place-items-center" v-html="mermaidSvg"></div>
        </q-card-section>
      </q-card>

      <q-card flat bordered class="overflow-hidden rounded-3xl bg-white/80 backdrop-blur-xl dark:bg-teal-950/40 xl:col-span-4">
        <q-card-section>
          <div class="text-overline">codemirror</div>
          <h2 class="text-h6 q-my-none q-mb-md">Editable command handler</h2>
          <textarea id="code-source" ref="code">{{ code }}</textarea>
        </q-card-section>
      </q-card>

      <q-card flat bordered class="overflow-hidden rounded-3xl bg-white/80 backdrop-blur-xl dark:bg-teal-950/40 xl:col-span-4">
        <q-card-section>
          <div class="text-overline">drawflow</div>
          <h2 class="text-h6 q-my-none q-mb-md">Frontend delivery graph</h2>
          <div id="flow-editor" ref="flow" class="h-[270px] overflow-hidden rounded-2xl bg-teal-900/5"></div>
        </q-card-section>
      </q-card>

      <q-card flat bordered class="overflow-hidden rounded-3xl bg-white/80 backdrop-blur-xl dark:bg-teal-950/40 xl:col-span-4">
        <q-card-section>
          <div class="row items-center justify-between q-mb-md">
            <div>
              <div class="text-overline">xterm + addons</div>
              <h2 class="text-h6 q-my-none">Local terminal preview</h2>
            </div>
            <q-badge color="blue-grey-7">{{ webglStatus }}</q-badge>
          </div>
          <div id="terminal" ref="terminal" class="h-[270px] overflow-hidden rounded-2xl bg-[#071516] p-2"></div>
        </q-card-section>
      </q-card>
    </section>
  </main>
</template>

<script>
export default {
  data() {
    return {
      webglStatus: "loading renderer",
      code: `router = SessionRouter()

@router.handler("brief.render")
async def render_brief(session, markdown):
    html = render_markdown(markdown)
    await session.call("brief.setHtml", html)`,
      editor: null,
      flow: null,
      markdownHtml: "",
      mermaidSvg: "",
      terminal: null,
      resizeObserver: null,
    };
  },
  async mounted() {
    await Promise.all([
      this.renderMarkdown(),
      this.renderMermaid(),
      this.mountCodeMirror(),
      this.mountDrawflow(),
      this.mountTerminal(),
    ]);
  },
  beforeUnmount() {
    this.resizeObserver?.disconnect();
    this.terminal?.dispose?.();
    this.editor?.toTextArea?.();
    this.$refs.flow?.replaceChildren();
  },
  methods: {
    async renderMarkdown() {
      await Promise.all([
        window.__stage.load("marked"),
        window.__stage.load("dompurify"),
      ]);
      const source = `## Professional sample brief

- Tiny FastAPI entrypoint.
- Rich Vue view with local-only assets.
- Sanitized inline HTML: <strong>trusted output</strong>.
- Unsafe attributes are stripped: <span onclick="alert('nope')">click text</span>.`;
      const parser = window.marked?.parse ? window.marked : window.marked?.marked;
      const html = parser.parse(source);
      this.markdownHtml = window.DOMPurify.sanitize(html);
    },

    async renderMermaid() {
      await window.__stage.load("mermaid");
      window.mermaid.initialize({
        startOnLoad: false,
        theme: document.body.classList.contains("body--dark") ? "dark" : "default",
      });
      const graph = `flowchart LR
        A[FastAPI app] --> B[Stage shell]
        B --> C{Lazy extension}
        C --> D[Markdown]
        C --> E[Diagram]
        C --> F[Editor]
        C --> G[Terminal]
        G --> H[AI-debuggable UI]`;
      const result = await window.mermaid.render(
        "stage-workbench-" + Date.now(),
        graph,
      );
      this.mermaidSvg = result.svg;
    },

    async mountCodeMirror() {
      await window.__stage.load("codemirror");
      this.editor = window.CodeMirror.fromTextArea(this.$refs.code, {
        mode: "javascript",
        lineNumbers: true,
        matchBrackets: true,
        autoCloseBrackets: true,
        theme: "default",
      });
      this.editor.setSize(null, 270);
    },

    async mountDrawflow() {
      await window.__stage.load("drawflow");
      this.flow = new window.Drawflow(this.$refs.flow);
      this.flow.start();
      const source = this.flow.addNode(
        "source",
        0,
        1,
        40,
        80,
        "stage-node",
        {},
        "<div><strong>source</strong><br>home.vue</div>",
      );
      const load = this.flow.addNode(
        "load",
        1,
        1,
        270,
        70,
        "stage-node",
        {},
        "<div><strong>lazy load</strong><br>__stage.load()</div>",
      );
      const ship = this.flow.addNode(
        "ship",
        1,
        0,
        500,
        90,
        "stage-node",
        {},
        "<div><strong>publish</strong><br>static or FastAPI</div>",
      );
      this.flow.addConnection(source, load, "output_1", "input_1");
      this.flow.addConnection(load, ship, "output_1", "input_1");
      this.flow.zoom_out();
    },

    async mountTerminal() {
      await Promise.all([
        window.__stage.load("xterm"),
        window.__stage.load("xterm/fit"),
        window.__stage.load("xterm/web-links"),
        window.__stage.load("xterm/webgl"),
      ]);
      const TerminalCtor = window.Terminal?.Terminal || window.Terminal;
      this.terminal = new TerminalCtor({
        cursorBlink: true,
        convertEol: true,
        fontFamily: '"SF Mono", Menlo, Consolas, monospace',
        fontSize: 13,
        theme: {
          background: "#071516",
          foreground: "#d9ffef",
          cursor: "#7fffd4",
        },
      });
      const fit = new window.FitAddon.FitAddon();
      this.terminal.loadAddon(fit);
      this.terminal.loadAddon(new window.WebLinksAddon.WebLinksAddon());
      this.terminal.open(this.$refs.terminal);
      try {
        this.terminal.loadAddon(new window.WebglAddon.WebglAddon());
        this.webglStatus = "webgl active";
      } catch (err) {
        this.webglStatus = "canvas fallback";
      }
      fit.fit();
      this.terminal.writeln("$ llming-stage serve .");
      this.terminal.writeln("watching .vue .js .css .py .html images");
      this.terminal.writeln("reloads only when file bytes change");
      this.resizeObserver = new ResizeObserver(() => fit.fit());
      this.resizeObserver.observe(this.$refs.terminal);
    },
  },
};
</script>
