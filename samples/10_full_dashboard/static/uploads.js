window.__stageViews = window.__stageViews || {};
window.__stageViews.uploads = {
  async mount(target) {
    const ws = await window.__ensureAppSocket();
    target.innerHTML = `
      ${window.__capNavBar('/uploads')}
      <div class="q-pa-md" style="max-width:760px;margin:0 auto">
        <div class="text-h5 q-mb-xs">Uploads</div>
        <div class="text-caption text-grey q-mb-md">
          Cookie-authed HTTP POST; progress streams on the shared WebSocket.
        </div>
        <div class="q-card q-pa-md">
          <input id="file" type="file" style="display:block;margin-bottom:12px">
          <div class="row items-center q-gutter-sm">
            <button id="go" class="q-btn bg-primary text-white"
                    style="padding:8px 16px;border:0;border-radius:6px;cursor:pointer">
              Upload
            </button>
            <div id="progress" class="text-caption text-grey"
                 style="font-variant-numeric:tabular-nums;min-height:1.4em"></div>
          </div>
        </div>
        <div class="q-card q-pa-md q-mt-md">
          <div class="text-overline text-grey q-mb-sm">history</div>
          <ul id="history" style="margin:0;padding-left:20px;
              font-family:ui-monospace,monospace;font-size:13px;line-height:1.8"></ul>
        </div>
      </div>`;

    const progress = target.querySelector('#progress');
    const history = target.querySelector('#history');

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

    const listener = (m) => {
      if (m.type === 'uploads.list')      render(m.items);
      else if (m.type === 'upload.progress')
        progress.textContent = `${m.name}: ${m.bytes.toLocaleString()} bytes…`;
      else if (m.type === 'upload.done') {
        progress.textContent = `${m.name}: done`;
        ws.send({type: 'uploads.list'});
      }
    };
    window.__appListeners.push(listener);
    ws.send({type: 'uploads.list'});

    target.querySelector('#go').addEventListener('click', async () => {
      const f = target.querySelector('#file').files[0];
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
