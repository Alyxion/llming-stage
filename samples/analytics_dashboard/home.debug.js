export default function debug(ctx) {
  ctx.action("analytics.filters", {
    label: "Apply dashboard filters",
    description: "Sets common chart filters without clicking through the controls.",
    scope: "analytics_dashboard",
    group: "Dashboard",
    params: {
      region: { type: "string", default: "North", options: ["North", "South", "East", "West", "Central"] },
      product: { type: "string", default: "Laptops", options: ["Laptops", "Phones", "Tablets", "Watches", "Headphones"] },
      comparison: { type: "boolean", default: true },
    },
    presets: [
      { id: "north-laptops", label: "North · Laptops", params: { region: "North", product: "Laptops", comparison: true } },
      { id: "south-phones", label: "South · Phones", params: { region: "South", product: "Phones", comparison: false } },
      { id: "west-watches", label: "West · Watches", params: { region: "West", product: "Watches", comparison: true } },
    ],
  }, async (params) => {
    await ctx.stage.connect();
    await ctx.command("dashboard.set_filters", {
      regions: [params.region],
      products: [params.product],
      show_comparison: params.comparison,
    });
  });

  ctx.action("analytics.refresh", {
    label: "Refresh dataset",
    scope: "analytics_dashboard",
    group: "Dashboard",
  }, async () => {
    await ctx.stage.connect();
    await ctx.command("dashboard.set_filters", {});
  });

  ctx.flow("analytics.ready", {
    label: "Demo-ready dashboard",
    scope: "analytics_dashboard",
    group: "Flows",
    button: false,
    steps: [["analytics.filters", { region: "North", product: "Laptops", comparison: true }]],
  });
}
