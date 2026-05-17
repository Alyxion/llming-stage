export default function debug(ctx) {
  ctx.action("three.scene", {
    label: "Tune scene",
    description: "Changes only stable uniforms and camera, avoiding particle rebuild stutter.",
    scope: "three_scene",
    group: "Scene",
    params: {
      glow: { type: "number", default: 1.8 },
      speed: { type: "number", default: 2.2 },
    },
    presets: [
      { id: "calm", label: "Calm", params: { glow: 1.1, speed: 1.0 } },
      { id: "bright", label: "Bright", params: { glow: 1.8, speed: 2.2 } },
    ],
  }, async (params) => {
    const view = ctx.view;
    if (!view) return;
    view.settings.colorIntensity = Number(params.glow || 1.2);
    view.settings.rotationSpeed = Number(params.speed || 1.5);
    await view.$nextTick();
    view.applySetting("colorIntensity");
    view.applySetting("rotationSpeed");
    view.sceneApi?.resetCamera?.();
  });
}
