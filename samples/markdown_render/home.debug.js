export default function debug(ctx) {
  ctx.action("markdown.seed", {
    label: "Seed markdown",
    scope: "markdown_render",
    group: "Editor",
    params: {
      mode: { type: "string", default: "html", options: ["html", "math"] },
    },
    presets: [
      { id: "html", label: "HTML", params: { mode: "html" } },
      { id: "math", label: "Math", params: { mode: "math" } },
    ],
  }, async (params) => {
    const view = ctx.view;
    if (!view) return;
    view.source = params.mode === "math"
      ? "# Debug formula\n\n$$E = mc^2$$\n\nInline $a^2+b^2=c^2$."
      : "# Debug brief\n\n- Local assets only\n- Sanitized rendering\n- Fast reload setup";
    if (params.mode === "math") await view.renderMath();
    else await view.renderHtml();
  });
}
