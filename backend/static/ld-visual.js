/* =========================================================================
   LOHA DRISHTI - VISUAL LAYER
     Vessel x Port hologram   a procedurally built ship, scaled to the class's
                              real LOA, beam and draft, turning on a projector
                              above the chosen berth: waterline, seabed at the
                              berth's usable depth, quay at its LOA limit and
                              walls at its beam limit. Fit colours come from the
                              engine's own checks (/api/planning/constraints).
     Port Profiles            seabed cross-section + gauge cards
     Vessel Fit               to-scale silhouettes + engine-checked grid
     Execution Brief          proportional voyage timeline
   Draws only; every number is read from the API or the synced reference data.
   ========================================================================= */
(function(){
  'use strict';

  const $ = id => document.getElementById(id);
  const esc = s => escapeHtml(String(s == null ? '' : s));
  const UKC = 0.6;
  const ORIGIN_NAME = {australia:'Australia', indonesia:'Indonesia', south_africa:'South Africa', usa:'USA'};
  const HATCHES = {handysize:5, supramax:5, panamax:7, capesize:9};
  const GEARED = {handysize:true, supramax:true};
  const TONE = {ok:'#38E1FF', warn:'#FFB547', fail:'#FF4D6A'};
  const CLASS_TINT = {handysize:'var(--ld-pos)', supramax:'var(--ld-accent)', panamax:'var(--ld-warn)', capesize:'var(--ld-crit)'};
  const ICON = {
    anchor: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="5" r="2"/><path d="M12 7v14M5 13a7 7 0 0014 0M8 11h8"/></svg>',
    ship: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 15l2 5h14l2-5z"/><path d="M6 15V9h8v6M9 9V5h3"/></svg>',
    plant: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 21V11l5 3V11l5 3V7l8 4v10z"/></svg>',
  };
  const reduced = () => window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  function cargo(){
    const i = (typeof activeInputs === 'object' && activeInputs) || {};
    let origin = ORIGIN_NAME[i.origin] || null;
    if(!origin && typeof activeResult === 'object' && activeResult && activeResult.winner){
      origin = ORIGIN_NAME[activeResult.winner.originKey] || null;
    }
    return {cargo_type: i.cargoType || 'coking_coal', origin: origin || 'Australia', parcel: i.qty || 80000};
  }
  const portByCode = code => Object.keys(PORTS).find(k => PORTS[k].code === code);
  const statusOf = s => s === 'pass' ? 'ok' : (s === 'fail' ? 'fail' : 'warn');

  /* ------------------------------------------------ engine fit (cached) */
  const FIT = {key:null, data:null, pending:null};
  function loadFit(){
    const c = cargo();
    const key = [c.cargo_type, c.origin, c.parcel].join('|');
    if(FIT.key === key && FIT.data) return Promise.resolve(FIT.data);
    if(FIT.key === key && FIT.pending) return FIT.pending;
    FIT.key = key;
    FIT.pending = api('/api/planning/constraints', {method:'POST', body: JSON.stringify(
      {cargo_type: c.cargo_type, origin: c.origin, parcel_size: c.parcel})})
      .then(d => { FIT.data = d; try { localStorage.setItem('ld-fit', JSON.stringify(d)); } catch(e){} return d; })
      .catch(err => { try { const d = JSON.parse(localStorage.getItem('ld-fit') || 'null'); if(d){ FIT.data = d; return d; } } catch(e){} throw err; });
    return FIT.pending;
  }
  function pairing(data, clsKey, portKey){
    const row = data && data.vessels.find(v => v.vessel_class.toLowerCase() === clsKey);
    const berth = row && row.berths.find(b => b.port_code === PORTS[portKey].code);
    return {row, berth};
  }
  function verdict(row, berth){
    if(!row || !berth) return 'fail';
    if(!row.load_port.feasible || !berth.feasible) return 'fail';
    return (berth.lightering || row.load_port.part_loaded) ? 'warn' : 'ok';
  }

  /* =================================================== HOLOGRAM (THREE) */
  const H = {THREE:null, loading:null, renderer:null, scene:null, camera:null, world:null, rings:null,
             mats:[], labels:[], raf:0, yaw:0.7, pitch:0.36, zoom:1, drag:null, sel:{cls:null, port:null},
             spec:null, clock:0, last:0, failed:false, mounted:false};

  function loadThree(){
    if(H.THREE) return Promise.resolve(H.THREE);
    H.loading = H.loading || import('https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js')
      .then(m => (H.THREE = m));
    return H.loading;
  }

  function holoMaterial(color, opacity){
    const T = H.THREE;
    const m = new T.ShaderMaterial({
      uniforms: {uColor:{value:new T.Color(color)}, uTime:{value:0}, uOpacity:{value:opacity}, uScan:{value:0}},
      vertexShader: `varying vec3 vN; varying vec3 vW; varying vec3 vV;
        void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz;
          vN = normalize(mat3(modelMatrix) * normal); vV = normalize(cameraPosition - w.xyz);
          gl_Position = projectionMatrix * viewMatrix * w; }`,
      fragmentShader: `uniform vec3 uColor; uniform float uTime; uniform float uOpacity; uniform float uScan;
        varying vec3 vN; varying vec3 vW; varying vec3 vV;
        void main(){
          float fres = pow(1.0 - abs(dot(normalize(vN), vV)), 2.2);
          float lines = 0.62 + 0.38 * sin(vW.y * 26.0 - uTime * 5.0);
          float sweep = exp(-pow((vW.y - uScan) * 5.0, 2.0));
          float flicker = 0.93 + 0.07 * sin(uTime * 37.0);
          float a = (0.10 + fres * 0.9) * lines * flicker * uOpacity + sweep * 0.35 * uOpacity;
          gl_FragColor = vec4(uColor * (0.55 + fres * 1.5 + sweep), a);
        }`,
      transparent: true, blending: T.AdditiveBlending, depthWrite: false, side: T.DoubleSide
    });
    H.mats.push(m);
    return m;
  }

  function gridMaterial(color, opacity, cell, radius){
    const T = H.THREE;
    const m = new T.ShaderMaterial({
      uniforms: {uColor:{value:new T.Color(color)}, uOpacity:{value:opacity}, uCell:{value:cell}, uR:{value:radius}, uTime:{value:0}, uScan:{value:0}},
      vertexShader: `varying vec2 vL; void main(){ vL = position.xz; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `uniform vec3 uColor; uniform float uOpacity; uniform float uCell; uniform float uR; uniform float uTime;
        varying vec2 vL;
        void main(){
          vec2 c = vL / uCell;
          vec2 g = abs(fract(c - 0.5) - 0.5) / fwidth(c);
          float line = 1.0 - min(min(g.x, g.y), 1.0);
          float fade = 1.0 - smoothstep(uR * 0.45, uR, length(vL));
          float pulse = 0.85 + 0.15 * sin(uTime * 1.7);
          gl_FragColor = vec4(uColor, (0.07 + line * 0.55) * fade * uOpacity * pulse);
        }`,
      transparent: true, blending: T.AdditiveBlending, depthWrite: false, side: T.DoubleSide
    });
    H.mats.push(m);
    return m;
  }

  function addHolo(parent, geometry, color, opacity, edgeOpacity){
    const T = H.THREE;
    const mesh = new T.Mesh(geometry, holoMaterial(color, opacity));
    const edges = new T.LineSegments(new T.EdgesGeometry(geometry, 25),
      new T.LineBasicMaterial({color, transparent:true, opacity: edgeOpacity == null ? 0.85 : edgeOpacity,
                               blending: T.AdditiveBlending, depthWrite:false}));
    mesh.add(edges);
    parent.add(mesh);
    return mesh;
  }

  /* Hull outline in plan: square stern with rounded corners, parallel
     midbody, bow tapering over the last 16% of the length. */
  function hullGeometry(L, B, D){
    const T = H.THREE, s = new T.Shape();
    const sx = -L / 2, bow = L / 2 - L * 0.16, r = B * 0.16;
    s.moveTo(sx + r, -B / 2);
    s.lineTo(bow, -B / 2);
    s.bezierCurveTo(bow + L * 0.1, -B / 2, L / 2, -B * 0.2, L / 2, 0);
    s.bezierCurveTo(L / 2, B * 0.2, bow + L * 0.1, B / 2, bow, B / 2);
    s.lineTo(sx + r, B / 2);
    s.quadraticCurveTo(sx, B / 2, sx, B / 2 - r);
    s.lineTo(sx, -B / 2 + r);
    s.quadraticCurveTo(sx, -B / 2, sx + r, -B / 2);
    const g = new T.ExtrudeGeometry(s, {depth: D, bevelEnabled: false, curveSegments: 18});
    g.rotateX(-Math.PI / 2);          // extrusion becomes height: keel y=0, deck y=D
    return g;
  }

  function buildShip(root, spec, color){
    const T = H.THREE;
    const {L, B, D, key} = spec;
    const ship = new T.Group();
    addHolo(ship, hullGeometry(L, B, D), color, 0.85, 1);

    // Superstructure at the stern: four tiers, bridge wings, funnel.
    const hx = -L / 2 + L * 0.075, tierH = D * 0.2;
    for(let i = 0; i < 4; i++){
      const w = B * (0.78 - i * 0.05), len = L * (0.085 - i * 0.006);
      const g = new T.BoxGeometry(len, tierH, w);
      g.translate(hx, D + tierH * (i + 0.5), 0);
      addHolo(ship, g, color, 0.5);
    }
    const wing = new T.BoxGeometry(L * 0.035, tierH * 0.18, B * 1.02);
    wing.translate(hx + L * 0.02, D + tierH * 3.9, 0);
    addHolo(ship, wing, color, 0.6);
    const funnel = new T.BoxGeometry(L * 0.03, tierH * 1.6, B * 0.2);
    funnel.translate(-L / 2 + L * 0.03, D + tierH * 4.3, 0);
    addHolo(ship, funnel, color, 0.6);

    // Hatch covers along the cargo block.
    const n = HATCHES[key] || 6, x0 = -L / 2 + L * 0.15, x1 = L / 2 - L * 0.12;
    const pitch = (x1 - x0) / n;
    for(let i = 0; i < n; i++){
      const g = new T.BoxGeometry(pitch * 0.7, D * 0.1, B * 0.62);
      g.translate(x0 + pitch * (i + 0.5), D + D * 0.05, 0);
      addHolo(ship, g, color, 0.45);
      // Geared classes carry deck cranes between the holds.
      if(GEARED[key] && i > 0 && i < n){
        const px = x0 + pitch * i, ped = new T.CylinderGeometry(B * 0.035, B * 0.045, D * 0.45, 10);
        ped.translate(px, D + D * 0.22, B * 0.3 * (i % 2 ? 1 : -1));
        addHolo(ship, ped, color, 0.6);
        const jib = new T.BoxGeometry(pitch * 1.1, B * 0.03, B * 0.03);
        jib.rotateZ(0.5);
        jib.translate(px + pitch * 0.35, D + D * 0.62, B * 0.3 * (i % 2 ? 1 : -1));
        addHolo(ship, jib, color, 0.7);
      }
    }
    // Forecastle and foremast.
    const fc = new T.BoxGeometry(L * 0.06, D * 0.14, B * 0.5);
    fc.translate(L / 2 - L * 0.09, D + D * 0.07, 0);
    addHolo(ship, fc, color, 0.5);
    const mast = new T.CylinderGeometry(B * 0.015, B * 0.02, D * 0.8, 6);
    mast.translate(L / 2 - L * 0.1, D + D * 0.4, 0);
    addHolo(ship, mast, color, 0.7);

    root.add(ship);
    return ship;
  }

  function disposeTree(obj){
    obj.traverse(o => { if(o.geometry) o.geometry.dispose(); if(o.material && o.material.dispose) o.material.dispose(); });
  }

  function buildScene(){
    const T = H.THREE, s = H.spec;
    if(H.world){ disposeTree(H.world); H.scene.remove(H.world); }
    H.mats = H.mats.filter(m => m.__keep);
    const world = new T.Group();
    H.world = world;
    H.scene.add(world);

    const {L, B, D, T: draft, depth, quay, beamLimit, tones} = s;
    const span = Math.max(L, quay) * 0.72 + 3;
    const floorY = draft - depth;              // seabed relative to keel (y = 0)

    buildShip(world, s, TONE[tones.overall]);

    // Water surface at the laden waterline.
    const water = new T.PlaneGeometry(span * 2.2, span * 2.2);
    water.rotateX(-Math.PI / 2);
    const wm = new T.Mesh(water, gridMaterial('#38E1FF', 0.22, 3.0, span * 0.95));
    wm.position.y = draft;
    world.add(wm);

    // Seabed at the berth's usable depth. Red when the keel would touch it.
    const floor = new T.PlaneGeometry(span * 2.2, span * 2.2);
    floor.rotateX(-Math.PI / 2);
    const fm = new T.Mesh(floor, gridMaterial(TONE[tones.draft], 0.55, 2.0, span * 1.0));
    fm.position.y = floorY;
    world.add(fm);
    if(floorY > 0){
      // Keel below the seabed: a solid warning slab where they overlap.
      const clash = new T.BoxGeometry(L * 0.98, floorY, B * 0.98);
      clash.translate(0, floorY / 2, 0);
      addHolo(world, clash, TONE[tones.draft], 0.28, 0.55);
    }

    // Quay along the berth at its LOA limit; posts mark the ends.
    const qh = draft + D * 0.35 - floorY;
    const q = new T.BoxGeometry(quay, qh, 1.1);
    q.translate(0, floorY + qh / 2, -(B / 2 + 1.4));
    addHolo(world, q, '#7FD8FF', 0.18, 0.45);
    [-quay / 2, quay / 2].forEach(x => {
      const post = new T.CylinderGeometry(0.22, 0.22, qh + D * 0.8, 8);
      post.translate(x, floorY + (qh + D * 0.8) / 2, -(B / 2 + 1.4));
      addHolo(world, post, TONE[tones.loa], 0.9, 1);
    });

    // Fairway walls at the berth's beam limit, amidships.
    if(beamLimit){
      [-beamLimit / 2, beamLimit / 2].forEach(z => {
        const wall = new T.PlaneGeometry(L * 0.28, draft + D * 0.3 - floorY);
        wall.translate(0, (draft + D * 0.3 + floorY) / 2, 0);
        const m = new T.Mesh(wall, holoMaterial(TONE[tones.beam], 0.35));
        m.position.z = z;
        const e = new T.LineSegments(new T.EdgesGeometry(wall), new T.LineBasicMaterial(
          {color: TONE[tones.beam], transparent:true, opacity:.9, blending:T.AdditiveBlending, depthWrite:false}));
        e.position.z = z;
        world.add(m, e);
      });
    }

    // Projector turntable below everything.
    if(H.rings){ disposeTree(H.rings); H.scene.remove(H.rings); }
    const rings = new T.Group();
    [1, 0.78, 0.56].forEach((f, i) => {
      const r = new T.RingGeometry(span * f - 0.08 - i * 0.02, span * f, 96, 1, 0, Math.PI * (i === 1 ? 1.6 : 2));
      r.rotateX(-Math.PI / 2);
      const m = new T.Mesh(r, new T.MeshBasicMaterial({color:'#38E1FF', transparent:true, opacity:.55 - i * .12,
                                                        blending:T.AdditiveBlending, depthWrite:false, side:T.DoubleSide}));
      m.userData.spin = (i % 2 ? -1 : 1) * (0.12 + i * 0.1);
      rings.add(m);
    });
    const beam = new T.CylinderGeometry(span * 0.98, span * 0.6, 0.02, 64, 1, true);
    rings.add(new T.Mesh(beam, new T.MeshBasicMaterial({color:'#38E1FF', transparent:true, opacity:.08,
                                                         blending:T.AdditiveBlending, depthWrite:false, side:T.DoubleSide})));
    rings.position.y = Math.min(0, floorY) - 0.4;
    H.rings = rings;
    H.scene.add(rings);

    H.scanRange = [Math.min(0, floorY) - 0.2, D + D * 1.2];
    H.target = new T.Vector3(0, (draft + Math.min(0, floorY)) / 2 + D * 0.2, 0);
    H.radius = Math.max(L, quay) * 0.82 + 4;

    // Callout anchors in world-group coordinates.
    H.labels = [
      {el:'lvLblLoa',   p:[L / 2, D * 1.35, 0]},
      {el:'lvLblDraft', p:[-L / 2, draft, B / 2]},
      {el:'lvLblDepth', p:[span * 0.55, floorY, span * 0.3]},
      {el:'lvLblQuay',  p:[quay / 2, floorY + qh + D * 0.8, -(B / 2 + 1.4)]},
      {el:'lvLblBeam',  p:[0, draft + D * 0.3, (beamLimit || B) / 2]},
    ];
  }

  function frame(now){
    H.raf = requestAnimationFrame(frame);
    const stage = $('lvStage');
    const panel = $('panel-vessels');
    if(!stage || !panel || !panel.classList.contains('active') || document.hidden) return;
    const dt = Math.min(0.05, (now - (H.last || now)) / 1000);
    H.last = now;
    H.clock += dt;
    if(!H.drag && !reduced()) H.yaw += dt * 0.28;

    const T = H.THREE, cam = H.camera, r = H.radius * H.zoom;
    cam.position.set(
      H.target.x + r * Math.cos(H.pitch) * Math.sin(H.yaw),
      H.target.y + r * Math.sin(H.pitch),
      H.target.z + r * Math.cos(H.pitch) * Math.cos(H.yaw));
    cam.lookAt(H.target);

    const [lo, hi] = H.scanRange;
    const scan = lo + (hi - lo) * (0.5 + 0.5 * Math.sin(H.clock * 0.9));
    H.mats.forEach(m => { if(m.uniforms){ m.uniforms.uTime.value = H.clock; if(m.uniforms.uScan) m.uniforms.uScan.value = scan; } });
    if(H.rings) H.rings.children.forEach(c => { if(c.userData.spin) c.rotation.y += dt * c.userData.spin; });
    H.renderer.render(H.scene, cam);

    // Project the callouts onto the stage.
    const w = stage.clientWidth, h = stage.clientHeight, v = new T.Vector3();
    H.labels.forEach(l => {
      const el = $(l.el);
      if(!el) return;
      v.set(l.p[0], l.p[1], l.p[2]).applyMatrix4(H.world.matrixWorld).project(cam);
      const show = v.z < 1 && Math.abs(v.x) < 1.1 && Math.abs(v.y) < 1.1;
      el.style.opacity = show ? '1' : '0';
      el.style.transform = `translate(${(v.x * 0.5 + 0.5) * w}px, ${(-v.y * 0.5 + 0.5) * h}px)`;
    });
  }

  function resize(){
    const stage = $('lvStage');
    if(!stage || !H.renderer) return;
    const w = stage.clientWidth, h = stage.clientHeight;
    H.renderer.setSize(w, h, false);
    H.camera.aspect = w / Math.max(h, 1);
    H.camera.updateProjectionMatrix();
  }

  async function startHologram(){
    const stage = $('lvStage');
    try{
      const T = await loadThree();
      if(!H.renderer){
        const canvas = document.createElement('canvas');
        canvas.className = 'lv-canvas';
        stage.prepend(canvas);
        H.renderer = new T.WebGLRenderer({canvas, antialias:true, alpha:true});
        H.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        H.scene = new T.Scene();
        H.camera = new T.PerspectiveCamera(34, 1, 0.1, 2000);
        new ResizeObserver(resize).observe(stage);
        bindDrag(canvas);
        resize();
        H.raf = requestAnimationFrame(frame);
      }
      if(H.spec) buildScene();
      stage.classList.remove('lv-nogl');
    }catch(err){
      H.failed = true;
      stage.classList.add('lv-nogl');
      const msg = $('lvNoGl');
      if(msg) msg.textContent = 'The 3D view needs WebGL and a network connection to load its renderer. The fit checks on the right still apply.';
    }
  }

  function bindDrag(canvas){
    canvas.addEventListener('pointerdown', e => { H.drag = {x:e.clientX, y:e.clientY, yaw:H.yaw, pitch:H.pitch}; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener('pointermove', e => {
      if(!H.drag) return;
      H.yaw = H.drag.yaw - (e.clientX - H.drag.x) * 0.008;
      H.pitch = Math.max(0.05, Math.min(1.25, H.drag.pitch + (e.clientY - H.drag.y) * 0.006));
    });
    const end = () => { H.drag = null; };
    canvas.addEventListener('pointerup', end);
    canvas.addEventListener('pointercancel', end);
    canvas.addEventListener('wheel', e => { e.preventDefault(); H.zoom = Math.max(0.55, Math.min(1.8, H.zoom * (1 + Math.sign(e.deltaY) * 0.08))); }, {passive:false});
  }

  /* -------------------------------------------------- hologram UI */
  function mountHologram(){
    if(H.mounted) return;
    const section = document.querySelector('#panel-vessels .section');
    const header = section && section.querySelector('.section-header');
    if(!header) return;
    H.mounted = true;
    const host = document.createElement('section');
    host.className = 'lv-holo';
    host.id = 'lvHolo';
    host.innerHTML = `
      <div class="lv-stage" id="lvStage">
        <div class="lv-hud"><span class="lv-dot"></span>VESSEL × PORT HOLOGRAM<small id="lvHudSub"></small></div>
        <div class="lv-nogl-msg" id="lvNoGl">Loading the 3D renderer…</div>
        <div class="lv-lbl" id="lvLblLoa"></div><div class="lv-lbl" id="lvLblDraft"></div>
        <div class="lv-lbl" id="lvLblDepth"></div><div class="lv-lbl" id="lvLblQuay"></div><div class="lv-lbl" id="lvLblBeam"></div>
        <div class="lv-legend"><span><i style="background:${TONE.ok}"></i>fits</span><span><i style="background:${TONE.warn}"></i>lightering / part-load</span><span><i style="background:${TONE.fail}"></i>cannot berth</span><span class="lv-hint">drag to rotate · scroll to zoom</span></div>
      </div>
      <div class="lv-side">
        <div class="ld-label">Vessel class</div><div class="lv-chips" id="lvCls"></div>
        <div class="ld-label">Discharge berth</div><div class="lv-chips" id="lvPort"></div>
        <div class="lv-verdict" id="lvVerdict"></div>
        <div class="lv-gauges" id="lvGauges"></div>
        <div class="lv-loadport" id="lvLoadPort"></div>
      </div>`;
    header.after(host);
    startHologram();
  }

  function selectPair(clsKey, portKey){
    if(clsKey) H.sel.cls = clsKey;
    if(portKey) H.sel.port = portKey;
    renderHoloSide();
  }

  function defaultSelection(){
    if(H.sel.cls && H.sel.port) return;
    const w = typeof activeResult === 'object' && activeResult && activeResult.winner;
    H.sel.cls = H.sel.cls || (w && w.vesselClassKey) || (typeof pickVesselClass === 'function' ? pickVesselClass(cargo().parcel) : 'panamax');
    H.sel.port = H.sel.port || (w && w.portKey) || Object.keys(PORTS)[0];
  }

  function gauge(label, value, limit, unit, tone, note){
    const max = Math.max(value, limit) * 1.12 || 1;
    return `<div class="lv-gauge"><div class="lv-gauge-top"><span>${label}</span><b style="color:${TONE[tone]}">${value.toFixed(1)} ${unit}</b></div>
      <div class="lv-track"><i style="width:${value / max * 100}%;background:${TONE[tone]}"></i><em style="left:${limit / max * 100}%" title="limit"></em></div>
      <small>${note}</small></div>`;
  }

  async function renderHoloSide(){
    defaultSelection();
    const cls = $('lvCls'), prt = $('lvPort');
    if(!cls) return;
    let data = null;
    try { data = await loadFit(); } catch(e){ data = null; }

    cls.innerHTML = Object.keys(VESSEL_CLASSES).map(k => {
      const {row} = pairing(data, k, H.sel.port);
      const v = row ? verdict(row, row.berths.find(b => b.port_code === PORTS[H.sel.port].code)) : 'ok';
      return `<button type="button" class="lv-chip${k === H.sel.cls ? ' on' : ''}" data-cls="${k}" style="--t:${TONE[v]}">
        <svg viewBox="0 0 60 16" aria-hidden="true">${silhouette(k, 60, 16)}</svg>${esc(VESSEL_CLASSES[k].name)}</button>`;
    }).join('');
    prt.innerHTML = Object.keys(PORTS).map(k => {
      const {row, berth} = pairing(data, H.sel.cls, k);
      const v = data ? verdict(row, berth) : 'ok';
      return `<button type="button" class="lv-chip${k === H.sel.port ? ' on' : ''}" data-port="${k}" style="--t:${TONE[v]}"><i></i>${esc(PORTS[k].name)}</button>`;
    }).join('');
    cls.querySelectorAll('[data-cls]').forEach(b => b.onclick = () => selectPair(b.dataset.cls, null));
    prt.querySelectorAll('[data-port]').forEach(b => b.onclick = () => selectPair(null, b.dataset.port));

    const v = VESSEL_CLASSES[H.sel.cls], p = PORTS[H.sel.port];
    const {row, berth} = pairing(data, H.sel.cls, H.sel.port);
    const checks = berth ? berth.checks : [];
    const st = name => { const c = checks.find(x => x.check === name); return c ? statusOf(c.status) : 'ok'; };
    const draft = row ? row.laden_draft_m : v.draft;
    const loa = row ? row.loa_m : v.loa, beam = row ? row.beam_m : v.beam;
    const usable = p.draft - UKC;
    const tones = {draft: st('Draft at berth'), loa: st('LOA at berth'), beam: st('Beam at berth'), overall: data ? verdict(row, berth) : 'ok'};
    const noLoad = row && !row.load_port.feasible;
    const word = noLoad ? 'CANNOT LOAD' : {ok:'FITS', warn:'LIGHTERING', fail:'CANNOT BERTH'}[tones.overall];

    $('lvVerdict').innerHTML = `<div class="lv-word" style="color:${TONE[tones.overall]}">${word}</div>
      <div class="lv-reason">${esc((berth && berth.reason) || (row && row.load_port.reason) ||
        (tones.overall === 'warn' ? `${v.name} sits ${(draft - usable).toFixed(1)} m deeper than ${p.name}'s usable draft - part of the cargo is lightered.`
                                  : `${v.name} clears ${p.name} on draft, length and beam.`))}</div>`;
    $('lvGauges').innerHTML =
        gauge('Laden draft vs usable depth', draft, usable, 'm', tones.draft, `berth ${p.draft} m − ${UKC} m under-keel = ${usable.toFixed(1)} m`)
      + gauge('Length overall vs berth limit', loa, p.loa, 'm', tones.loa, `${p.name} accepts ${p.loa} m`)
      + gauge('Beam vs berth limit', beam, p.beam || beam, 'm', tones.beam, p.beam ? `${p.name} accepts ${p.beam} m` : 'no beam limit recorded');
    const lp = row && row.load_port, lpName = data && data.load_port ? data.load_port.name : 'origin terminal';
    $('lvLoadPort').innerHTML = row ? `<span class="ld-label">Load port · ${esc(lpName)}</span>
      <div style="color:${TONE[!lp.feasible ? 'fail' : lp.part_loaded ? 'warn' : 'ok']}">${!lp.feasible ? esc(lp.reason) : lp.part_loaded ? `Part-loaded to ${Math.round(row.lift_mt).toLocaleString('en-IN')} MT by the terminal's draft` : `Loads a full ${Math.round(row.lift_mt).toLocaleString('en-IN')} MT lift`}</div>` : '';
    $('lvHudSub').textContent = `${v.name} · ${p.name}`;

    H.spec = {key: H.sel.cls, L: loa / 10, B: beam / 10, D: (v.draft / 0.72) / 10, T: draft / 10,
              depth: usable / 10, quay: p.loa / 10, beamLimit: (p.beam || 0) / 10, tones};
    const lbl = (id, text) => { const el = $(id); if(el) el.textContent = text; };
    lbl('lvLblLoa', `LOA ${loa} m`);
    lbl('lvLblDraft', `waterline · ${draft.toFixed(1)} m laden`);
    lbl('lvLblDepth', `seabed · ${usable.toFixed(1)} m usable`);
    lbl('lvLblQuay', `berth limit ${p.loa} m`);
    lbl('lvLblBeam', `beam ${beam} m · limit ${p.beam || '—'} m`);
    if(H.THREE && H.renderer) buildScene();
  }

  /* ============================================== SILHOUETTES (2D) */
  function silhouette(key, w, h){
    const v = VESSEL_CLASSES[key], maxL = VESSEL_CLASSES.capesize ? VESSEL_CLASSES.capesize.loa : 300;
    const L = (v.loa / maxL) * (w - 4), x0 = (w - L) / 2, D = h * 0.42, deck = h * 0.4, keel = deck + D;
    const n = HATCHES[key] || 6;
    const hatches = Array.from({length:n}, (_, i) => {
      const hx = x0 + L * 0.16 + (L * 0.72 / n) * i;
      return `<rect x="${hx.toFixed(1)}" y="${(deck - h * 0.07).toFixed(1)}" width="${(L * 0.72 / n * 0.7).toFixed(1)}" height="${(h * 0.07).toFixed(1)}" fill="currentColor" opacity=".7"/>`;
    }).join('');
    return `<path d="M${x0} ${deck} L${x0 + L * 0.9} ${deck} L${x0 + L} ${deck - h * 0.06} L${x0 + L * 0.93} ${keel} L${x0 + L * 0.04} ${keel} Z" fill="currentColor" opacity=".9"/>
      <rect x="${x0 + L * 0.03}" y="${deck - h * 0.34}" width="${L * 0.09}" height="${h * 0.34}" fill="currentColor"/>
      ${hatches}`;
  }

  /* ================================================ PORT PROFILES */
  function depthChart(){
    const ports = Object.values(PORTS).slice().sort((a, b) => b.draft - a.draft);
    const classes = Object.entries(VESSEL_CLASSES);
    const W = 960, H0 = 300, top = 46, bottom = 250, left = 20, right = 170;
    const maxD = 21, y = d => top + d / maxD * (bottom - top);
    const colW = (W - left - right) / ports.length;
    const cols = ports.map((p, i) => {
      const x = left + i * colW, d = y(p.draft);
      const fits = classes.filter(([, v]) => v.draft + UKC <= p.draft).length;
      return `<g><rect x="${x + 4}" y="${top}" width="${colW - 8}" height="${d - top}" fill="url(#lvWater)" rx="3"/>
        <path d="M${x + 4} ${d} h${colW - 8} V${bottom + 6} H${x + 4} Z" fill="url(#lvSeabed)" stroke="#B08A55" stroke-opacity=".7" stroke-width="1.2"/>
        <text x="${x + colW / 2}" y="${d - 8}" text-anchor="middle" class="lv-ax strong">${p.draft} m</text>
        <text x="${x + colW / 2}" y="${bottom + 24}" text-anchor="middle" class="lv-ax strong">${esc(p.name.split('/')[0])}</text>
        <text x="${x + colW / 2}" y="${bottom + 40}" text-anchor="middle" class="lv-ax">${fits}/${classes.length} fit</text></g>`;
    }).join('');
    const lines = classes.map(([k, v]) => {
      const yy = y(v.draft + UKC);
      return `<line x1="${left}" x2="${W - right + 6}" y1="${yy}" y2="${yy}" stroke="${CLASS_TINT[k]}" stroke-width="2" stroke-dasharray="7 5"/>
        <g transform="translate(${W - right + 12} ${yy - 7})" style="color:${CLASS_TINT[k]}"><svg width="40" height="14" viewBox="0 0 60 16">${silhouette(k, 60, 16)}</svg></g>
        <text x="${W - right + 58}" y="${yy + 4}" class="lv-ax" fill="${CLASS_TINT[k]}">${esc(v.name)} ${v.draft} m</text>`;
    }).join('');
    return `<section class="ld-card lv-depth">
      <div class="lp-cardhead"><div><h4>Berth depth vs vessel draft</h4>
        <p class="ld-card-sub">Each column is a berth's water depth; each dashed line is a class's full-laden draft plus ${UKC} m under-keel. A line above the seabed clears; below it, the ship must be lightered or part-loaded.</p></div></div>
      <svg viewBox="0 0 ${W} ${H0}" role="img" aria-label="Berth depth against vessel draft">
        <defs><linearGradient id="lvWater" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="var(--ld-accent)" stop-opacity=".45"/><stop offset="1" stop-color="var(--ld-accent)" stop-opacity=".12"/></linearGradient>
          <pattern id="lvSeabed" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="8" height="8" fill="#B08A55" fill-opacity=".28"/><line x1="0" y1="0" x2="0" y2="8" stroke="#B08A55" stroke-opacity=".55" stroke-width="2"/></pattern></defs>
        <line x1="${left}" x2="${W - right}" y1="${top}" y2="${top}" stroke="var(--ld-accent)" stroke-width="1.5"/>
        <text x="${left}" y="${top - 10}" class="lv-ax">sea level</text>
        ${cols}${lines}
      </svg></section>`;
  }

  function metricBar(label, value, max, text, tone){
    return `<div class="lv-mbar"><span>${label}</span><div class="lv-mtrack"><i style="width:${Math.min(100, value / max * 100)}%;background:${tone || 'var(--ld-accent)'}"></i></div><b>${text}</b></div>`;
  }

  renderPortGrid = function(){
    const grid = $('portGrid');
    if(!grid) return;
    const month = typeof currentMonth === 'function' ? currentMonth() : new Date().getMonth() + 1;
    const ports = Object.values(PORTS);
    const mx = f => Math.max(...ports.map(f));
    let chart = $('lvDepthHost');
    if(!chart){ chart = document.createElement('div'); chart.id = 'lvDepthHost'; grid.before(chart); }
    chart.innerHTML = depthChart();
    grid.innerHTML = ports.map(p => {
      const monsoon = p.monsoon.includes(month);
      return `<div class="port-card lv-port">
        <div class="lv-port-head"><div><div class="port-name">${esc(p.name)}</div><div class="port-code">${esc(p.code)} · ${p.berths} berth${p.berths > 1 ? 's' : ''}</div></div>
          ${monsoon ? '<span class="lp-chip part">monsoon now</span>' : ''}</div>
        <div class="lv-berths">${Array.from({length:p.berths}, () => '<i></i>').join('')}</div>
        ${metricBar('Draft', p.draft, mx(x => x.draft), p.draft + ' m')}
        ${metricBar('LOA', p.loa, mx(x => x.loa), p.loa + ' m')}
        ${metricBar('Beam', p.beam || 0, mx(x => x.beam || 0), (p.beam || '—') + ' m')}
        ${metricBar('Queue', p.waitDays, mx(x => x.waitDays), p.waitDays + ' d', p.waitDays > 4 ? 'var(--ld-crit)' : p.waitDays > 2.5 ? 'var(--ld-warn)' : 'var(--ld-pos)')}
        ${metricBar('Discharge', p.mechRate, mx(x => x.mechRate), Math.round(p.mechRate / 1000) + 'k MT/d')}
        ${metricBar('Demurrage', p.demurrage, mx(x => x.demurrage), '$' + (p.demurrage / 1000).toFixed(1) + 'k/d', 'var(--ld-warn)')}
        <div class="lv-months" title="Weather-affected months">${[1,2,3,4,5,6,7,8,9,10,11,12].map(m =>
          `<i class="${p.monsoon.includes(m) ? 'wx' : ''}${m === month ? ' now' : ''}">${'JFMAMJJASOND'[m - 1]}</i>`).join('')}</div>
      </div>`;
    }).join('');
    // The comparison table repeats the cards; fold it away.
    const table = $('portCompTable');
    const card = table && table.closest('.battle-card');
    if(card && !card.closest('details')){
      const d = document.createElement('details');
      d.className = 'lv-fold';
      d.innerHTML = '<summary>Show the comparison table</summary>';
      card.before(d);
      d.appendChild(card);
    }
    const tbody = $('portCompBody');
    if(tbody){
      tbody.innerHTML = ports.map(p => `<tr><td><b>${esc(p.name)}</b></td><td>${p.draft}</td><td>${p.loa} m</td><td>${p.berths}</td>
        <td>${p.waitDays} d</td><td>${Math.round(p.mechRate).toLocaleString('en-IN')}</td><td>${p.evacKm} km</td>
        <td>$${Math.round(p.demurrage).toLocaleString('en-IN')}</td><td>${p.monsoon.includes(month) ? 'HIGH' : 'LOW'}</td></tr>`).join('');
    }
  };

  /* ================================================== VESSEL FIT */
  renderVesselGrid = function(){
    const grid = $('vesselGrid');
    if(!grid) return;
    mountHologram();
    // Badge the class the engine actually chose, not a parcel-size rule of thumb.
    const w = typeof activeResult === 'object' && activeResult && activeResult.winner;
    const rec = w ? w.vesselClassKey : null;
    const classes = Object.entries(VESSEL_CLASSES);
    const mx = f => Math.max(...classes.map(([, v]) => f(v)));
    const draw = data => {
      grid.innerHTML = classes.map(([k, v]) => {
        const row = data && data.vessels.find(r => r.vessel_class.toLowerCase() === k);
        const ok = row ? row.berths.filter(b => b.feasible).length : null;
        return `<button type="button" class="vessel-card lv-vessel${k === rec ? ' selected' : ''}" data-cls="${k}">
          <div class="lv-vessel-head"><h4>${esc(v.name)}</h4>${k === rec ? '<span class="winner-badge">ENGINE PICK</span>' : ''}</div>
          <svg class="lv-sil" viewBox="0 0 120 30" style="color:${CLASS_TINT[k]}" aria-hidden="true">${silhouette(k, 120, 30)}</svg>
          ${metricBar('DWT', v.dwtMax, mx(x => x.dwtMax), Math.round(v.dwtMax / 1000) + 'k t', CLASS_TINT[k])}
          ${metricBar('LOA', v.loa, mx(x => x.loa), v.loa + ' m', CLASS_TINT[k])}
          ${metricBar('Beam', v.beam, mx(x => x.beam), v.beam + ' m', CLASS_TINT[k])}
          ${metricBar('Draft', v.draft, mx(x => x.draft), v.draft + ' m', CLASS_TINT[k])}
          <div class="lv-access">${ok == null ? '' : `<b>${ok}/${row.berths.length}</b> berths usable${row.load_port.part_loaded ? ' · part-loads at origin' : ''}${!row.load_port.feasible ? ' · <span style="color:var(--ld-crit)">cannot load at origin</span>' : ''}`}</div>
        </button>`;
      }).join('');
      grid.querySelectorAll('[data-cls]').forEach(b => b.onclick = () => { selectPair(b.dataset.cls, null); $('lvHolo').scrollIntoView({behavior:'smooth', block:'start'}); });
      drawMatrix(data);
    };
    draw(FIT.data);
    loadFit().then(draw).catch(() => draw(null));
    renderHoloSide();
  };

  function drawMatrix(data){
    const head = $('vesselPortMatrixHead'), body = $('vesselPortMatrixBody');
    if(!head || !body) return;
    const card = head.closest('.battle-card');
    const p = card && card.querySelector('.section-header p');
    if(p) p.textContent = 'The engine\'s own checks for the cargo on file - draft (with lightering), LOA and beam at every berth, and the origin load port. Click any cell to see that pairing in the hologram.';
    const classes = Object.keys(VESSEL_CLASSES);
    head.innerHTML = `<tr><th>Berth</th>${classes.map(k => `<th>${esc(VESSEL_CLASSES[k].name)}</th>`).join('')}</tr>`;
    if(!data){ body.innerHTML = '<tr><td colspan="5">Engine checks unavailable.</td></tr>'; return; }
    body.innerHTML = Object.keys(PORTS).map(pk => `<tr><td><b>${esc(PORTS[pk].name)}</b></td>${classes.map(k => {
        const {row, berth} = pairing(data, k, pk);
        const v = verdict(row, berth);
        const label = {ok:'Fits', warn:'Lighter', fail:'No'}[v];
        return `<td><button type="button" class="lv-cell" data-cls="${k}" data-port="${pk}" style="--t:${TONE[v]}" title="${esc((berth && berth.reason) || label)}"><i></i>${label}</button></td>`;
      }).join('')}</tr>`).join('');
    body.querySelectorAll('.lv-cell').forEach(b => b.onclick = () => {
      selectPair(b.dataset.cls, b.dataset.port);
      $('lvHolo').scrollIntoView({behavior:'smooth', block:'start'});
    });
  }

  /* ============================================ EXECUTION BRIEF TIMELINE */
  function voyageStrip(a){
    const legs = [
      ['Load port', a.load_port_days, 'var(--ld-mute)', a.load_port || 'origin'],
      ['Sea passage', a.sea_days, 'var(--ld-accent)', ''],
      ['Berth queue', a.wait_days, 'var(--ld-warn)', a.congestion_basis || ''],
      ['Discharge', a.discharge_days, 'var(--ld-pos)', a.port_name],
    ].filter(l => l[1] > 0);
    const total = legs.reduce((s, l) => s + l[1], 0) || 1;
    return `<section class="ld-card lv-voyage">
      <div class="lp-cardhead"><div><h4>Voyage cycle · ${total.toFixed(1)} days</h4>
        <p class="ld-card-sub">${esc(a.load_port || 'Origin')} → ${esc(a.port_name)} → ${Math.round(a.rail_km)} km by rail to the plant</p></div></div>
      <div class="lv-strip">${legs.map(l => `<div class="lv-leg" style="flex:${l[1]};--c:${l[2]}"><b>${l[1].toFixed(1)} d</b><span>${l[0]}</span></div>`).join('')}
        <div class="lv-leg rail" style="--c:var(--ld-ink)"><b>${Math.round(a.rail_km)} km</b><span>Rail</span></div></div>
      <div class="lv-route"><span>${ICON.anchor}${esc(a.load_port || 'Origin')}</span><i></i><span>${ICON.ship}${esc(a.vessel_class)}</span><i></i><span>${ICON.anchor}${esc(a.port_name)}</span><i></i><span>${ICON.plant}Plant</span></div>
    </section>`;
  }

  function injectBrief(){
    const panel = $('panel-approved');
    const main = panel && panel.querySelector('.ldb-main');
    const a = typeof activeResult === 'object' && activeResult && activeResult.winner && activeResult.winner.api;
    if(!main || !a) return;
    const existing = panel.querySelector('.lv-voyage');
    const html = voyageStrip(a);
    if(existing){ if(existing.dataset.sig !== a.port_name + a.vessel_class + a.total_cycle_days) existing.outerHTML = html; else return; }
    else main.insertAdjacentHTML('afterend', html);
    const el = panel.querySelector('.lv-voyage');
    if(el) el.dataset.sig = a.port_name + a.vessel_class + a.total_cycle_days;
  }

  /* ============================================ ABOUT: LIVE COST BUILD-UP */
  function renderAboutCost(){
    const host = $('lvAboutCost');
    const a = typeof activeResult === 'object' && activeResult && activeResult.winner && activeResult.winner.api;
    if(!host || !a) return;
    const parts = [
      ['Ocean freight', a.ocean_freight_usd, 'var(--ld-accent)'], ['Vessel hire', a.vessel_hire_usd, 'var(--navy-surface)'],
      ['Deadfreight', a.deadfreight_usd, 'var(--ld-crit)'], ['Port dues', a.port_dues_usd, 'var(--ld-mute)'],
      ['Demurrage', a.demurrage_usd, 'var(--ld-warn)'], ['Lightering', a.lightering_usd, '#B08A55'],
      ['Inland rail', a.inland_rail_usd, 'var(--ld-pos)'],
    ].filter(p => p[1] > 0);
    const total = parts.reduce((s, p) => s + p[1], 0) || 1, t = a.parcel_mt || 1;
    host.innerHTML = `<div class="lv-stack">${parts.map(p => `<i style="flex:${p[1]};background:${p[2]}" title="${p[0]}: $${(p[1] / t).toFixed(2)}/MT"></i>`).join('')}</div>
      <ul class="lv-key lv-key-grid">${parts.map(p => `<li><i style="background:${p[2]}"></i>${p[0]} <b>$${(p[1] / t).toFixed(2)}</b><small>${Math.round(p[1] / total * 100)}%</small></li>`).join('')}</ul>
      <p class="lp-foot">${esc(a.vessel_class)} via ${esc(a.port_name)} · $${a.landed_cost_usd_mt.toFixed(2)}/MT landed, before the cargo's FOB price.</p>`;
  }

  /* ============================================ COMMAND CENTRE CTA */
  function injectCta(){
    const cta = document.querySelector('#ldCommand .ldc-cta');
    if(!cta || $('ldcHolo')) return;
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'ld-btn'; b.id = 'ldcHolo';
    b.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/></svg>3D vessel × port';
    b.onclick = () => {
      const w = activeResult && activeResult.winner;
      if(w){ H.sel.cls = w.vesselClassKey; H.sel.port = w.portKey; }
      switchPanel('vessels');
    };
    const note = cta.querySelector('.ldc-run-note');
    cta.insertBefore(b, note || null);
  }

  /* ================================================================ HOOKS */
  const obs = new MutationObserver(() => { injectBrief(); injectCta(); });
  ['panel-approved', 'panel-command'].forEach(id => { const el = $(id); if(el) obs.observe(el, {childList:true, subtree:true}); });

  const _switch = switchPanel;
  switchPanel = function(name){
    const out = _switch.apply(this, arguments);
    if(document.getElementById('panel-vessels').classList.contains('active')){ mountHologram(); renderVesselGrid(); }
    if(document.getElementById('panel-ports').classList.contains('active')) renderPortGrid();
    if(document.getElementById('panel-approved').classList.contains('active')) injectBrief();
    if(document.getElementById('panel-about').classList.contains('active')) renderAboutCost();
    return out;
  };
  injectCta();
})();
