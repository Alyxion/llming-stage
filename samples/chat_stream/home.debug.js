export default function debug(ctx) {
  ctx.action("chat.sendPrompt", {
    label: "Send prompt",
    scope: "chat_stream",
    group: "Chat",
    params: {
      text: { type: "string", default: "Stream a short product launch update." },
    },
    presets: [
      { id: "launch", label: "Launch", params: { text: "Stream a short product launch update." } },
      { id: "support", label: "Support", params: { text: "Draft a concise customer support answer." } },
    ],
  }, async (params) => {
    const view = ctx.view;
    if (!view) return;
    view.text = params.text;
    await view.send();
  });
}
