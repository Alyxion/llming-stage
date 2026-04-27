<template>
  <main ref="wrap" class="absolute inset-0 overflow-hidden bg-black">
    <canvas id="scene-canvas" ref="canvas" class="block h-full w-full"></canvas>
    <section class="pointer-events-none absolute inset-0 text-slate-100">
      <header class="absolute left-7 top-6">
        <h1 class="scene-title-line text-2xl font-bold tracking-tight text-white">Three.js Tornado</h1>
        <p class="mt-1 text-xs uppercase tracking-[0.18em] text-white/45">drag · right-click pan · scroll zoom</p>
      </header>

      <div id="scene-controls" class="pointer-events-auto absolute bottom-6 left-1/2 w-[min(720px,calc(100vw-2rem))] -translate-x-1/2 rounded-2xl border border-white/10 bg-black/60 p-4 shadow-2xl shadow-black/60 backdrop-blur-xl">
        <div class="mb-3 flex items-center gap-2 border-b border-white/10 pb-3 font-medium">
          <span class="font-extrabold text-orange-400">CTRL</span>
          <span>Controls</span>
          <span class="flex-1"></span>
          <span class="hidden text-xs text-white/55 sm:inline">drag to rotate · scroll to zoom</span>
        </div>
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <label v-for="control in controls" :key="control.id" class="grid grid-cols-[80px_1fr_48px] items-center gap-3 text-xs uppercase tracking-wider text-white/75">
            <span>{{ control.label }}</span>
            <input
              :id="'c-' + control.id"
              v-model.number="settings[control.key]"
              class="accent-orange-400"
              type="range"
              :min="control.min"
              :max="control.max"
              :step="control.step"
              @input="applySetting(control.key)"
            >
            <output :id="'o-' + control.id" class="text-right tabular-nums text-white/70">{{ settings[control.key] }}</output>
          </label>
        </div>
        <div class="mt-4 flex justify-center">
          <button id="c-reset" type="button" class="rounded-lg border border-orange-400/40 px-5 py-2 text-xs font-bold uppercase tracking-widest text-orange-400 hover:bg-orange-400/10" @click="resetScene">
            Reset
          </button>
        </div>
      </div>
    </section>
  </main>
</template>

