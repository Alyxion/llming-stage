# Third-Party Resources

All bundled third-party resources and their licenses. This file MUST be updated
whenever a vendored file or asset is added, removed, or upgraded.

No AGPL, GPL, or LGPL resource is ever permitted in this repository.

## Vendor Libraries (`llming_stage/vendor/`)

| Resource | Version | License | Source | Purpose |
|----------|---------|---------|--------|---------|
| Vue.js | 3.x | MIT | https://github.com/vuejs/core | Reactive UI framework |
| Quasar Framework | 2.x | MIT | https://github.com/quasarframework/quasar | UI component library |
| Three.js | 0.184.0 | MIT | https://registry.npmjs.org/three/-/three-0.184.0.tgz (sha1 `5bca0a3851eea5345e4c205567b40dfa49b791b5`) | 3D rendering. Ships as two files — `three.module.min.js` re-exports from the co-located `three.core.min.js`; both are required. |
| Three.js OrbitControls | 0.184.0 | MIT | `examples/jsm/controls/OrbitControls.js` from the same Three.js tarball | Mouse / touch / wheel camera controls (vendored as `three-orbit-controls.module.js`). |
| Apache ECharts | 6.0.0 | Apache 2.0 | https://registry.npmjs.org/echarts/-/echarts-6.0.0.tgz (sha1 `2935aa7751c282d1abbbf7d719d397199a15b9e7`) | Chart library — line, bar, pie, gauge, radar, heatmap, scatter, candlestick. |
| Plotly.js (basic) | 2.x | MIT | https://github.com/plotly/plotly.js | Charts and data visualization (lighter bundle — scatter, bar, pie). |
| Plotly.js (full) | 3.5.0 | MIT | https://registry.npmjs.org/plotly.js-dist-min/-/plotly.js-dist-min-3.5.0.tgz (sha1 `d81d1c77dd93c927de2f84cdcd3f8697fb47583b`) | Full Plotly bundle — every chart type incl. heatmap, candlestick, choropleth. Loaded only when an app calls `__stage.load('plotly/full')`. |
| KaTeX | 0.16.45 | MIT | https://registry.npmjs.org/katex/-/katex-0.16.45.tgz (sha1 `ba60d39c54746b6b8d39ce0e7f6eace07143149c`) | LaTeX math rendering. Ships `katex.min.{js,css}` plus 20 woff2 font files under `fonts/katex/` (CSS rewritten to `url(../fonts/katex/…)` so every font ends up under the unified `/_stage/fonts/` URL tree). |
| Mermaid | 11.14.0 | MIT | https://registry.npmjs.org/mermaid/-/mermaid-11.14.0.tgz (sha1 `ce81b22bc10f3117ef7737406ef2d10ee1741769`) | Diagram rendering — UMD bundle (`mermaid.min.js`) so a single fetch covers every diagram type. |
| marked | 18.0.2 | MIT | https://registry.npmjs.org/marked/-/marked-18.0.2.tgz (sha1 `180cb158a2d2dc377821cfb088a10ca1b5630ef0`) | Markdown parser (UMD). |
| DOMPurify | 3.x | Apache 2.0 / MPL 2.0 | https://github.com/cure53/DOMPurify | HTML sanitization |
| xterm.js | 6.0.0 | MIT | https://registry.npmjs.org/@xterm/xterm/-/xterm-6.0.0.tgz (sha1 `93637b0f2ee3a70718b5746a27c9c506af16745b`) | Terminal emulator. |
| xterm.js fit addon | 0.11.0 | MIT | https://registry.npmjs.org/@xterm/addon-fit/-/addon-fit-0.11.0.tgz (sha1 `ba4778b69fcc9044a060c2176bbe077657d7b37e`) | Terminal autosize. |
| xterm.js web-links addon | 0.12.0 | MIT | https://registry.npmjs.org/@xterm/addon-web-links/-/addon-web-links-0.12.0.tgz (sha1 `bc34ae46f4c12012256d451ac2b9be791c0b6bfa`) | Click-through URL detection. |
| xterm.js webgl addon | 0.19.0 | MIT | https://registry.npmjs.org/@xterm/addon-webgl/-/addon-webgl-0.19.0.tgz (sha1 `02533c3f7c0af3ac9a44bbb095cbd47d48e90c25`) | GPU-accelerated terminal renderer. |
| Drawflow | 0.0.60 | MIT | https://registry.npmjs.org/drawflow/-/drawflow-0.0.60.tgz (sha1 `313eadb43190a04ebba16d2cb49d1c9516030a15`) | Visual node-graph editor. |
| CodeMirror 5 | 5.65.21 | MIT | https://registry.npmjs.org/codemirror/-/codemirror-5.65.21.tgz (sha1 `cacf320606c5450ad3b3da34bb9c666afec21068`) | In-browser code editor. Vendored files: `codemirror.{js,css}`, `codemirror-mode-javascript.js`, `codemirror-addon-matchbrackets.js`, `codemirror-addon-closebrackets.js`. |

## Fonts (`llming_stage/fonts/`)

| Resource | Version | License | Source | Purpose |
|----------|---------|---------|--------|---------|
| Roboto | 3.x | Apache 2.0 | https://github.com/googlefonts/roboto | Default UI font |
| Material Icons | 4.x | Apache 2.0 | https://github.com/google/material-design-icons | UI icons (filled, outlined, round, sharp) |
| Material Symbols | 1.x | Apache 2.0 | https://github.com/google/material-design-icons | UI icons (outlined, rounded, sharp) |

## Icon & Emoji Sets (`llming_stage/assets/*.zip`)

| Resource | Version | License | Source | Purpose |
|----------|---------|---------|--------|---------|
| Phosphor Icons | 2.x | MIT | https://github.com/phosphor-icons/core | UI icons (6 weights: bold, duotone, fill, light, regular, thin) |
| Noto Emoji | 15.x | SIL OFL 1.1 / Apache 2.0 | https://github.com/googlefonts/noto-emoji | Emoji rendering |
| Tabler Icons | 3.41.1 | MIT | https://registry.npmjs.org/@tabler/icons/-/icons-3.41.1.tgz (sha1 `dff9c77af287c73c2fcab4074cfa9f2069f9b7ee`) | UI icons (~6 000 SVGs, outline + filled). Served via `tabler-icons.zip` at `/_stage/tabler/<style>/<name>.svg`. |

## Quasar Locale Packs (`llming_stage/lang/`)

Bundled with Quasar — MIT licensed, sourced from the Quasar distribution
(https://github.com/quasarframework/quasar).
