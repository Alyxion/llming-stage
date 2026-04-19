window.__stageViews = window.__stageViews || {};
window.__stageViews.chat = {
  async mount(target) {
    const ws = await window.__ensureAppSocket();
    target.innerHTML = `
      <div class="q-pa-md" style="max-width:700px;margin:auto">
        <nav style="margin-bottom:24px">${window.__navLinks('/chat')}</nav>
        <h1 class="text-h5">Chat</h1>
        <div id="log" style="min-height:300px;padding:12px;border:1px solid #ddd;border-radius:4px;background:#fafafa"></div>
        <div style="display:flex;gap:8px;margin-top:16px">
          <input id="q" placeholder="Ask anything" style="flex:1;padding:6px;border:1px solid #ccc;border-radius:4px">
          <button id="send" class="b">Send</button>
        </div>
      </div>
      <style>
        .b{padding:6px 12px;background:#1976d2;color:#fff;border:0;border-radius:4px;cursor:pointer}
        .u{color:#444}.a{color:#1976d2}.msg{margin:4px 0}
      </style>`;

    const log = document.getElementById('log');
    const q = document.getElementById('q');
    const pending = new Map();

    const addMsg = (role, text = '') => {
      const d = document.createElement('div');
      d.className = `msg ${role === 'user' ? 'u' : 'a'}`;
      d.textContent = `${role}: ${text}`;
      log.appendChild(d);
      return d;
    };

    const listener = (m) => {
      if (m.type === 'chat.history') {
        for (const msg of m.messages) addMsg(msg.role, msg.text);
      } else if (m.type === 'chat.start') {
        pending.set(m.id, addMsg('assistant'));
      } else if (m.type === 'chat.delta') {
        const d = pending.get(m.id);
        if (d) d.textContent += m.delta;
      } else if (m.type === 'chat.done') {
        pending.delete(m.id);
      }
    };
    window.__appListeners.push(listener);
    ws.send({type: 'chat.history'});

    const send = () => {
      const text = q.value.trim();
      if (!text) return;
      addMsg('user', text);
      q.value = '';
      ws.send({type: 'chat.ask', text});
    };
    document.getElementById('send').addEventListener('click', send);
    q.addEventListener('keydown', (e) => { if (e.key === 'Enter') send(); });

    return {
      unmount() {
        const i = window.__appListeners.indexOf(listener);
        if (i >= 0) window.__appListeners.splice(i, 1);
        target.innerHTML = '';
      },
    };
  },
};
