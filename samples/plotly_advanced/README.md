# Advanced Plotly

Showcases the `Stage(app).view("/", "home.vue")` API with chart types
only available in the **`plotly/full`** bundle (4.8 MB) — 3D surface,
heatmap, candlestick, and a Sankey diagram. The basic Plotly bundle
(~1 MB, what sample 10 uses) doesn't include any of these.

The view calls `await __stage.load('plotly/full')` on mount, so the
heavy bundle only hits the wire when this sample is opened. Development
reload is handled by `Stage` and is content-hash based, so this sample
does not need manual static mounts or cache-busting query strings.

This sample intentionally uses Sankey instead of choropleth: Plotly's
default choropleth path can fetch topology JSON from `cdn.plot.ly`,
which violates llming-stage's no-external-network runtime guarantee.

## Run

```bash
poetry run python samples/plotly_advanced/main.py
open http://localhost:8765
```
