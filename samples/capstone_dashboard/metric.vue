<template>
  <main class="min-h-screen bg-gradient-to-br from-slate-50 to-indigo-50 text-slate-900 dark:from-slate-950 dark:to-indigo-950 dark:text-slate-100">
    <nav class="flex flex-wrap items-center gap-5 border-b border-slate-500/20 px-7 py-4">
      <div class="mr-4 flex items-center gap-3"><div class="text-3xl font-black text-indigo-500">◎</div><div><div class="cap-brand-name font-extrabold">Capstone</div><div class="text-xs opacity-60">sample 10</div></div></div>
      <a data-stage-link href="/" class="cap-nav-item font-bold text-inherit no-underline opacity-70">Home</a><a data-stage-link href="/metric" class="cap-nav-item font-bold text-indigo-500 no-underline">Metrics</a><a data-stage-link href="/uploads" class="cap-nav-item font-bold text-inherit no-underline opacity-70">Uploads</a><a data-stage-link href="/chat" class="cap-nav-item font-bold text-inherit no-underline opacity-70">Chat</a>
    </nav>
    <section class="mx-auto max-w-6xl p-6">
      <div class="row items-center justify-between q-mb-md">
        <div>
          <h1 class="text-h5 q-my-xs">Live metrics</h1>
          <p class="text-caption q-mb-none">Streaming at 2 Hz over the session WebSocket.</p>
        </div>
        <div class="flex gap-2">
          <button type="button" class="rounded-xl bg-indigo-500 px-5 py-3 font-extrabold text-white" @click="start">Start</button>
          <button type="button" class="rounded-xl bg-slate-600 px-5 py-3 font-extrabold text-white" @click="stop">Stop</button>
        </div>
      </div>
      <div class="grid gap-5 md:grid-cols-[2fr_1fr]">
        <div class="rounded-3xl border border-indigo-500/20 bg-white/80 p-5 dark:bg-indigo-950/30">
          <div class="text-subtitle2 q-mb-sm">Requests per second</div>
          <div id="chart" ref="chart" class="h-72 w-full"></div>
        </div>
        <div class="rounded-3xl border border-indigo-500/20 bg-white/80 p-5 dark:bg-indigo-950/30">
          <div class="text-subtitle2">Latest sample</div>
          <div id="latest" class="mt-5 text-6xl font-black tabular-nums text-indigo-500">{{ latest }}</div>
          <p class="text-caption">The server task starts from a SessionRouter handler.</p>
        </div>
      </div>
    </section>
  </main>
</template>

<script>
export default {
  data() {
    return { xs: [], ys: [], latest: "—", themeObs: null };
  },
  async mounted() {
    await this.$stage.connect();
    await window.__stage.load("plotly");
    this.draw();
    this.themeObs = new MutationObserver(() => this.relayout());
    this.themeObs.observe(document.body, { attributes: true, attributeFilter: ["class"] });
  },
  beforeUnmount() {
    this.themeObs?.disconnect();
    try { window.Plotly.purge(this.$refs.chart); } catch (_) {}
  },
  methods: {
    theme() {
      const dark = document.body.classList.contains("body--dark");
      return {
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: dark ? "#e2e8f0" : "#1e293b" },
        margin: { l: 45, r: 15, t: 10, b: 35 },
        yaxis: { range: [-2, 2], gridcolor: dark ? "rgba(255,255,255,.08)" : "rgba(0,0,0,.08)" },
        xaxis: { gridcolor: dark ? "rgba(255,255,255,.08)" : "rgba(0,0,0,.08)" },
      };
    },
    draw() {
      window.Plotly.newPlot(
        this.$refs.chart,
        [{ x: this.xs, y: this.ys, mode: "lines", fill: "tozeroy", line: { color: "#6366f1", width: 2 } }],
        this.theme(),
        { displayModeBar: false, responsive: true },
      );
    },
    relayout() {
      window.Plotly.relayout(this.$refs.chart, this.theme());
    },
    addMetricSample(t, value) {
      this.xs.push(t);
      this.ys.push(value);
      if (this.xs.length > 200) {
        this.xs.shift();
        this.ys.shift();
      }
      window.Plotly.update(this.$refs.chart, { x: [this.xs], y: [this.ys] });
      this.latest = value.toFixed(2);
    },
    start() {
      this.$stage.send("metric.start");
    },
    stop() {
      this.$stage.send("metric.stop");
    },
  },
};
</script>
