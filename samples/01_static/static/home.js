window.__stageViews = window.__stageViews || {};
window.__stageViews.home = {
  mount(target) {
    target.innerHTML = `
      <div class="column items-center justify-center" style="min-height:100%;padding:48px 24px;gap:24px">
        <div class="text-h2" style="font-weight:700;letter-spacing:-0.02em;
             background:linear-gradient(135deg,#6366f1,#a855f7);
             -webkit-background-clip:text;background-clip:text;color:transparent">
          Static shell
        </div>
        <div class="text-subtitle1 text-grey" style="max-width:520px;text-align:center">
          One HTML document, served as a fixed string. No session, no WebSocket —
          everything on this page could be hosted from a CDN bucket.
        </div>
        <div class="row q-gutter-sm">
          <div class="q-chip bg-primary text-white">
            <span class="q-chip__content">Vue + Quasar</span>
          </div>
          <div class="q-chip bg-secondary text-white">
            <span class="q-chip__content">No server reactivity</span>
          </div>
          <div class="q-chip bg-accent text-white">
            <span class="q-chip__content">Static deployable</span>
          </div>
        </div>
      </div>`;
    return { unmount() { target.innerHTML = ''; } };
  },
};
