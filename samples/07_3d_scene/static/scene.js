window.__stageViews = window.__stageViews || {};
window.__stageViews.scene = {
  async mount(target) {
    await window.__stage.load('three');
    await window.__stage.load('three/controls');
    const THREE = await import(window.__stage.base + '/vendor/three.module.min.js');
    const { OrbitControls } = await import(
      window.__stage.base + '/vendor/three-orbit-controls.module.js');

    target.innerHTML = `
      <div id="scene-wrap">
        <canvas id="scene-canvas"></canvas>
        <div id="scene-overlay">
          <div class="scene-title">
            <div class="scene-title-line">Three.js Tornado</div>
            <div class="scene-title-sub">drag · right-click pan · scroll zoom</div>
          </div>
          <div id="scene-controls">
            <div class="sc-header">
              <q-icon name="tune" size="18px" style="color:#fb923c"></q-icon>
              <span>Controls</span>
              <span class="sc-spacer"></span>
              <span class="sc-hint">drag to rotate · scroll to zoom</span>
            </div>
            <div class="sc-grid">
              <label><span>Particles</span>
                <input id="c-particles" type="range" min="2000" max="30000" step="500" value="15000">
                <output id="o-particles">15000</output></label>
              <label><span>Rotation</span>
                <input id="c-rotation" type="range" min="0.5" max="5.0" step="0.1" value="1.5">
                <output id="o-rotation">1.5</output></label>
              <label><span>Height</span>
                <input id="c-height" type="range" min="4" max="15" step="0.5" value="10">
                <output id="o-height">10</output></label>
              <label><span>Radius</span>
                <input id="c-radius" type="range" min="1" max="6" step="0.5" value="2.5">
                <output id="o-radius">2.5</output></label>
              <label><span>Glow</span>
                <input id="c-glow" type="range" min="0.2" max="2.5" step="0.1" value="1.2">
                <output id="o-glow">1.2</output></label>
              <label><span>Turbulence</span>
                <input id="c-wind" type="range" min="0" max="3" step="0.1" value="0.8">
                <output id="o-wind">0.8</output></label>
            </div>
            <div class="sc-footer">
              <button id="c-reset">Reset</button>
            </div>
          </div>
        </div>
      </div>
      <style>
        #scene-wrap { position: absolute; inset: 0; background: #000; overflow: hidden; }
        #scene-canvas { display: block; width: 100%; height: 100%; }
        #scene-overlay { position: absolute; inset: 0; pointer-events: none;
          color: #e9e6ff; font: 14px/1.4 -apple-system, system-ui, sans-serif; }
        .scene-title { position: absolute; top: 22px; left: 28px; }
        .scene-title-line { font-size: 24px; font-weight: 700; letter-spacing: -0.01em;
          color: #fff; text-shadow: 0 2px 20px rgba(255, 140, 60, .35); }
        .scene-title-sub { margin-top: 4px; opacity: .45; font-size: 11px;
          letter-spacing: .18em; text-transform: uppercase; color: #aaa; }
        #scene-controls { position: absolute; bottom: 24px; left: 50%;
          transform: translateX(-50%); pointer-events: auto; min-width: 560px;
          padding: 14px 18px 10px; border-radius: 12px;
          background: rgba(0, 0, 0, 0.55); border: 1px solid rgba(255, 255, 255, 0.12);
          backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
          box-shadow: 0 14px 50px rgba(0, 0, 0, 0.6); }
        .sc-header { display: flex; align-items: center; gap: 8px; padding: 0 2px 10px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.08); margin-bottom: 10px;
          font-weight: 500; }
        .sc-spacer { flex: 1; }
        .sc-hint { opacity: .55; font-size: 11px; }
        .sc-grid { display: grid; grid-template-columns: repeat(3, minmax(160px, 1fr));
          gap: 10px 20px; }
        .sc-grid label { display: grid; grid-template-columns: 78px 1fr 42px;
          align-items: center; gap: 10px; font-size: 11px; letter-spacing: .08em;
          text-transform: uppercase; opacity: .75; }
        .sc-grid input[type=range] { -webkit-appearance: none; appearance: none;
          width: 100%; height: 3px; border-radius: 2px; background: rgba(255,255,255,.15);
          outline: none; }
        .sc-grid input[type=range]::-webkit-slider-thumb {
          -webkit-appearance: none; appearance: none; width: 12px; height: 12px;
          border-radius: 50%; background: #fb923c;
          box-shadow: 0 0 8px rgba(251, 146, 60, .8); cursor: pointer; }
        .sc-grid input[type=range]::-moz-range-thumb { width: 12px; height: 12px;
          border: 0; border-radius: 50%; background: #fb923c;
          box-shadow: 0 0 8px rgba(251, 146, 60, .8); cursor: pointer; }
        .sc-grid output { font-variant-numeric: tabular-nums; text-align: right;
          font-size: 11px; opacity: .7; }
        .sc-footer { display: flex; justify-content: center; margin-top: 10px; }
        .sc-footer button { padding: 6px 18px; border: 1px solid rgba(251, 146, 60, .4);
          background: transparent; color: #fb923c; border-radius: 4px; cursor: pointer;
          font-size: 12px; letter-spacing: .1em; text-transform: uppercase;
          transition: background .1s; }
        .sc-footer button:hover { background: rgba(251, 146, 60, .1); }
      </style>`;

    const wrap = target.querySelector('#scene-wrap');
    const canvas = target.querySelector('#scene-canvas');

    const settings = {
      particleCount: 15000,
      rotationSpeed: 1.5,
      height: 10.0,
      radius: 2.5,
      colorIntensity: 1.2,
      windStrength: 0.8,
    };

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

    const bind = (id, key, parse = parseFloat) => {
      const el = target.querySelector('#c-' + id);
      const out = target.querySelector('#o-' + id);
      out.value = el.value;
      el.addEventListener('input', () => {
        const v = parse(el.value);
        settings[key] = v;
        out.value = el.value;
        if (key === 'particleCount') {
          buildTornado();
        } else if (particles) {
          const uniformKey = 'u' + key[0].toUpperCase() + key.slice(1);
          if (particles.material.uniforms[uniformKey]) {
            particles.material.uniforms[uniformKey].value = v;
          }
        }
      });
    };
    bind('particles', 'particleCount', (v) => parseInt(v, 10));
    bind('rotation',  'rotationSpeed');
    bind('height',    'height');
    bind('radius',    'radius');
    bind('glow',      'colorIntensity');
    bind('wind',      'windStrength');

    target.querySelector('#c-reset').addEventListener('click', () => {
      const defaults = { particles: 15000, rotation: 1.5, height: 10, radius: 2.5, glow: 1.2, wind: 0.8 };
      for (const [id, v] of Object.entries(defaults)) {
        const el = target.querySelector('#c-' + id);
        el.value = v;
        el.dispatchEvent(new Event('input'));
      }
      camera.position.set(0, 5, 15);
      controls.target.set(0, 4, 0);
      controls.update();
    });

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

    return {
      unmount() {
        running = false;
        ro.disconnect();
        controls.dispose();
        renderer.dispose();
        if (particles) { particles.geometry.dispose(); particles.material.dispose(); }
        ambientGeom.dispose();
        ambient.material.dispose();
        target.innerHTML = '';
      },
    };
  },
};
