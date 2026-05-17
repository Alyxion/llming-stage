export default function debug(ctx) {
  ctx.action("counter.set", {
    label: "Set counter",
    scope: "counter",
    group: "Server state",
    params: {
      value: { type: "number", default: 12 },
    },
    presets: [
      { id: "zero", label: "Zero", params: { value: 0 } },
      { id: "dozen", label: "Dozen", params: { value: 12 } },
    ],
  }, async (params) => {
    const view = ctx.view;
    if (!view) return;
    await ctx.stage.connect();
    await ctx.command("counter.reset");
    const target = Number(params.value || 0);
    if (target !== 0) await ctx.command("counter.inc", { by: target });
  });

  ctx.action("counter.bump", {
    label: "Bump counter",
    scope: "counter",
    group: "Server state",
    params: {
      by: { type: "number", default: 5 },
    },
  }, async (params) => {
    await ctx.stage.connect();
    await ctx.command("counter.inc", { by: Number(params.by || 1) });
  });
}
