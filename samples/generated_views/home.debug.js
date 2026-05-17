export default function debug(ctx) {
  ctx.action("generated.navigate", {
    label: "Open generated route",
    scope: "generated_views",
    group: "Navigation",
    params: {
      route: { type: "string", default: "/status", options: ["/", "/status"] },
    },
  }, (params) => ctx.router.navigate(params.route));
}
