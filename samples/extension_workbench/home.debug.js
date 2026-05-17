export default function debug(ctx) {
  ctx.action("workbench.rebuild", {
    label: "Rebuild loaded widgets",
    scope: "extension_workbench",
    group: "Extensions",
  }, async () => {
    const view = ctx.view;
    if (!view) return;
    await Promise.all([
      view.renderMarkdown(),
      view.renderMermaid(),
    ]);
    view.editor?.setValue?.("// debug action updated the editor\n" + view.code);
    view.terminal?.writeln?.("debug action: terminal is live");
  });
}
