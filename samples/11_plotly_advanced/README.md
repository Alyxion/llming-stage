# 11 — Advanced Plotly

Showcases the chart types only available in the **`plotly/full`**
bundle (4.8 MB) — 3D surface, heatmap, candlestick, and a US-states
choropleth. The basic Plotly bundle (~1 MB, what sample 10 uses)
doesn't include any of these.

The view calls `await __stage.load('plotly/full')` on mount, so the
heavy bundle only hits the wire when this sample is opened.

## Run

```bash
poetry run python samples/11_plotly_advanced/main.py
open http://localhost:8080
```
