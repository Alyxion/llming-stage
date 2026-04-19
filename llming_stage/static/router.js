// llming-stage SPA router.
//
// Minimal hash/history router. Each registered route loads a view module
// lazily via window.__stage.load(), then calls its `mount(target, params)`
// export with the mount target element. Previous view's `unmount()` is
// invoked before the next one mounts.
(function () {
  if (window.__stageRouter) return;

  const routes = []; // [{pattern: RegExp, paramNames: string[], view: string}]
  let mountTarget = null;
  let currentView = null;
  let currentUnmount = null;

  function compile(pattern) {
    const paramNames = [];
    const regexStr = '^' + pattern.replace(/\/:([^/]+)/g, (_, name) => {
      paramNames.push(name);
      return '/([^/]+)';
    }).replace(/\*$/, '.*') + '$';
    return { regex: new RegExp(regexStr), paramNames };
  }

  function match(path) {
    for (const route of routes) {
      const m = route.regex.exec(path);
      if (m) {
        const params = {};
        route.paramNames.forEach((n, i) => { params[n] = decodeURIComponent(m[i + 1]); });
        return { route, params };
      }
    }
    return null;
  }

  async function activate(path) {
    const hit = match(path);
    if (!hit) return false;
    const { route, params } = hit;
    if (currentUnmount) {
      try { currentUnmount(); } catch (_) { /* ignore */ }
      currentUnmount = null;
    }
    if (!mountTarget) {
      mountTarget = document.getElementById('app-shell-view');
    }
    mountTarget.innerHTML = '';
    await window.__stage.load(route.view);
    const viewApi = window.__stageViews && window.__stageViews[route.view];
    if (!viewApi || typeof viewApi.mount !== 'function') {
      throw new Error('llming-stage: view "' + route.view + '" did not register mount()');
    }
    currentView = route.view;
    const result = await viewApi.mount(mountTarget, params);
    currentUnmount = (result && typeof result.unmount === 'function') ? result.unmount : null;
    return true;
  }

  function register(pattern, view) {
    const compiled = compile(pattern);
    routes.push({ regex: compiled.regex, paramNames: compiled.paramNames, view });
  }

  function navigate(path, { replace = false } = {}) {
    if (replace) history.replaceState(null, '', path);
    else history.pushState(null, '', path);
    return activate(path);
  }

  async function start() {
    mountTarget = document.getElementById('app-shell-view');
    window.addEventListener('popstate', () => activate(location.pathname));
    document.addEventListener('click', (ev) => {
      const a = ev.target.closest && ev.target.closest('a[data-stage-link]');
      if (!a) return;
      const href = a.getAttribute('href');
      if (!href || href.startsWith('http')) return;
      ev.preventDefault();
      navigate(href);
    });
    await activate(location.pathname);
  }

  // View modules register themselves via this object:
  //   window.__stageViews = window.__stageViews || {};
  //   window.__stageViews.home = { mount(target, params) { ... } };
  window.__stageViews = window.__stageViews || {};

  window.__stageRouter = Object.freeze({
    register,
    navigate,
    start,
    get current() { return currentView; },
  });
})();
