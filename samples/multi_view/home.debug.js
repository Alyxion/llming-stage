export default function debug(ctx) {
  ctx.action("multi.navigate", {
    label: "Open route",
    scope: "multi_view",
    group: "Navigation",
    params: {
      route: { type: "string", default: "/timer", options: ["/", "/timer"] },
    },
  }, (params) => ctx.router.navigate(params.route));

  ctx.action("multi.openDrawer", {
    label: "Open drawer",
    scope: "multi_view",
    group: "Navigation",
  }, () => ctx.view?.openDrawer?.());
}
