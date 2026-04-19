window.__stageViews = window.__stageViews || {};
window.__stageViews.scene = {
  async mount(target) {
    target.innerHTML = `
      <div class="q-pa-md text-center">
        <h1 class="text-h4">Lazy-loaded Three.js</h1>
        <p class="text-caption">
          Three.js was not in the critical path. It loads on mount via
          <code>window.__stage.load('three')</code>.
        </p>
        <div id="canvas-holder" style="width:640px;height:480px;margin:24px auto;background:#111"></div>
      </div>`;

    await window.__stage.load('three');
    const THREE = await import(window.__stage.base + '/vendor/three.module.min.js');

    const holder = document.getElementById('canvas-holder');
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x111111);
    const camera = new THREE.PerspectiveCamera(60, 640 / 480, 0.1, 100);
    camera.position.z = 3;
    const renderer = new THREE.WebGLRenderer({antialias: true});
    renderer.setSize(640, 480);
    holder.appendChild(renderer.domElement);

    const geom = new THREE.BoxGeometry(1, 1, 1);
    const mat = new THREE.MeshStandardMaterial({color: 0x1976d2, metalness: 0.3, roughness: 0.4});
    const cube = new THREE.Mesh(geom, mat);
    scene.add(cube);
    const light = new THREE.DirectionalLight(0xffffff, 1.2);
    light.position.set(2, 2, 4);
    scene.add(light);
    scene.add(new THREE.AmbientLight(0x555555));

    let stop = false;
    const loop = () => {
      if (stop) return;
      cube.rotation.x += 0.01;
      cube.rotation.y += 0.013;
      renderer.render(scene, camera);
      requestAnimationFrame(loop);
    };
    loop();

    return {
      unmount() {
        stop = true;
        renderer.dispose();
        target.innerHTML = '';
      },
    };
  },
};
