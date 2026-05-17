export default function debug(ctx) {
  ctx.action("capstone.chat.ask", {
    label: "Send chat prompt",
    scope: "capstone_dashboard",
    group: "Chat",
    params: {
      text: { type: "string", default: "Summarize the dashboard." },
    },
    presets: [
      { id: "summary", label: "Summary", params: { text: "Summarize the dashboard." } },
      { id: "risk", label: "Risks", params: { text: "What should I inspect first?" } },
    ],
  }, async (params) => {
    const view = ctx.view;
    if (!view) return;
    view.text = params.text;
    await view.send();
  });
}
