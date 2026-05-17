export default function debug(ctx) {
  ctx.action("capstone.metric.refresh", {
    label: "Redraw metric chart",
    scope: "capstone_dashboard",
    group: "Metrics",
  }, () => {
    ctx.view?.draw?.();
  });

  ctx.action("capstone.metric.navigate", {
    label: "Go to upload/chat",
    scope: "capstone_dashboard",
    group: "Navigation",
    params: {
      route: { type: "string", default: "/uploads", options: ["/", "/uploads", "/chat"] },
    },
  }, (params) => ctx.router.navigate(params.route));
}
