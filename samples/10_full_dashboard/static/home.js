async function ensureSocket() {
  if (window.__appSocket) return window.__appSocket;
  const {sessionId, wsUrl} = await fetch('/api/session', {credentials: 'include'})
    .then((r) => r.json());
  window.__appSessionId = sessionId;
  const listeners = [];
  const ws = new window.LlmingWebSocket(wsUrl, {
    onMessage: (m) => listeners.forEach((fn) => fn(m)),
  });
  ws.connect();
  window.__appSocket = ws;
  window.__appListeners = listeners;
  return ws;
}
window.__ensureAppSocket = ensureSocket;

function navBar(active) {
  const items = [
    ['/',         'Home',     'home'],
    ['/metric',   'Metrics',  'insights'],
    ['/uploads',  'Uploads',  'cloud_upload'],
    ['/chat',     'Chat',     'forum'],
  ];
  return `
    <div class="cap-nav">
      <div class="cap-brand">
        <div class="cap-brand-mark">◎</div>
        <div>
          <div class="cap-brand-name">Capstone</div>
          <div class="cap-brand-sub">llming-stage · sample 10</div>
        </div>
      </div>
      <nav class="cap-nav-items">
        ${items.map(([h, l, i]) => `
          <a data-stage-link href="${h}" class="cap-nav-item ${h === active ? 'active' : ''}">
            <q-icon name="${i}" size="18px"></q-icon><span>${l}</span>
          </a>`).join('')}
      </nav>
    </div>
    <style>
      .cap-nav { display: flex; align-items: center; gap: 32px;
        padding: 14px 28px; border-bottom: 1px solid rgba(128,128,128,.18);
        background: rgba(0,0,0,.02); }
      .body--dark .cap-nav { background: rgba(255,255,255,.02); }
      .cap-brand { display: flex; align-items: center; gap: 12px; }
      .cap-brand-mark { font-size: 26px;
        background: linear-gradient(135deg,#6366f1,#a855f7);
        -webkit-background-clip: text; background-clip: text; color: transparent;
        font-weight: 700; }
      .cap-brand-name { font-weight: 600; font-size: 15px; letter-spacing: -.01em; }
      .cap-brand-sub { font-size: 11px; opacity: .55; }
      .cap-nav-items { display: flex; gap: 4px; flex: 1; }
      .cap-nav-item { display: flex; align-items: center; gap: 6px;
        padding: 8px 14px; border-radius: 6px; text-decoration: none;
        color: inherit; opacity: .7; font-size: 13px;
        transition: background .12s, opacity .12s; }
      .cap-nav-item:hover { opacity: 1; background: rgba(128,128,128,.1); }
      .cap-nav-item.active { opacity: 1; background: rgba(99,102,241,.15); color: #6366f1; }
    </style>`;
}
window.__capNavBar = navBar;

window.__stageViews = window.__stageViews || {};
window.__stageViews.home = {
  async mount(target) {
    await ensureSocket();
    target.innerHTML = `
      ${navBar('/')}
      <div class="q-pa-lg" style="max-width:1100px;margin:0 auto">
        <div class="text-h3 q-mb-xs" style="font-weight:700;letter-spacing:-.02em">
          One session. Everything live.
        </div>
        <div class="text-subtitle1 text-grey q-mb-lg" style="max-width:640px">
          A capstone tying together streaming metrics, file upload, and chat —
          all reactive, all on the same WebSocket.
        </div>
        <div class="row q-col-gutter-md">
          ${card('/metric', 'insights', 'Live metrics',
                 'Plotly dashboard with streaming requests, latency percentiles, and traffic mix.',
                 '#6366f1')}
          ${card('/uploads', 'cloud_upload', 'File upload',
                 'HTTP POST streams bytes; progress and completion events flow back over the socket.',
                 '#10b981')}
          ${card('/chat', 'forum', 'Streaming chat',
                 'Server emits token deltas for each reply. The history lives on the session.',
                 '#a855f7')}
        </div>
        <div class="q-card q-pa-md q-mt-lg">
          <div class="text-overline text-grey">session</div>
          <div class="text-body2" style="font-family:ui-monospace,monospace">
            ${window.__appSessionId}
          </div>
        </div>
      </div>`;

    function card(href, icon, title, body, color) {
      return `
        <div class="col-12 col-md-4">
          <a data-stage-link href="${href}"
             class="q-card cap-home-card"
             style="text-decoration:none;color:inherit;display:flex;flex-direction:column;gap:10px;
                    padding:20px;height:100%;border-top:3px solid ${color}">
            <q-icon name="${icon}" size="32px" style="color:${color}"></q-icon>
            <div class="text-h6" style="font-weight:600">${title}</div>
            <div class="text-body2 text-grey">${body}</div>
            <div style="flex:1"></div>
            <div class="text-caption" style="color:${color};font-weight:500">
              Open →
            </div>
          </a>
        </div>`;
    }

    return { unmount() { target.innerHTML = ''; } };
  },
};
