export default function debug(ctx) {
  ctx.action("generated.status", {
    label: "Set status",
    scope: "generated_views",
    group: "Status",
    params: {
      status: { type: "string", default: "debug-ready" },
    },
  }, (params) => {
    if (ctx.view) ctx.view.status = params.status;
  });
}
