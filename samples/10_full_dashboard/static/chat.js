window.__stageViews = window.__stageViews || {};
window.__stageViews.chat = {
  async mount(target) {
    const ws = await window.__ensureAppSocket();
    target.innerHTML = `
      ${window.__capNavBar('/chat')}
      <div class="column" style="flex:1;padding:16px 20px">
        <div style="max-width:780px;margin:0 auto;flex:1;display:flex;flex-direction:column;gap:14px;width:100%">
          <div>
            <div class="text-h5">Chat</div>
            <div class="text-caption text-grey">Streamed replies over the same session socket.</div>
          </div>
          <div id="log" class="q-card q-pa-md" style="flex:1;overflow:auto;min-height:300px"></div>
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

    const log = target.querySelector('#log');
    const q = target.querySelector('#q');
    const pending = new Map();

    const addMsg = (role, text = '') => {
      const row = document.createElement('div');
      row.className = `msg ${role}`;
      const av = document.createElement('div');
      av.className = 'avatar';
      av.textContent = role === 'user' ? 'U' : 'A';
      const body = document.createElement('div');
      body.className = 'body';
      body.textContent = text;
      row.appendChild(av);
      row.appendChild(body);
      log.appendChild(row);
      log.scrollTop = log.scrollHeight;
      return body;
    };

    const listener = (m) => {
      if (m.type === 'chat.history') {
        for (const msg of m.messages) addMsg(msg.role, msg.text);
      } else if (m.type === 'chat.start')      pending.set(m.id, addMsg('assistant'));
      else if (m.type === 'chat.delta') {
        const b = pending.get(m.id);
        if (b) { b.textContent += m.delta; log.scrollTop = log.scrollHeight; }
      } else if (m.type === 'chat.done') pending.delete(m.id);
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
    target.querySelector('#send').addEventListener('click', send);
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
