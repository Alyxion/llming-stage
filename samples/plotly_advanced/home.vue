<template>
  <main class="min-h-screen p-6 text-slate-900 bg-slate-50 dark:text-slate-100 dark:bg-slate-950">
    <div class="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <div class="text-h5">Plotly · advanced bundle</div>
        <div class="text-caption text-grey">
          Chart types only available in <code>plotly/full</code> — 3D surface,
          heatmap, candlestick, Sankey. Loaded on demand.
        </div>
      </div>
      <q-chip class="bg-secondary text-white" dense square>
        <q-icon name="bolt" size="14px" class="q-mr-xs"/>plotly-full
      </q-chip>
    </div>

    <div class="grid gap-4 md:grid-cols-2">
      <div>
        <div class="q-card q-pa-md h-[380px]">
          <div class="text-subtitle2 q-mb-sm">3D surface — sin(x)·cos(y)</div>
          <div id="chart-surface" class="h-80 w-full"></div>
        </div>
      </div>
      <div>
        <div class="q-card q-pa-md h-[380px]">
          <div class="text-subtitle2 q-mb-sm">Correlation heatmap</div>
          <div id="chart-heat" class="h-80 w-full"></div>
        </div>
      </div>
    </div>

    <div class="mt-4 grid gap-4 md:grid-cols-2">
      <div>
        <div class="q-card q-pa-md h-[360px]">
          <div class="text-subtitle2 q-mb-sm">Stock — candlestick (30 days)</div>
          <div id="chart-candle" class="h-[300px] w-full"></div>
        </div>
      </div>
      <div>
        <div class="q-card q-pa-md h-[360px]">
          <div class="text-subtitle2 q-mb-sm">Sankey — energy flow</div>
          <div id="chart-sankey" class="h-[300px] w-full"></div>
        </div>
      </div>
    </div>
  </main>
</template>

