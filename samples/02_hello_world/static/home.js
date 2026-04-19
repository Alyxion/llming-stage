window.__stageViews = window.__stageViews || {};
window.__stageViews.home = {
  async mount(target) {
    target.innerHTML = `
      <div class="q-pa-xl" style="max-width:500px;margin:auto">
        <h1 class="text-h4">hello_world</h1>
        <p>FE → BE:
          <input id="name" placeholder="your name" value="world"
                 style="padding:4px;border:1px solid #ccc;border-radius:3px">
          <button id="say" style="padding:4px 12px">Say hi</button>
        </p>
        <p id="reply" style="color:#1976d2;min-height:1.4em"></p>
        <p class="q-mt-lg">BE → FE (every 1 s):
          <code id="tick" style="font-family:monospace">—</code></p>
      </div>`;

    const {wsUrl} = await fetch('/api/session', {credentials: 'include'}).then(r => r.json());
    const ws = new window.LlmingWebSocket(wsUrl, {
      onMessage: (m) => {
        if (m.type === 'hello.reply') document.getElementById('reply').textContent = m.text;
        else if (m.type === 'tick') document.getElementById('tick').textContent = 'tick ' + m.n;
      },
    });
    ws.connect();

    document.getElementById('say').addEventListener('click', () => {
      ws.send({type: 'hello.say', name: document.getElementById('name').value});
    });

    return { unmount() { ws.close(); target.innerHTML = ''; } };
  },
};
