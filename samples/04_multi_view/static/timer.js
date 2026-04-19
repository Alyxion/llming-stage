window.__stageViews = window.__stageViews || {};
window.__stageViews.timer = {
  async mount(target) {
    target.innerHTML = `
      <div class="q-pa-xl text-center" style="max-width:600px;margin:auto">
        <h1 class="text-h4">Timer</h1>
        <p style="font-size:64px;margin:24px 0" id="val">—</p>
        <button id="start" class="t-btn">Start 10s</button>
        <button id="cancel" class="t-btn" style="margin-left:12px;background:#888">Cancel</button>
        <p class="q-mt-xl">
          <a data-stage-link href="/"
             style="color:#1976d2;text-decoration:underline">← Back home</a>
        </p>
      </div>
      <style>
        .t-btn { padding:8px 16px; background:#1976d2; color:#fff;
          border:0; border-radius:4px; cursor:pointer; font-size:16px }
      </style>`;

    const ws = await window.__ensureSampleSocket();
    const val = document.getElementById('val');

    const listener = (m) => {
      if (m.type === 'timer.tick') val.textContent = m.remaining + 's';
      else if (m.type === 'timer.done') val.textContent = '✓ done';
    };
    window.__sampleListeners.push(listener);

    document.getElementById('start').addEventListener('click',
      () => ws.send({type: 'timer.start', seconds: 10}));
    document.getElementById('cancel').addEventListener('click',
      () => ws.send({type: 'timer.cancel'}));

    return {
      unmount() {
        const i = window.__sampleListeners.indexOf(listener);
        if (i >= 0) window.__sampleListeners.splice(i, 1);
        target.innerHTML = '';
      },
    };
  },
};
