window.__stageViews = window.__stageViews || {};
window.__stageViews.uploads = {
  async mount(target) {
    const ws = await window.__ensureAppSocket();
    target.innerHTML = `
      <div class="q-pa-md" style="max-width:900px;margin:auto">
        <nav style="margin-bottom:24px">${window.__navLinks('/uploads')}</nav>
        <h1 class="text-h5">Uploads</h1>
        <input type="file" id="file" style="display:block;margin:12px 0">
        <button id="go" class="b">Upload</button>
        <p id="progress" style="font-family:monospace"></p>
        <ul id="history" style="font-family:monospace"></ul>
      </div>
      <style>.b{padding:6px 12px;background:#1976d2;color:#fff;border:0;border-radius:4px;cursor:pointer}</style>`;

    const progress = document.getElementById('progress');
    const history = document.getElementById('history');

    const render = (items) => {
      history.innerHTML = '';
      for (const it of items) {
        const li = document.createElement('li');
        li.textContent = `${it.name} — ${it.bytes} bytes — ${it.sha256.slice(0, 12)}…`;
        history.appendChild(li);
      }
    };

    const listener = (m) => {
      if (m.type === 'uploads.list') render(m.items);
      else if (m.type === 'upload.progress')
        progress.textContent = `${m.name}: ${m.bytes} bytes…`;
      else if (m.type === 'upload.done') {
        progress.textContent = `${m.name}: done`;
        ws.send({type: 'uploads.list'});
      }
    };
    window.__appListeners.push(listener);
    ws.send({type: 'uploads.list'});

    document.getElementById('go').addEventListener('click', async () => {
      const f = document.getElementById('file').files[0];
      if (!f) return;
      const fd = new FormData();
      fd.append('file', f);
      progress.textContent = `${f.name}: starting…`;
      await fetch('/api/upload', {method: 'POST', body: fd, credentials: 'include'});
    });

    return {
      unmount() {
        const i = window.__appListeners.indexOf(listener);
        if (i >= 0) window.__appListeners.splice(i, 1);
        target.innerHTML = '';
      },
    };
  },
};
