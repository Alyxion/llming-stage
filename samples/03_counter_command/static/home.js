window.__stageViews = window.__stageViews || {};
window.__stageViews.home = {
  async mount(target) {
    target.innerHTML = `
      <div class="q-pa-xl text-center">
        <h1 class="text-h4">Counter</h1>
        <p class="text-caption">Session: <code id="sid">…</code></p>
        <div style="font-size:64px;margin:24px 0" id="val">0</div>
        <button id="dec" class="counter-btn">−</button>
        <button id="inc" class="counter-btn">+</button>
        <button id="reset" class="counter-btn" style="margin-left:24px">reset</button>
      </div>
      <style>
        .counter-btn { padding:8px 16px; margin:0 4px;
          background:#1976d2; color:#fff; border:0; border-radius:4px;
          font-size:18px; cursor:pointer }
      </style>`;

    const {sessionId, wsUrl} = await fetch('/api/session', {credentials: 'include'})
      .then(r => r.json());
    document.getElementById('sid').textContent = sessionId;

    const val = document.getElementById('val');
    const ws = new window.LlmingWebSocket(wsUrl, {
      onMessage: (m) => {
        if (m.type === 'counter.update') val.textContent = m.value;
      },
    });
    ws.connect();

    document.getElementById('inc').addEventListener('click',
      () => ws.send({type: 'counter.inc', by: 1}));
    document.getElementById('dec').addEventListener('click',
      () => ws.send({type: 'counter.inc', by: -1}));
    document.getElementById('reset').addEventListener('click',
      () => ws.send({type: 'counter.reset'}));

    return { unmount() { ws.close(); target.innerHTML = ''; } };
  },
};
