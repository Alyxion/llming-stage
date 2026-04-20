async function ensureSocket() {
  if (window.__sampleSocket) return window.__sampleSocket;
  const {wsUrl} = await fetch('/api/session', {credentials: 'include'}).then((r) => r.json());
  const ws = new window.LlmingWebSocket(wsUrl, {
    onMessage: (m) => { (window.__sampleListeners || []).forEach((fn) => fn(m)); },
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
      <div class="column items-center justify-center" style="min-height:100%;gap:24px;padding:32px">
        <div style="width:100%;max-width:520px" class="q-card q-pa-lg">
          <div class="text-overline text-grey">shared session</div>
          <div class="text-h4 q-mt-xs">Multi-view SPA</div>
          <div class="text-caption text-grey q-mt-xs">
            Two routes, one WebSocket. Navigating doesn't reconnect — the
            server-side timer keeps running.
          </div>
          <div class="q-mt-lg row q-gutter-sm">
            <a data-stage-link href="/timer"
               class="q-btn bg-primary text-white"
               style="padding:10px 18px;border-radius:8px;text-decoration:none;
                      font-weight:500;display:inline-block">
              Open timer →
            </a>
          </div>
        </div>
      </div>`;
    await ensureSocket();
    return { unmount() { target.innerHTML = ''; } };
  },
};
