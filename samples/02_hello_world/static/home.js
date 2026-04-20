window.__stageViews = window.__stageViews || {};
window.__stageViews.home = {
  async mount(target) {
    target.innerHTML = `
      <div class="q-pa-lg column items-center" style="gap:24px;min-height:100%">
        <div style="width:100%;max-width:520px;display:flex;flex-direction:column;gap:20px">
          <div>
            <div class="text-h4">hello_world</div>
            <div class="text-caption text-grey">One FE→BE call and a once-per-second BE→FE tick.</div>
          </div>
          <div class="q-card q-pa-md">
            <div class="text-overline text-grey">FE → BE</div>
            <div class="row items-center q-gutter-sm q-mt-xs">
              <input id="name" placeholder="your name" value="world"
                     class="q-field__native" style="flex:1;padding:8px 10px;
                     border:1px solid rgba(128,128,128,.3);border-radius:4px;background:transparent">
              <button id="say" class="q-btn q-btn--standard bg-primary text-white"
                      style="padding:8px 16px;border:0;border-radius:4px;cursor:pointer;font-weight:500">
                Say hi
              </button>
            </div>
            <div id="reply" class="q-mt-md text-subtitle1"
                 style="min-height:1.6em;color:var(--q-primary)"></div>
          </div>
          <div class="q-card q-pa-md">
            <div class="row items-center justify-between">
              <div class="text-overline text-grey">BE → FE timer</div>
              <q-chip class="bg-positive text-white" dense>live</q-chip>
            </div>
            <div class="text-h3 q-mt-sm" id="tick" style="font-variant-numeric:tabular-nums">—</div>
          </div>
        </div>
      </div>`;

    const {wsUrl} = await fetch('/api/session', {credentials: 'include'}).then((r) => r.json());
    const ws = new window.LlmingWebSocket(wsUrl, {
      onMessage: (m) => {
        if (m.type === 'hello.reply') target.querySelector('#reply').textContent = m.text;
        else if (m.type === 'tick')   target.querySelector('#tick').textContent = 'tick ' + m.n;
      },
    });
    ws.connect();

    target.querySelector('#say').addEventListener('click', () => {
      ws.send({type: 'hello.say', name: target.querySelector('#name').value});
    });

    return { unmount() { ws.close(); target.innerHTML = ''; } };
  },
};
