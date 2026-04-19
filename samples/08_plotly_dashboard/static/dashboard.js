window.__stageViews = window.__stageViews || {};
window.__stageViews.dashboard = {
  async mount(target) {
    target.innerHTML = `
      <div class="q-pa-md" style="max-width:900px;margin:auto">
        <h1 class="text-h4">Live metric (Plotly, lazy-loaded)</h1>
        <div id="chart" style="width:100%;height:420px"></div>
        <button id="start" class="d-btn">Start stream</button>
        <button id="stop" class="d-btn" style="margin-left:8px;background:#888">Stop</button>
      </div>
      <style>
        .d-btn { padding:8px 16px; background:#1976d2; color:#fff;
          border:0; border-radius:4px; cursor:pointer }
      </style>`;

    await window.__stage.load('plotly');

    const xs = [], ys = [];
    Plotly.newPlot('chart', [
      {x: xs, y: ys, mode: 'lines', line: {color: '#1976d2'}, name: 'value'},
    ], {
      margin: {l: 40, r: 20, t: 10, b: 40},
      xaxis: {title: 't (s)'},
      yaxis: {title: 'value', range: [-2, 2]},
    }, {displayModeBar: false, responsive: true});

    const {wsUrl} = await fetch('/api/session', {credentials: 'include'})
      .then(r => r.json());
    const ws = new window.LlmingWebSocket(wsUrl, {
      onMessage: (m) => {
        if (m.type === 'metric.sample') {
          xs.push(m.t);
          ys.push(m.value);
          if (xs.length > 200) { xs.shift(); ys.shift(); }
          Plotly.update('chart', {x: [xs], y: [ys]});
        }
      },
    });
    ws.connect();

    document.getElementById('start').addEventListener('click',
      () => ws.send({type: 'metric.start'}));
    document.getElementById('stop').addEventListener('click',
      () => ws.send({type: 'metric.stop'}));

    return {
      unmount() {
        ws.send({type: 'metric.stop'});
        ws.close();
        Plotly.purge('chart');
        target.innerHTML = '';
      },
    };
  },
};
