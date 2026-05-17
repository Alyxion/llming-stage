export default function debug(ctx) {
  ctx.action("capstone.navigate", {
    label: "Open capstone route",
    scope: "capstone_dashboard",
    group: "Navigation",
    params: {
      route: { type: "string", default: "/metric", options: ["/", "/metric", "/uploads", "/chat"] },
    },
    presets: [
      { id: "metrics", label: "Metrics", params: { route: "/metric" } },
      { id: "chat", label: "Chat", params: { route: "/chat" } },
    ],
  }, (params) => ctx.router.navigate(params.route));
}
