export default function debug(ctx) {
  ctx.action("timer.control", {
    label: "Control timer",
    scope: "multi_view",
    group: "Timer",
    params: {
      command: { type: "string", default: "start", options: ["start", "cancel"] },
    },
    presets: [
      { id: "start", label: "Start", params: { command: "start" } },
      { id: "cancel", label: "Cancel", params: { command: "cancel" } },
    ],
  }, (params) => {
    const view = ctx.view;
    if (!view) return;
    await ctx.stage.connect();
    if (params.command === "cancel") await view.cancel();
    else await view.start();
  });
}