<script>
export default {
  async mounted() {
    const originalGetContext = HTMLCanvasElement.prototype.getContext;
    const patchedGetContext = function(type, options) {
      if (type === '2d') {
        return originalGetContext.call(this, type, {
          ...(options || {}),
          willReadFrequently: true,
        });
      }
      return originalGetContext.call(this, type, options);
    };
    HTMLCanvasElement.prototype.getContext = patchedGetContext;
    this.restoreCanvasReadbackHint = () => {
      if (HTMLCanvasElement.prototype.getContext === patchedGetContext) {
        HTMLCanvasElement.prototype.getContext = originalGetContext;
      }
    };

    await window.__stage.load('plotly/full');
    await this.$nextTick();

    const dark = () => document.body.classList.contains('body--dark');
    const theme = () => {
      const d = dark();
      return {
        paper: 'rgba(0,0,0,0)',
        plot: 'rgba(0,0,0,0)',
        text: d ? '#e2e8f0' : '#1e293b',
        muted: d ? '#94a3b8' : '#64748b',
        grid: d ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
      };
    };
    const common = () => ({
      paper_bgcolor: theme().paper,
      plot_bgcolor: theme().plot,
      font: { color: theme().text, family: '-apple-system, system-ui, sans-serif', size: 12 },
      margin: { l: 50, r: 20, t: 10, b: 35 },
    });

    const ids = ['chart-surface', 'chart-heat', 'chart-candle', 'chart-sankey'];
    const plotJobs = [];

    const N = 60;
    const xs = Array.from({ length: N }, (_, i) => -3 + (i / (N - 1)) * 6);
    const ys = xs.slice();
    const z = ys.map((y) => xs.map((x) => Math.sin(x) * Math.cos(y) +
                                            0.5 * Math.sin(x * y * 0.4)));
    plotJobs.push(Plotly.newPlot('chart-surface', [{
      type: 'surface', x: xs, y: ys, z, showscale: false,
      colorscale: 'Viridis',
      contours: { z: { show: true, usecolormap: true, project: { z: true } } },
    }], {
      ...common(),
      margin: { l: 0, r: 0, t: 0, b: 0 },
      scene: {
        xaxis: { title: '', gridcolor: theme().grid, color: theme().muted },
        yaxis: { title: '', gridcolor: theme().grid, color: theme().muted },
        zaxis: { title: '', gridcolor: theme().grid, color: theme().muted },
        camera: { eye: { x: 1.6, y: 1.6, z: 0.9 } },
        bgcolor: theme().paper,
      },
    }, { displayModeBar: false, responsive: true }));

    const labels = ['α', 'β', 'γ', 'δ', 'ε', 'ζ', 'η', 'θ', 'ι', 'κ'];
    const heat = Array.from({ length: labels.length }, (_, i) =>
      Array.from({ length: labels.length }, (_, j) =>
        i === j ? 1 : (Math.cos((i * 7 + j * 3) * 0.7) * 0.6 + Math.random() * 0.2)));
    plotJobs.push(Plotly.newPlot('chart-heat', [{
      type: 'heatmap', x: labels, y: labels, z: heat,
      colorscale: 'RdBu', reversescale: true, zmid: 0,
      showscale: true,
      colorbar: { thickness: 10, len: 0.85 },
    }], {
      ...common(),
      xaxis: { side: 'top', tickfont: { color: theme().muted } },
      yaxis: { autorange: 'reversed', tickfont: { color: theme().muted } },
    }, { displayModeBar: false, responsive: true }));

    const dates = [], open = [], close = [], low = [], high = [];
    let p = 100;
    for (let i = 0; i < 30; i++) {
      const o = p;
      const c = o + (Math.random() * 8 - 4);
      const lo = Math.min(o, c) - Math.random() * 2.5;
      const hi = Math.max(o, c) + Math.random() * 2.5;
      const d = new Date(); d.setDate(d.getDate() - (30 - i));
      dates.push(d.toISOString().slice(0, 10));
      open.push(o); close.push(c); low.push(lo); high.push(hi);
      p = c;
    }
    plotJobs.push(Plotly.newPlot('chart-candle', [{
      type: 'candlestick',
      x: dates, open, close, low, high,
      increasing: { line: { color: '#10b981' } },
      decreasing: { line: { color: '#ef4444' } },
    }], {
      ...common(),
      xaxis: { rangeslider: { visible: false }, gridcolor: theme().grid,
               tickfont: { color: theme().muted } },
      yaxis: { gridcolor: theme().grid, tickfont: { color: theme().muted } },
    }, { displayModeBar: false, responsive: true }));

    plotJobs.push(Plotly.newPlot('chart-sankey', [{
      type: 'sankey', orientation: 'h',
      node: {
        label: ['Coal', 'Gas', 'Solar', 'Wind', 'Nuclear', 'Grid', 'Industry', 'Households', 'Transport'],
        pad: 14, thickness: 14,
        color: ['#475569', '#64748b', '#fbbf24', '#06b6d4', '#a855f7',
                '#3b82f6', '#10b981', '#f97316', '#ef4444'],
        line: { color: theme().grid, width: 0.5 },
      },
      link: {
        source: [0, 1, 2, 3, 4, 5, 5, 5],
        target: [5, 5, 5, 5, 5, 6, 7, 8],
        value:  [22, 18, 9, 11, 14, 30, 26, 18],
        color: 'rgba(99,102,241,0.25)',
      },
    }], {
      ...common(),
      margin: { l: 10, r: 10, t: 10, b: 10 },
    }, { displayModeBar: false, responsive: true }));

    await Promise.all(plotJobs);

    this.ro = new ResizeObserver(() => ids.forEach((id) => {
      try { Plotly.Plots.resize(id); } catch (_) {}
    }));
    this.ro.observe(this.$el);

    this.themeObs = new MutationObserver(() => ids.forEach((id) => {
      try { Plotly.relayout(id, common()); } catch (_) {}
    }));
    this.themeObs.observe(document.body, { attributes: true, attributeFilter: ['class'] });
  },

  beforeUnmount() {
    this.ro?.disconnect();
    this.themeObs?.disconnect();
    this.restoreCanvasReadbackHint?.();
    ['chart-surface', 'chart-heat', 'chart-candle', 'chart-sankey'].forEach((id) => {
      try { Plotly.purge(id); } catch (_) {}
    });
  },
};
</script>
