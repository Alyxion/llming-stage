window.__stageViews = window.__stageViews || {};
window.__stageViews.reader = {
  async mount(target) {
    target.innerHTML = `
      <div class="q-pa-md" style="max-width:900px;margin:auto;display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div>
          <h1 class="text-h5">Source</h1>
          <textarea id="src" style="width:100%;height:420px;font-family:monospace;font-size:14px"></textarea>
          <div class="q-mt-sm" style="display:flex;gap:8px">
            <button id="render-math" class="r-btn">Render math</button>
            <button id="render-html" class="r-btn">Sanitise &amp; render</button>
          </div>
        </div>
        <div>
          <h1 class="text-h5">Output</h1>
          <div id="out" style="padding:12px;border:1px solid #ddd;border-radius:4px;background:#fafafa;min-height:440px"></div>
        </div>
      </div>
      <style>
        .r-btn { padding:6px 12px; background:#1976d2; color:#fff;
          border:0; border-radius:4px; cursor:pointer }
      </style>`;

    const src = document.getElementById('src');
    const out = document.getElementById('out');
    src.value = [
      'The quadratic formula:',
      '',
      '$$ x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a} $$',
      '',
      'Inline math: $e^{i\\pi} + 1 = 0$.',
      '',
      '<b>Bold HTML</b> and <script>alert("xss")</script> will be sanitised.',
    ].join('\n');

    document.getElementById('render-math').addEventListener('click', async () => {
      await window.__stage.load('katex');
      const parts = src.value.split(/(\$\$[^$]+\$\$|\$[^$]+\$)/);
      out.innerHTML = '';
      for (const part of parts) {
        if (part.startsWith('$$') && part.endsWith('$$')) {
          const div = document.createElement('div');
          katex.render(part.slice(2, -2), div, {displayMode: true, throwOnError: false});
          out.appendChild(div);
        } else if (part.startsWith('$') && part.endsWith('$') && part.length > 1) {
          const span = document.createElement('span');
          katex.render(part.slice(1, -1), span, {throwOnError: false});
          out.appendChild(span);
        } else {
          out.appendChild(document.createTextNode(part));
        }
      }
    });

    document.getElementById('render-html').addEventListener('click', async () => {
      await window.__stage.load('dompurify');
      out.innerHTML = DOMPurify.sanitize(src.value);
    });

    return { unmount() { target.innerHTML = ''; } };
  },
};
