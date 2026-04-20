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
| Plotly.js (basic) | 2.x | MIT | https://github.com/plotly/plotly.js | Charts and data visualization |
| KaTeX | 0.16.x | MIT | https://github.com/KaTeX/KaTeX | LaTeX math rendering |
| Mermaid | 11.x | MIT | https://github.com/mermaid-js/mermaid | Diagram rendering |
| DOMPurify | 3.x | Apache 2.0 / MPL 2.0 | https://github.com/cure53/DOMPurify | HTML sanitization |

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

## Quasar Locale Packs (`llming_stage/lang/`)

Bundled with Quasar — MIT licensed, sourced from the Quasar distribution
(https://github.com/quasarframework/quasar).
