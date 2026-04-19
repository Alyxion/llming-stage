// Shared socket + listener registry, created lazily on first view mount.
async function ensureSocket() {
  if (window.__appSocket) return window.__appSocket;
  const {sessionId, wsUrl} = await fetch('/api/session', {credentials: 'include'})
    .then(r => r.json());
  window.__appSessionId = sessionId;
  const listeners = [];
  const ws = new window.LlmingWebSocket(wsUrl, {
    onMessage: (m) => listeners.forEach(fn => fn(m)),
  });
  ws.connect();
  window.__appSocket = ws;
  window.__appListeners = listeners;
  return ws;
}
window.__ensureAppSocket = ensureSocket;

function navLinks(active) {
  const items = [
    ['/', 'Home'],
    ['/metric', 'Live chart'],
    ['/uploads', 'Uploads'],
    ['/chat', 'Chat'],
  ];
  return items.map(([h, l]) =>
    `<a data-stage-link href="${h}" style="margin-right:16px;color:${h === active ? '#1976d2' : '#666'};text-decoration:${h === active ? 'underline' : 'none'}">${l}</a>`
  ).join('');
}
window.__navLinks = navLinks;

window.__stageViews = window.__stageViews || {};
window.__stageViews.home = {
  async mount(target) {
    await ensureSocket();
    target.innerHTML = `
      <div class="q-pa-md" style="max-width:900px;margin:auto">
        <nav style="margin-bottom:24px">${navLinks('/')}</nav>
        <h1 class="text-h4">Capstone dashboard</h1>
        <p>One SPA, one session, one WebSocket. Navigating between
           views keeps all state alive.</p>
        <p class="text-caption q-mt-lg">
          Session: <code>${window.__appSessionId}</code>
        </p>
        <ul style="line-height:1.8">
          <li><b>Live chart</b> — Plotly + server-pushed metric stream</li>
          <li><b>Uploads</b> — HTTP POST + WS progress events</li>
          <li><b>Chat</b> — streamed replies over the same socket</li>
        </ul>
      </div>`;
    return { unmount() { target.innerHTML = ''; } };
  },
};
