window.__stageViews = window.__stageViews || {};
window.__stageViews.home = {
  async mount(target) {
    target.innerHTML = `
      <div class="column items-center justify-center" style="min-height:100%;gap:24px;padding:32px">
        <div style="width:100%;max-width:420px" class="q-card q-pa-xl text-center">
          <div class="text-overline text-grey">server-held counter</div>
          <div id="val" class="q-my-lg" style="font-size:120px;font-weight:700;
               background:linear-gradient(135deg,#6366f1,#06b6d4);
               -webkit-background-clip:text;background-clip:text;color:transparent;
               font-variant-numeric:tabular-nums;line-height:1">0</div>
          <div class="row q-gutter-sm justify-center">
            <button id="dec" class="q-btn bg-grey-7 text-white"
                    style="padding:10px 22px;border:0;border-radius:8px;font-size:22px;cursor:pointer">−</button>
            <button id="inc" class="q-btn bg-primary text-white"
                    style="padding:10px 22px;border:0;border-radius:8px;font-size:22px;cursor:pointer">+</button>
            <button id="reset" class="q-btn bg-negative text-white"
                    style="padding:10px 22px;border:0;border-radius:8px;cursor:pointer">reset</button>
          </div>
          <div class="text-caption text-grey q-mt-lg">
            Open two tabs — each gets its own session and counter.
          </div>
        </div>
      </div>`;

    const {wsUrl} = await fetch('/api/session', {credentials: 'include'}).then((r) => r.json());
    const val = target.querySelector('#val');
    const ws = new window.LlmingWebSocket(wsUrl, {
      onMessage: (m) => { if (m.type === 'counter.update') val.textContent = m.value; },
    });
    ws.connect();

    target.querySelector('#inc').addEventListener('click',
      () => ws.send({type: 'counter.inc', by: 1}));
    target.querySelector('#dec').addEventListener('click',
      () => ws.send({type: 'counter.inc', by: -1}));
    target.querySelector('#reset').addEventListener('click',
      () => ws.send({type: 'counter.reset'}));

    return { unmount() { ws.close(); target.innerHTML = ''; } };
  },
};
