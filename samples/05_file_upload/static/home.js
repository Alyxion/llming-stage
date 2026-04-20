window.__stageViews = window.__stageViews || {};
window.__stageViews.home = {
  async mount(target) {
    target.innerHTML = `
      <div class="q-pa-lg column items-center" style="gap:20px;min-height:100%">
        <div style="width:100%;max-width:640px;display:flex;flex-direction:column;gap:20px">
          <div>
            <div class="text-h4">File upload</div>
            <div class="text-caption text-grey">
              HTTP POST carries the bytes; the WebSocket streams progress and completion.
            </div>
          </div>
          <div class="q-card q-pa-md">
            <input id="file" type="file" style="display:block;margin-bottom:12px">
            <div class="row items-center q-gutter-sm">
              <button id="go" class="q-btn bg-primary text-white"
                      style="padding:8px 18px;border:0;border-radius:6px;cursor:pointer">
                Upload
              </button>
              <div id="progress" class="text-caption text-grey"
                   style="font-variant-numeric:tabular-nums;min-height:1.4em"></div>
            </div>
          </div>
          <div class="q-card q-pa-md">
            <div class="text-overline text-grey q-mb-sm">history · this session</div>
            <ul id="history" style="margin:0;padding-left:20px;
                font-family:ui-monospace,monospace;font-size:13px;line-height:1.8"></ul>
          </div>
        </div>
      </div>`;

    const {wsUrl} = await fetch('/api/session', {credentials: 'include'}).then((r) => r.json());
    const history = target.querySelector('#history');
    const progress = target.querySelector('#progress');

    const render = (items) => {
      history.innerHTML = '';
      if (!items.length) {
        history.innerHTML = '<li style="list-style:none;opacity:.5">no uploads yet</li>';
        return;
      }
      for (const it of items) {
        const li = document.createElement('li');
        li.textContent = `${it.name} — ${it.bytes.toLocaleString()} bytes — ${it.sha256.slice(0, 12)}…`;
        history.appendChild(li);
      }
    };

    const ws = new window.LlmingWebSocket(wsUrl, {
      onOpen: () => ws.send({type: 'uploads.list'}),
      onMessage: (m) => {
        if (m.type === 'uploads.list') render(m.items);
        else if (m.type === 'upload.progress')
          progress.textContent = `${m.name}: ${m.bytes.toLocaleString()} bytes…`;
        else if (m.type === 'upload.done') {
          progress.textContent = `${m.name}: done · sha256 ${m.sha256.slice(0, 12)}…`;
          ws.send({type: 'uploads.list'});
        }
      },
    });
    ws.connect();

    target.querySelector('#go').addEventListener('click', async () => {
      const f = target.querySelector('#file').files[0];
      if (!f) return;
      const fd = new FormData();
      fd.append('file', f);
      progress.textContent = `${f.name}: starting…`;
      await fetch('/api/upload', {method: 'POST', body: fd, credentials: 'include'});
    });

    return { unmount() { ws.close(); target.innerHTML = ''; } };
  },
};
