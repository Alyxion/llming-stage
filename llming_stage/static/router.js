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

  // ---- Deployment-base resolution (static shipping) -------------------
  // A statically-built bundle can be served from ANY mount point: the origin
  // root, a sub-path like '/app/', a CDN prefix. Each built index.html bakes
  // the route it represents as window.__stageRoute; we subtract that known
  // suffix from the document's actual path to learn the deployment base, so
  // client-side routing keeps matching wherever the bundle lands. With no
  // baked route (the live server, served at the origin root) the base is ''
  // and behavior is unchanged.
  function _routeDir(route) {
    if (!route || route === '/') return '/';
    return route.replace(/\/+$/, '') + '/';
  }
  function _computeBase() {
    const known = window.__stageRoute;
    if (typeof known !== 'string') return '';
    let cur = location.pathname.replace(/index\.html$/, '');
    if (cur.charAt(cur.length - 1) !== '/') cur += '/';
    const dir = _routeDir(known);
    if (cur.length >= dir.length && cur.slice(cur.length - dir.length) === dir) {
      return cur.slice(0, cur.length - dir.length); // '' (root) or e.g. '/app'
    }
    return '';
  }
  const base = _computeBase();

  // Map the document's real pathname to a base-relative ROUTE path: strip the
  // deployment base, a trailing 'index.html', and a trailing slash.
  function normalizePath(path) {
    let p = path;
    if (base && p.indexOf(base) === 0) p = p.slice(base.length);
    p = p.replace(/index\.html$/, '');
    if (p.charAt(0) !== '/') p = '/' + p;
    if (p.length > 1) p = p.replace(/\/+$/, '');
    return p || '/';
  }
  // Turn a route path back into a real URL under the deployment base.
  function withBase(path) {
    const rel = path.charAt(0) === '/' ? path : '/' + path;
    return (base + rel) || '/';
  }
  function currentPath() { return normalizePath(location.pathname); }

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
    if (window.__stage.debug && window.__stage.debug.enabled) {
      try {
        await window.__stage.debug.loadForView(route.view);
      } catch (e) {
        console.warn('[llming-stage] debug actions failed to load for ' + route.view, e);
      }
    }
    return true;
  }

  function register(pattern, view) {
    const compiled = compile(pattern);
    routes.push({ regex: compiled.regex, paramNames: compiled.paramNames, view });
  }

  function navigate(path, { replace = false } = {}) {
    const full = withBase(path);
    if (replace) history.replaceState(null, '', full);
    else history.pushState(null, '', full);
    return activate(normalizePath(full));
  }

  async function start() {
    mountTarget = document.getElementById('app-shell-view');
    window.addEventListener('popstate', () => activate(currentPath()));
    document.addEventListener('click', (ev) => {
      const a = ev.target.closest && ev.target.closest('a[data-stage-link]');
      if (!a) return;
      const href = a.getAttribute('href');
      if (!href || href.startsWith('http')) return;
      ev.preventDefault();
      navigate(href);
    });
    await activate(currentPath());
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
