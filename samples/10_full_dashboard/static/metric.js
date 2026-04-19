window.__stageViews = window.__stageViews || {};
window.__stageViews.metric = {
  async mount(target) {
    const ws = await window.__ensureAppSocket();
    await window.__stage.load('plotly');

    target.innerHTML = `
      <div class="q-pa-md" style="max-width:900px;margin:auto">
        <nav style="margin-bottom:24px">${window.__navLinks('/metric')}</nav>
        <h1 class="text-h5">Live chart</h1>
        <div id="chart" style="width:100%;height:400px"></div>
        <div class="q-mt-sm">
          <button id="start" class="b">Start</button>
          <button id="stop" class="b" style="margin-left:8px;background:#888">Stop</button>
        </div>
      </div>
      <style>.b{padding:6px 12px;background:#1976d2;color:#fff;border:0;border-radius:4px;cursor:pointer}</style>`;

    const xs = [], ys = [];
    Plotly.newPlot('chart', [{x: xs, y: ys, mode: 'lines', line: {color: '#1976d2'}}], {
      margin: {l: 40, r: 20, t: 10, b: 40},
      yaxis: {range: [-2, 2]},
    }, {displayModeBar: false, responsive: true});

    const listener = (m) => {
      if (m.type === 'metric.sample') {
        xs.push(m.t); ys.push(m.value);
        if (xs.length > 200) { xs.shift(); ys.shift(); }
        Plotly.update('chart', {x: [xs], y: [ys]});
      }
    };
    window.__appListeners.push(listener);

    document.getElementById('start').addEventListener('click',
      () => ws.send({type: 'metric.start'}));
    document.getElementById('stop').addEventListener('click',
      () => ws.send({type: 'metric.stop'}));

    return {
      unmount() {
        const i = window.__appListeners.indexOf(listener);
        if (i >= 0) window.__appListeners.splice(i, 1);
        Plotly.purge('chart');
        target.innerHTML = '';
      },
    };
  },
};
