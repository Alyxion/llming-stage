window.__stageViews = window.__stageViews || {};
window.__stageViews.home = {
  async mount(target) {
    target.innerHTML = `
      <div class="q-pa-xl" style="max-width:700px;margin:auto">
        <h1 class="text-h4">File upload</h1>
        <p>POST goes to <code>/api/upload</code>. Progress + completion
           events stream back on the WebSocket.</p>
        <input type="file" id="file" style="display:block;margin:16px 0">
        <button id="go" class="up-btn">Upload</button>
        <p id="progress" class="q-mt-md" style="font-family:monospace"></p>
        <h2 class="text-h6 q-mt-xl">History (server-held per session)</h2>
        <ul id="history" style="font-family:monospace"></ul>
      </div>
      <style>
        .up-btn { padding:8px 16px; background:#1976d2; color:#fff;
          border:0; border-radius:4px; cursor:pointer }
      </style>`;

    const {wsUrl} = await fetch('/api/session', {credentials: 'include'})
      .then(r => r.json());
    const history = document.getElementById('history');
    const progress = document.getElementById('progress');

    const renderHistory = (items) => {
      history.innerHTML = '';
      for (const it of items) {
        const li = document.createElement('li');
        li.textContent = `${it.name} — ${it.bytes} bytes — ${it.sha256.slice(0, 12)}…`;
        history.appendChild(li);
      }
    };

    const ws = new window.LlmingWebSocket(wsUrl, {
      onOpen: () => ws.send({type: 'uploads.list'}),
      onMessage: (m) => {
        if (m.type === 'uploads.list') renderHistory(m.items);
        else if (m.type === 'upload.progress')
          progress.textContent = `${m.name}: ${m.bytes} bytes…`;
        else if (m.type === 'upload.done') {
          progress.textContent = `${m.name}: done (sha256 ${m.sha256.slice(0, 12)}…)`;
          ws.send({type: 'uploads.list'});
        }
      },
    });
    ws.connect();

    document.getElementById('go').addEventListener('click', async () => {
      const f = document.getElementById('file').files[0];
      if (!f) return;
      const fd = new FormData();
      fd.append('file', f);
      progress.textContent = `${f.name}: starting…`;
      await fetch('/api/upload', {method: 'POST', body: fd, credentials: 'include'});
    });

    return { unmount() { ws.close(); target.innerHTML = ''; } };
  },
};
