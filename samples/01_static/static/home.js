window.__stageViews = window.__stageViews || {};
window.__stageViews.home = {
  mount(target) {
    target.innerHTML = `
      <div class="q-pa-xl text-center">
        <h1 class="text-h3">Static</h1>
        <p>No WebSocket. No session. Nothing dynamic on the server.</p>
      </div>`;
    return { unmount() { target.innerHTML = ''; } };
  },
};
