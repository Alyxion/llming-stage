window.__stageViews = window.__stageViews || {};
window.__stageViews.reader = {
  async mount(target) {
    target.innerHTML = `
      <div class="q-pa-md" style="min-height:100%">
        <div style="max-width:1100px;margin:0 auto;display:flex;flex-direction:column;gap:16px">
          <div>
            <div class="text-h5">Math + sanitised HTML</div>
            <div class="text-caption text-grey">
              KaTeX and DOMPurify are not in the critical path — they load on first use.
            </div>
          </div>
          <div class="row q-col-gutter-md">
            <div class="col-12 col-md-6">
              <div class="q-card q-pa-md" style="height:100%">
                <div class="row items-center justify-between q-mb-sm">
                  <div class="text-subtitle2">Source</div>
                  <div class="row q-gutter-xs">
                    <button id="render-math" class="q-btn bg-primary text-white"
                            style="padding:6px 12px;border:0;border-radius:4px;cursor:pointer;font-size:12px">
                      Render math
                    </button>
                    <button id="render-html" class="q-btn bg-secondary text-white"
                            style="padding:6px 12px;border:0;border-radius:4px;cursor:pointer;font-size:12px">
                      Sanitise HTML
                    </button>
                  </div>
                </div>
                <textarea id="src" spellcheck="false"
                          style="width:100%;min-height:360px;font-family:ui-monospace,monospace;
                                 font-size:13px;padding:10px;border:1px solid rgba(128,128,128,.25);
                                 border-radius:4px;background:rgba(128,128,128,.04);
                                 color:inherit;resize:vertical"></textarea>
              </div>
            </div>
            <div class="col-12 col-md-6">
              <div class="q-card q-pa-md" style="height:100%">
                <div class="text-subtitle2 q-mb-sm">Output</div>
                <div id="out" style="min-height:360px;padding:12px;border-radius:4px;
                     background:rgba(128,128,128,.04);line-height:1.6"></div>
              </div>
            </div>
          </div>
        </div>
      </div>`;

    const src = target.querySelector('#src');
    const out = target.querySelector('#out');
    src.value = [
      'The quadratic formula:',
      '',
      '$$ x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a} $$',
      '',
      "Inline math: $e^{i\\pi} + 1 = 0$.",
      '',
      '<b>Bold HTML</b> and <script>alert("xss")</script> will be sanitised.',
    ].join('\n');

    target.querySelector('#render-math').addEventListener('click', async () => {
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

    target.querySelector('#render-html').addEventListener('click', async () => {
      await window.__stage.load('dompurify');
      out.innerHTML = DOMPurify.sanitize(src.value);
    });

    return { unmount() { target.innerHTML = ''; } };
  },
};
