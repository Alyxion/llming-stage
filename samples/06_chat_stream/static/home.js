window.__stageViews = window.__stageViews || {};
window.__stageViews.home = {
  async mount(target) {
    target.innerHTML = `
      <div class="column" style="min-height:100%;padding:20px 24px">
        <div style="width:100%;max-width:760px;margin:0 auto;display:flex;flex-direction:column;flex:1;gap:16px">
          <div>
            <div class="text-h5">Streaming chat</div>
            <div class="text-caption text-grey">
              Server emits chat.start → chat.delta × N → chat.done; client appends tokens live.
            </div>
          </div>
          <div id="log" class="q-card q-pa-md" style="flex:1;overflow:auto;min-height:280px"></div>
          <div class="q-card q-pa-sm row items-center q-gutter-sm no-wrap">
            <input id="q" placeholder="Ask anything"
                   style="flex:1;padding:10px 12px;border:0;background:transparent;outline:none;font-size:15px">
            <button id="send" class="q-btn bg-primary text-white"
                    style="padding:8px 18px;border:0;border-radius:6px;cursor:pointer">
              Send
            </button>
          </div>
        </div>
      </div>
      <style>
        .msg { margin: 10px 0; display: flex; gap: 10px; align-items: flex-start; }
        .msg .avatar { flex: 0 0 32px; width: 32px; height: 32px; border-radius: 50%;
          display: flex; align-items: center; justify-content: center;
          font-size: 16px; font-weight: 600; color: #fff; }
        .msg.user .avatar { background: #64748b; }
        .msg.assistant .avatar { background: linear-gradient(135deg,#6366f1,#a855f7); }
        .msg .body { flex: 1; padding: 8px 12px; border-radius: 8px;
          background: rgba(128,128,128,0.08); line-height: 1.55; }
        .msg.user .body { background: rgba(99,102,241,0.08); }
      </style>`;

    const {wsUrl} = await fetch('/api/session', {credentials: 'include'}).then((r) => r.json());
    const log = target.querySelector('#log');
    const input = target.querySelector('#q');
    const pending = new Map();

    const addMsg = (role, text = '') => {
      const row = document.createElement('div');
      row.className = `msg ${role}`;
      const av = document.createElement('div'); av.className = 'avatar';
      av.textContent = role === 'user' ? 'U' : 'A';
      const body = document.createElement('div'); body.className = 'body';
      body.textContent = text;
      row.appendChild(av); row.appendChild(body);
      log.appendChild(row);
      log.scrollTop = log.scrollHeight;
      return body;
    };

    const ws = new window.LlmingWebSocket(wsUrl, {
      onMessage: (m) => {
        if (m.type === 'chat.start')      pending.set(m.id, addMsg('assistant'));
        else if (m.type === 'chat.delta') {
          const b = pending.get(m.id);
          if (b) { b.textContent += m.delta; log.scrollTop = log.scrollHeight; }
        } else if (m.type === 'chat.done') pending.delete(m.id);
      },
    });
    ws.connect();

    const send = () => {
      const text = input.value.trim();
      if (!text) return;
      addMsg('user', text);
      input.value = '';
      ws.send({type: 'chat.ask', text});
    };
    target.querySelector('#send').addEventListener('click', send);
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') send(); });

    return { unmount() { ws.close(); target.innerHTML = ''; } };
  },
};
