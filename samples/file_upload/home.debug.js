export default function debug(ctx) {
  ctx.action("upload.seedHistory", {
    label: "Seed upload history",
    scope: "file_upload",
    group: "Uploads",
  }, () => {
    const view = ctx.view;
    if (!view) return;
    view.progress = "debug file ready";
    view.history = ["debug-import.csv", "sample-image.png", ...view.history].slice(0, 5);
  });
}
