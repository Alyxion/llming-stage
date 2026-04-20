# 07 — Three.js tornado

Full-screen particle tornado with custom GLSL shaders, orbit controls,
and six live-parameter sliders on a glass-morphism control panel.

Six sliders rebuild or live-update the shader uniforms:
particles, rotation speed, height, radius, glow, and turbulence.

## Run

```bash
poetry run python samples/07_3d_scene/main.py
open http://localhost:8080
```

Drag to orbit, right-click-drag to pan, scroll to zoom.