<script>
export default {
  data() {
    return {
      cleanup: null,
      controls: [
        { id: 'particles', label: 'Particles', key: 'particleCount', min: 2000, max: 30000, step: 500 },
        { id: 'rotation', label: 'Rotation', key: 'rotationSpeed', min: 0.5, max: 5.0, step: 0.1 },
        { id: 'height', label: 'Height', key: 'height', min: 4, max: 15, step: 0.5 },
        { id: 'radius', label: 'Radius', key: 'radius', min: 1, max: 6, step: 0.5 },
        { id: 'glow', label: 'Glow', key: 'colorIntensity', min: 0.2, max: 2.5, step: 0.1 },
        { id: 'wind', label: 'Turbulence', key: 'windStrength', min: 0, max: 3, step: 0.1 },
      ],
      settings: {
        particleCount: 15000,
        rotationSpeed: 1.5,
        height: 10.0,
        radius: 2.5,
        colorIntensity: 1.2,
        windStrength: 0.8,
      },
      sceneApi: null,
    };
  },
  async mounted() {
    await window.__stage.load('three');
    await window.__stage.load('three/controls');
    const THREE = await import(window.__stage.base + '/vendor/three.module.min.js');
    const { OrbitControls } = await import(
      window.__stage.base + '/vendor/three-orbit-controls.module.js');

    const wrap = this.$refs.wrap;
    const canvas = this.$refs.canvas;
    const settings = this.settings;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000000);
    scene.fog = new THREE.FogExp2(0x000000, 0.02);

    const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 1000);
    camera.position.set(0, 5, 15);
    camera.lookAt(0, 4, 0);

    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.target.set(0, 4, 0);
    controls.update();

    const ambientCount = 500;
    const ambientGeom = new THREE.BufferGeometry();
    const ambientPos = new Float32Array(ambientCount * 3);
    for (let i = 0; i < ambientCount; i++) {
      ambientPos[i * 3] = (Math.random() - 0.5) * 40;
      ambientPos[i * 3 + 1] = Math.random() * 20;
      ambientPos[i * 3 + 2] = (Math.random() - 0.5) * 40;
    }
    ambientGeom.setAttribute('position', new THREE.BufferAttribute(ambientPos, 3));
    const ambient = new THREE.Points(ambientGeom,
      new THREE.PointsMaterial({ color: 0xff6600, size: 0.05, transparent: true, opacity: 0.5 }));
    scene.add(ambient);

    let particles = null;
    function buildTornado() {
      if (particles) {
        scene.remove(particles);
        particles.geometry.dispose();
        particles.material.dispose();
      }
      const count = settings.particleCount;
      const geom = new THREE.BufferGeometry();
      const positions = new Float32Array(count * 3);
      const colors    = new Float32Array(count * 3);
      const sizes     = new Float32Array(count);
      const randoms   = new Float32Array(count * 4);
      for (let i = 0; i < count; i++) {
        const t = Math.pow(Math.random(), 0.7);
        const angle = Math.random() * Math.PI * 2;
        const radiusAtHeight = settings.radius * (0.1 + t * 0.9);
        const thickness = 0.3 + Math.random() * 0.4;
        const r = radiusAtHeight * thickness;
        positions[i * 3]     = Math.cos(angle) * r;
        positions[i * 3 + 1] = t * settings.height;
        positions[i * 3 + 2] = Math.sin(angle) * r;
        colors[i * 3]     = 1.0;
        colors[i * 3 + 1] = 0.2 + t * 0.6;
        colors[i * 3 + 2] = t * t * 0.4;
        sizes[i] = 0.3 + Math.random() * 0.5 + t * 0.5;
        randoms[i * 4]     = Math.random();
        randoms[i * 4 + 1] = Math.random();
        randoms[i * 4 + 2] = Math.random();
        randoms[i * 4 + 3] = Math.random();
      }
      geom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      geom.setAttribute('color',    new THREE.BufferAttribute(colors, 3));
      geom.setAttribute('size',     new THREE.BufferAttribute(sizes, 1));
      geom.setAttribute('aRandom',  new THREE.BufferAttribute(randoms, 4));

      const mat = new THREE.ShaderMaterial({
        uniforms: {
          uTime:           { value: 0 },
          uRotationSpeed:  { value: settings.rotationSpeed },
          uHeight:         { value: settings.height },
          uRadius:         { value: settings.radius },
          uColorIntensity: { value: settings.colorIntensity },
          uWindStrength:   { value: settings.windStrength },
          uPixelRatio:     { value: Math.min(window.devicePixelRatio, 2) },
        },
        vertexShader: `
          attribute float size;
          attribute vec4 aRandom;
          uniform float uTime;
          uniform float uRotationSpeed;
          uniform float uHeight;
          uniform float uRadius;
          uniform float uWindStrength;
          uniform float uPixelRatio;
          varying vec3 vColor;
          varying float vAlpha;
          void main() {
            vColor = color;
            vec3 pos = position;
            float heightFactor = pos.y / uHeight;
            float angle = atan(pos.z, pos.x);
            float rotationOffset = uTime * uRotationSpeed * (1.0 + heightFactor * 0.5);
            rotationOffset += aRandom.x * 6.28;
            float turbulence = sin(uTime * 2.0 + aRandom.y * 10.0) * uWindStrength * 0.3;
            turbulence += cos(uTime * 1.5 + aRandom.z * 8.0) * uWindStrength * 0.2;
            float funnelRadius = uRadius * (0.2 + heightFactor * 0.8);
            funnelRadius += turbulence * heightFactor;
            float newAngle = angle + rotationOffset;
            pos.x = cos(newAngle) * funnelRadius;
            pos.z = sin(newAngle) * funnelRadius;
            pos.y = mod(pos.y + uTime * 0.5 * (1.0 + aRandom.w), uHeight);
            pos.x += sin(uTime * 3.0 + aRandom.x * 20.0) * 0.1 * uWindStrength;
            pos.z += cos(uTime * 2.5 + aRandom.y * 15.0) * 0.1 * uWindStrength;
            vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
            gl_Position = projectionMatrix * mvPosition;
            gl_PointSize = size * 50.0 * uPixelRatio / -mvPosition.z;
            gl_PointSize = clamp(gl_PointSize, 2.0, 40.0);
            vAlpha = 0.6 + heightFactor * 0.4;
            vAlpha *= smoothstep(0.0, 0.05, heightFactor);
            vAlpha *= smoothstep(1.0, 0.95, heightFactor);
          }`,
        fragmentShader: `
          varying vec3 vColor;
          varying float vAlpha;
          uniform float uColorIntensity;
          void main() {
            vec2 c = gl_PointCoord - vec2(0.5);
            float dist = length(c);
            if (dist > 0.5) discard;
            float alpha = 1.0 - smoothstep(0.0, 0.5, dist);
            alpha = pow(alpha, 1.5);
            alpha *= vAlpha;
            vec3 col = vColor * uColorIntensity * 1.5;
            gl_FragColor = vec4(col, alpha);
          }`,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        vertexColors: true,
      });

      particles = new THREE.Points(geom, mat);
      scene.add(particles);
    }
    buildTornado();

    this.sceneApi = {
      apply: (key) => {
        const v = settings[key];
        if (key === 'particleCount') {
          buildTornado();
        } else if (particles) {
          const uniformKey = 'u' + key[0].toUpperCase() + key.slice(1);
          if (particles.material.uniforms[uniformKey]) {
            particles.material.uniforms[uniformKey].value = v;
          }
        }
      },
      resetCamera: () => {
      camera.position.set(0, 5, 15);
      controls.target.set(0, 4, 0);
      controls.update();
      },
    };

    const resize = () => {
      const w = wrap.clientWidth, h = wrap.clientHeight;
      renderer.setSize(w, h, false);
      camera.aspect = w / Math.max(1, h);
      camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);

    let running = true;
    const clock = new THREE.Clock();
    const tick = () => {
      if (!running) return;
      requestAnimationFrame(tick);
      const elapsed = clock.getElapsedTime();
      if (particles) particles.material.uniforms.uTime.value = elapsed;
      ambient.rotation.y = elapsed * 0.1;
      controls.update();
      renderer.render(scene, camera);
    };
    tick();

    this.cleanup = () => {
        running = false;
        ro.disconnect();
        controls.dispose();
        renderer.dispose();
        if (particles) { particles.geometry.dispose(); particles.material.dispose(); }
        ambientGeom.dispose();
        ambient.material.dispose();
    };
  },
  beforeUnmount() {
    this.cleanup?.();
  },
  methods: {
    applySetting(key) {
      this.sceneApi?.apply(key);
    },
    resetScene() {
      Object.assign(this.settings, {
        particleCount: 15000,
        rotationSpeed: 1.5,
        height: 10,
        radius: 2.5,
        colorIntensity: 1.2,
        windStrength: 0.8,
      });
      this.$nextTick(() => {
        for (const key of Object.keys(this.settings)) this.applySetting(key);
        this.sceneApi?.resetCamera();
      });
    },
  },
};
</script>
