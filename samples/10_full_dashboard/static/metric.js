window.__stageViews = window.__stageViews || {};
window.__stageViews.metric = {
  async mount(target) {
    const ws = await window.__ensureAppSocket();
    await window.__stage.load('plotly');

    const dark = () => document.body.classList.contains('body--dark');
    const th = () => ({
      paper: 'rgba(0,0,0,0)', plot: 'rgba(0,0,0,0)',
      text: dark() ? '#e2e8f0' : '#1e293b',
      muted: dark() ? '#94a3b8' : '#64748b',
      grid: dark() ? 'rgba(255,255,255,.08)' : 'rgba(0,0,0,.08)',
    });
    const COMMON = () => {
      const t = th();
      return {
        paper_bgcolor: t.paper, plot_bgcolor: t.plot,
        font: { color: t.text, family: '-apple-system, system-ui, sans-serif', size: 12 },
        margin: { l: 45, r: 15, t: 10, b: 35 }, hovermode: 'x unified',
        xaxis: { gridcolor: t.grid, zerolinecolor: t.grid, linecolor: t.grid, tickcolor: t.muted },
        yaxis: { gridcolor: t.grid, zerolinecolor: t.grid, linecolor: t.grid, tickcolor: t.muted },
      };
    };

    target.innerHTML = `
      ${window.__capNavBar('/metric')}
      <div class="q-pa-md">
        <div class="row items-center justify-between q-mb-md">
          <div>
            <div class="text-h5">Live metrics</div>
            <div class="text-caption text-grey">Streaming at 2 Hz over the session WebSocket</div>
          </div>
          <div class="row q-gutter-sm">
            <button id="m-start" class="q-btn bg-primary text-white"
                    style="padding:6px 14px;border:0;border-radius:6px;cursor:pointer;font-size:13px">
              <q-icon name="play_arrow" size="16px"></q-icon> Start
            </button>
            <button id="m-stop" class="q-btn bg-grey-7 text-white"
                    style="padding:6px 14px;border:0;border-radius:6px;cursor:pointer;font-size:13px">
              <q-icon name="stop" size="16px"></q-icon> Stop
            </button>
          </div>
        </div>
        <div class="row q-col-gutter-md">
          <div class="col-12 col-md-8">
            <div class="q-card q-pa-md" style="height:320px">
              <div class="text-subtitle2 q-mb-sm">Requests per second</div>
              <div id="chart" style="width:100%;height:250px"></div>
            </div>
          </div>
          <div class="col-12 col-md-4">
            <div class="q-card q-pa-md" style="height:320px">
              <div class="text-subtitle2 q-mb-sm">Latest sample</div>
              <div class="text-caption text-grey">live value</div>
              <div id="latest" class="q-mt-xs" style="font-size:64px;font-weight:700;
                   background:linear-gradient(135deg,#6366f1,#06b6d4);
                   -webkit-background-clip:text;background-clip:text;color:transparent;
                   font-variant-numeric:tabular-nums;line-height:1">—</div>
              <div class="text-caption text-grey q-mt-sm">
                The server spawns an asyncio task on ``metric.start`` and pushes every 500 ms.
              </div>
            </div>
          </div>
        </div>
      </div>`;

    const xs = [], ys = [];
    const MAX = 200;
    Plotly.newPlot('chart',
      [{ x: xs, y: ys, mode: 'lines', fill: 'tozeroy',
         line: { color: '#6366f1', width: 2 },
         fillcolor: 'rgba(99,102,241,.15)' }],
      { ...COMMON(), yaxis: { ...COMMON().yaxis, range: [-2, 2] } },
      { displayModeBar: false, responsive: true });

    const latest = target.querySelector('#latest');
    const listener = (m) => {
      if (m.type !== 'metric.sample') return;
      xs.push(m.t); ys.push(m.value);
      if (xs.length > MAX) { xs.shift(); ys.shift(); }
      Plotly.update('chart', { x: [xs], y: [ys] });
      latest.textContent = m.value.toFixed(2);
    };
    window.__appListeners.push(listener);

    target.querySelector('#m-start').addEventListener('click',
      () => ws.send({type: 'metric.start'}));
    target.querySelector('#m-stop').addEventListener('click',
      () => ws.send({type: 'metric.stop'}));

    const themeObs = new MutationObserver(() => Plotly.relayout('chart', COMMON()));
    themeObs.observe(document.body, { attributes: true, attributeFilter: ['class'] });

    return {
      unmount() {
        const i = window.__appListeners.indexOf(listener);
        if (i >= 0) window.__appListeners.splice(i, 1);
        themeObs.disconnect();
        try { Plotly.purge('chart'); } catch (_) {}
        target.innerHTML = '';
      },
    };
  },
};
