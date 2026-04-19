window.__stageViews = window.__stageViews || {};
window.__stageViews.home = {
  async mount(target) {
    target.innerHTML = `
      <div class="q-pa-xl" style="max-width:700px;margin:auto">
        <h1 class="text-h4">Streaming chat</h1>
        <div id="log" style="min-height:200px;padding:12px;border:1px solid #ddd;border-radius:4px;background:#fafafa"></div>
        <div style="display:flex;gap:8px;margin-top:16px">
          <input id="q" placeholder="Ask anything"
                 style="flex:1;padding:8px;border:1px solid #ccc;border-radius:4px">
          <button id="send" class="c-btn">Send</button>
        </div>
      </div>
      <style>
        .c-btn { padding:8px 16px; background:#1976d2; color:#fff;
          border:0; border-radius:4px; cursor:pointer }
        .msg { margin:8px 0; }
        .msg.user { color:#444; }
        .msg.assistant { color:#1976d2; }
      </style>`;

    const {wsUrl} = await fetch('/api/session', {credentials: 'include'})
      .then(r => r.json());
    const log = document.getElementById('log');
    const inputEl = document.getElementById('q');
    const currentPerId = new Map();

    const addMsg = (role, text = '') => {
      const div = document.createElement('div');
      div.className = `msg ${role}`;
      div.textContent = `${role}: ${text}`;
      log.appendChild(div);
      return div;
    };

    const ws = new window.LlmingWebSocket(wsUrl, {
      onMessage: (m) => {
        if (m.type === 'chat.start') {
          currentPerId.set(m.id, addMsg('assistant'));
        } else if (m.type === 'chat.delta') {
          const div = currentPerId.get(m.id);
          if (div) div.textContent += m.delta;
        } else if (m.type === 'chat.done') {
          currentPerId.delete(m.id);
        }
      },
    });
    ws.connect();

    const send = () => {
      const text = inputEl.value.trim();
      if (!text) return;
      addMsg('user', text);
      inputEl.value = '';
      ws.send({type: 'chat.ask', text});
    };
    document.getElementById('send').addEventListener('click', send);
    inputEl.addEventListener('keydown', (e) => { if (e.key === 'Enter') send(); });

    return { unmount() { ws.close(); target.innerHTML = ''; } };
  },
};
