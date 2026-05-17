export default function debug(ctx) {
  ctx.action("basic.seedForm", {
    label: "Seed form",
    description: "Fills the form, toggles flags, and selects a tab.",
    scope: "basic_components",
    group: "Forms",
    params: {
      name: { type: "string", default: "Ada Lovelace" },
      segment: { type: "string", default: "Enterprise", options: ["Startup", "Mid-market", "Enterprise"] },
      confidence: { type: "number", default: 91 },
      tab: { type: "string", default: "tree", options: ["table", "tree"] },
    },
    presets: [
      { id: "enterprise", label: "Enterprise", params: { name: "Ada Lovelace", segment: "Enterprise", confidence: 91, tab: "tree" } },
      { id: "midmarket", label: "Mid-market", params: { name: "Grace Hopper", segment: "Mid-market", confidence: 76, tab: "table" } },
    ],
  }, (params) => {
    const view = ctx.view;
    if (!view) return;
    view.name = params.name;
    view.segment = params.segment;
    view.approved = true;
    view.urgent = true;
    view.confidence = params.confidence;
    view.tab = params.tab;
  });

  ctx.action("basic.openDialog", {
    label: "Open dialog",
    scope: "basic_components",
    group: "Forms",
  }, () => {
    if (ctx.view) ctx.view.dialog = true;
  });
}
