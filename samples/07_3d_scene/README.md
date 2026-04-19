# 07 — 3D scene (lazy Three.js)

Shows how a view pulls in an expensive dependency on demand.
Three.js (~340 KB) is *not* in the critical path — it only loads
when this view mounts, via `window.__stage.load('three')`.

## What to notice

- `main.py` has no llming-com wiring at all. This sample is pure
  client-side — falls into the "pure static, no server reactivity"
  branch of the communication model.
- `scene.js` calls `__stage.load('three')` to register the library,
  then `await import(...)` to get the module namespace.
- `unmount()` stops the animation loop and disposes the renderer so
  navigating away cleans up properly.

## Run

```bash
poetry run python samples/07_3d_scene/main.py
open http://localhost:8080
```

Open devtools → Network → filter `three` — you'll see the request
fires only after the view mounts.

