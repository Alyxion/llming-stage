window.__stageViews = window.__stageViews || {};
window.__stageViews.timer = {
  async mount(target) {
    target.innerHTML = `
      <div class="column items-center justify-center" style="min-height:100%;gap:24px;padding:32px">
        <div style="width:100%;max-width:420px" class="q-card q-pa-xl text-center">
          <div class="text-overline text-grey">server-driven countdown</div>
          <div id="val" class="q-my-lg" style="font-size:96px;font-weight:700;
               background:linear-gradient(135deg,#f59e0b,#ef4444);
               -webkit-background-clip:text;background-clip:text;color:transparent;
               font-variant-numeric:tabular-nums;line-height:1">—</div>
          <div class="row q-gutter-sm justify-center">
            <button id="start" class="q-btn bg-primary text-white"
                    style="padding:10px 20px;border:0;border-radius:8px;cursor:pointer">
              Start 10 s
            </button>
            <button id="cancel" class="q-btn bg-grey-7 text-white"
                    style="padding:10px 20px;border:0;border-radius:8px;cursor:pointer">
              Cancel
            </button>
          </div>
          <div class="q-mt-lg">
            <a data-stage-link href="/" class="text-primary"
               style="text-decoration:none">← Back home</a>
          </div>
        </div>
      </div>`;

    const ws = await window.__ensureSampleSocket();
    const val = target.querySelector('#val');
    const listener = (m) => {
      if (m.type === 'timer.tick')      val.textContent = m.remaining + 's';
      else if (m.type === 'timer.done') val.textContent = '✓ done';
    };
    window.__sampleListeners.push(listener);

    target.querySelector('#start').addEventListener('click',
      () => ws.send({type: 'timer.start', seconds: 10}));
    target.querySelector('#cancel').addEventListener('click',
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
