window.__stageViews = window.__stageViews || {};
window.__stageViews.advanced = {
  async mount(target) {
    await window.__stage.load('plotly/full');

    const dark = () => document.body.classList.contains('body--dark');
    const theme = () => {
      const d = dark();
      return {
        paper: 'rgba(0,0,0,0)', plot: 'rgba(0,0,0,0)',
        text: d ? '#e2e8f0' : '#1e293b',
        muted: d ? '#94a3b8' : '#64748b',
        grid: d ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
      };
    };

    target.innerHTML = `
      <div class="q-pa-md" style="min-height:100%">
        <div class="row items-end justify-between q-mb-md">
          <div>
            <div class="text-h5">Plotly · advanced bundle</div>
            <div class="text-caption text-grey">
              Chart types only available in <code>plotly/full</code> — 3D surface,
              heatmap, candlestick, choropleth. Loaded on demand.
            </div>
          </div>
          <q-chip class="bg-secondary text-white" dense square>
            <q-icon name="bolt" size="14px" class="q-mr-xs"/>plotly-full
          </q-chip>
        </div>

        <div class="row q-col-gutter-md">
          <div class="col-12 col-md-6">
            <div class="q-card q-pa-md" style="height:380px">
              <div class="text-subtitle2 q-mb-sm">3D surface — sin(x)·cos(y)</div>
              <div id="chart-surface" style="width:100%;height:320px"></div>
            </div>
          </div>
          <div class="col-12 col-md-6">
            <div class="q-card q-pa-md" style="height:380px">
              <div class="text-subtitle2 q-mb-sm">Correlation heatmap</div>
              <div id="chart-heat" style="width:100%;height:320px"></div>
            </div>
          </div>
        </div>

        <div class="row q-col-gutter-md q-mt-sm">
          <div class="col-12 col-md-6">
            <div class="q-card q-pa-md" style="height:360px">
              <div class="text-subtitle2 q-mb-sm">Stock — candlestick (30 days)</div>
              <div id="chart-candle" style="width:100%;height:300px"></div>
            </div>
          </div>
          <div class="col-12 col-md-6">
            <div class="q-card q-pa-md" style="height:360px">
              <div class="text-subtitle2 q-mb-sm">Sankey — energy flow</div>
              <div id="chart-sankey" style="width:100%;height:300px"></div>
            </div>
          </div>
        </div>
      </div>`;

    await new Promise((r) => requestAnimationFrame(r));

    const COMMON = () => ({
      paper_bgcolor: theme().paper,
      plot_bgcolor: theme().plot,
      font: { color: theme().text, family: '-apple-system, system-ui, sans-serif', size: 12 },
      margin: { l: 50, r: 20, t: 10, b: 35 },
    });

    // ---- 3D surface: z = sin(x)·cos(y) on a 50×50 grid -------------
    {
      const N = 60;
      const xs = Array.from({ length: N }, (_, i) => -3 + (i / (N - 1)) * 6);
      const ys = xs.slice();
      const z = ys.map((y) => xs.map((x) => Math.sin(x) * Math.cos(y) +
                                              0.5 * Math.sin(x * y * 0.4)));
      Plotly.newPlot('chart-surface', [{
        type: 'surface', x: xs, y: ys, z, showscale: false,
        colorscale: 'Viridis',
        contours: {
          z: { show: true, usecolormap: true, project: { z: true } },
        },
      }], {
        ...COMMON(),
        margin: { l: 0, r: 0, t: 0, b: 0 },
        scene: {
          xaxis: { title: '', gridcolor: theme().grid, color: theme().muted },
          yaxis: { title: '', gridcolor: theme().grid, color: theme().muted },
          zaxis: { title: '', gridcolor: theme().grid, color: theme().muted },
          camera: { eye: { x: 1.6, y: 1.6, z: 0.9 } },
          bgcolor: theme().paper,
        },
      }, { displayModeBar: false, responsive: true });
    }

    // ---- Heatmap: synthetic correlation matrix ----------------------
    {
      const labels = ['α', 'β', 'γ', 'δ', 'ε', 'ζ', 'η', 'θ', 'ι', 'κ'];
      const N = labels.length;
      const z = Array.from({ length: N }, (_, i) =>
        Array.from({ length: N }, (_, j) =>
          i === j ? 1 : (Math.cos((i * 7 + j * 3) * 0.7) * 0.6 + Math.random() * 0.2)));
      Plotly.newPlot('chart-heat', [{
        type: 'heatmap', x: labels, y: labels, z,
        colorscale: 'RdBu', reversescale: true, zmid: 0,
        showscale: true,
        colorbar: { thickness: 10, len: 0.85 },
      }], {
        ...COMMON(),
        xaxis: { side: 'top', tickfont: { color: theme().muted } },
        yaxis: { autorange: 'reversed', tickfont: { color: theme().muted } },
      }, { displayModeBar: false, responsive: true });
    }

    // ---- Candlestick: 30 days of synthetic OHLC ---------------------
    {
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
      Plotly.newPlot('chart-candle', [{
        type: 'candlestick',
        x: dates, open, close, low, high,
        increasing: { line: { color: '#10b981' } },
        decreasing: { line: { color: '#ef4444' } },
      }], {
        ...COMMON(),
        xaxis: { rangeslider: { visible: false }, gridcolor: theme().grid,
                 tickfont: { color: theme().muted } },
        yaxis: { gridcolor: theme().grid, tickfont: { color: theme().muted } },
      }, { displayModeBar: false, responsive: true });
    }

    // ---- Sankey: synthetic energy-flow diagram ---------------------
    {
      // Sankey is a plotly-full-only type and renders entirely client-
      // side — no external data fetches (unlike choropleth, which by
      // default pulls topology JSON from cdn.plot.ly).
      const labels = [
        'Coal', 'Gas', 'Solar', 'Wind', 'Nuclear',
        'Grid', 'Industry', 'Households', 'Transport',
      ];
      Plotly.newPlot('chart-sankey', [{
        type: 'sankey', orientation: 'h',
        node: {
          label: labels, pad: 14, thickness: 14,
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
        ...COMMON(),
        margin: { l: 10, r: 10, t: 10, b: 10 },
      }, { displayModeBar: false, responsive: true });
    }

    const ids = ['chart-surface', 'chart-heat', 'chart-candle', 'chart-sankey'];
    const ro = new ResizeObserver(() => ids.forEach((id) => {
      try { Plotly.Plots.resize(id); } catch (_) {}
    }));
    ro.observe(target);

    const themeObs = new MutationObserver(() => ids.forEach((id) => {
      try { Plotly.relayout(id, COMMON()); } catch (_) {}
    }));
    themeObs.observe(document.body, { attributes: true, attributeFilter: ['class'] });

    return {
      unmount() {
        ro.disconnect();
        themeObs.disconnect();
        ids.forEach((id) => { try { Plotly.purge(id); } catch (_) {} });
        target.innerHTML = '';
      },
    };
  },
};
