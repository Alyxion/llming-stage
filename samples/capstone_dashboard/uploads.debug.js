export default function debug(ctx) {
  ctx.action("capstone.upload.fakeHistory", {
    label: "Seed upload history",
    scope: "capstone_dashboard",
    group: "Uploads",
  }, () => {
    const view = ctx.view;
    if (!view) return;
    view.progress = "debug upload ready";
    view.history = ["demo-report.csv", "debug-export.json", ...view.history].slice(0, 5);
  });
}
