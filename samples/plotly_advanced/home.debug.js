export default function debug(ctx) {
  ctx.action("plotly.relayout", {
    label: "Relayout Plotly charts",
    scope: "plotly_advanced",
    group: "Charts",
    params: {
      height: { type: "number", default: 320 },
    },
  }, async (params) => {
    if (!window.Plotly) return;
    for (const id of ["chart-surface", "chart-heat", "chart-candle", "chart-sankey"]) {
      const el = document.getElementById(id);
      if (el) await window.Plotly.relayout(el, { height: Number(params.height || 320) });
    }
  });
}
