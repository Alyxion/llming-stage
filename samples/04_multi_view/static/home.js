// Shared WebSocket — created once, hung off `window` so the timer view reuses it.
async function ensureSocket() {
  if (window.__sampleSocket) return window.__sampleSocket;
  const {wsUrl} = await fetch('/api/session', {credentials: 'include'}).then(r => r.json());
  const ws = new window.LlmingWebSocket(wsUrl, {
    onMessage: (m) => { (window.__sampleListeners || []).forEach(fn => fn(m)); },
  });
  ws.connect();
  window.__sampleSocket = ws;
  window.__sampleListeners = [];
  return ws;
}
window.__ensureSampleSocket = ensureSocket;

window.__stageViews = window.__stageViews || {};
window.__stageViews.home = {
  async mount(target) {
    target.innerHTML = `
      <div class="q-pa-xl" style="max-width:600px;margin:auto">
        <h1 class="text-h4">Home</h1>
        <p>One session, two views. Navigating keeps the WebSocket alive.</p>
        <p class="q-mt-lg">
          <a data-stage-link href="/timer"
             style="color:#1976d2;text-decoration:underline">Open timer →</a>
        </p>
      </div>`;
    await ensureSocket();  // establish early so /timer inherits it
    return { unmount() { target.innerHTML = ''; } };
  },
};
