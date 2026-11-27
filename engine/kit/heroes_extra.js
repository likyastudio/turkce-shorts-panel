// engine/kit/heroes_extra.js — Extra 3D-Toon heroProp dioramas (same toonMat / tbox / tcyl language)
// Registered kinds:
//   halic_chain        — Golden Horn mouth: water, two towers, giant floating iron chain, blocked galley
//   ships_hill         — Galata hill with greased log slipway; galleys sliding up & over (oars rowing in the air!)
//   city_walls         — Theodosian land walls + towers + Hagia Sophia dome + Şahi great bronze cannon
//   golden_horn_fleet  — Ottoman galleys afloat INSIDE the Golden Horn in front of the sea walls
// Each builder receives { THREE, heroGroup, tbox, tcyl, toonMat } and returns animate(t).

function makeWater(THREE, toonMat, w, d, color = '#2f7fc1') {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, 0.12, d), toonMat(color));
  m.receiveShadow = true;
  return m;
}

// Ottoman kadırga (galley): hull + prow + stern cabin + mast + red lateen-ish sail + crescent flag + oars
export function makeGalley(ctx, opts = {}) {
  const { THREE, tbox, tcyl, toonMat } = ctx;
  const g = new THREE.Group();
  const hullC = opts.hull || '#7a4a22';
  const sailC = opts.sail || '#d62828';
  g.add(tbox(3.0, 0.5, 0.8, hullC, 0, 0.25, 0));
  g.add(tbox(3.2, 0.12, 0.92, '#4e2c16', 0, 0.54, 0));
  const prow = tbox(0.9, 0.36, 0.5, hullC, 1.8, 0.42, 0);
  prow.rotation.z = 0.35;
  g.add(prow);
  g.add(tbox(0.7, 0.55, 0.78, '#9c6b3a', -1.25, 0.85, 0));
  g.add(tbox(0.78, 0.1, 0.86, '#ffd60a', -1.25, 1.14, 0));
  g.add(tcyl(0.06, 0.07, 2.6, 8, '#5c3a1a', 0.15, 1.85, 0));
  const yard = tbox(2.4, 0.08, 0.08, '#5c3a1a', 0.15, 2.9, 0);
  yard.rotation.z = -0.32;
  g.add(yard);
  const sail = tbox(1.9, 1.5, 0.05, sailC, 0.2, 2.1, 0.06);
  sail.rotation.z = -0.12;
  g.add(sail);
  // White crescent emblem on sail
  const cres = tcyl(0.34, 0.34, 0.07, 18, '#ffffff', 0.2, 2.15, 0.1);
  cres.rotation.x = Math.PI / 2;
  g.add(cres);
  const cresCut = tcyl(0.28, 0.28, 0.08, 18, sailC, 0.3, 2.19, 0.12);
  cresCut.rotation.x = Math.PI / 2;
  g.add(cresCut);
  const flag = tbox(0.5, 0.3, 0.03, '#c92a2a', 0.42, 3.35, 0);
  g.add(flag);
  const oars = [];
  for (let i = 0; i < 6; i++) {
    for (const side of [-1, 1]) {
      const pivot = new THREE.Group();
      pivot.position.set(-0.9 + i * 0.42, 0.5, side * 0.46);
      const oar = tbox(0.06, 0.06, 1.1, '#c8a06a', 0, -0.15, side * 0.5);
      oar.rotation.x = side * 0.5;
      pivot.add(oar);
      g.add(pivot);
      oars.push({ pivot, side, i });
    }
  }
  return {
    group: g,
    flag,
    row(t, speed = 4.2) {
      for (const o of oars) o.pivot.rotation.y = Math.sin(t * speed + o.i * 0.15) * 0.45 * o.side;
      flag.rotation.y = Math.sin(t * 3.1) * 0.3;
    },
  };
}

function makeTower(ctx, x, z, h = 4.2, r = 0.9, color = '#c9b48a') {
  const { THREE, tbox, tcyl } = ctx;
  const g = new THREE.Group();
  g.add(tcyl(r, r * 1.08, h, 14, color, 0, h / 2, 0));
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2;
    g.add(tbox(0.32, 0.36, 0.32, color, Math.cos(a) * r * 0.92, h + 0.16, Math.sin(a) * r * 0.92));
  }
  g.position.set(x, 0, z);
  return g;
}

function halicChain(ctx) {
  const { THREE, heroGroup, tbox, tcyl, toonMat } = ctx;
  const water = makeWater(THREE, toonMat, 22, 12, '#2f7fc1');
  water.position.set(0, 0.04, -0.6);
  heroGroup.add(water);
  heroGroup.add(makeTower(ctx, -6.4, -0.4, 5.0, 1.1));
  heroGroup.add(makeTower(ctx, 6.4, -0.4, 5.0, 1.1, '#bfa77a'));
  // Giant floating chain: alternating torus links between towers + wooden floats
  const linkMat = toonMat('#3a3f47');
  const links = [];
  const N = 26;
  for (let i = 0; i < N; i++) {
    const u = i / (N - 1);
    const x = -5.6 + u * 11.2;
    const link = new THREE.Mesh(new THREE.TorusGeometry(0.28, 0.09, 8, 14), linkMat);
    link.castShadow = true;
    link.rotation.y = i % 2 === 0 ? 0 : Math.PI / 2;
    heroGroup.add(link);
    links.push({ link, x, u, i });
    if (i % 3 === 1) {
      const log = tcyl(0.22, 0.22, 1.1, 10, '#8b5a2b', x, 0.2, 1.0);
      log.rotation.x = Math.PI / 2;
      heroGroup.add(log);
      links.push({ log, x, u, i });
    }
  }
  // Ottoman galley stuck in front of the chain (outside)
  const gal = makeGalley(ctx);
  gal.group.position.set(0.5, 0.05, 3.2);
  gal.group.rotation.y = Math.PI / 2 + 0.2;
  gal.group.scale.setScalar(0.85);
  heroGroup.add(gal.group);
  return (t) => {
    for (const L of links) {
      const y = 0.55 - Math.sin(L.u * Math.PI) * 0.35 + Math.sin(t * 1.6 + L.u * 6) * 0.05;
      if (L.link) L.link.position.set(L.x, y, 1.0);
      if (L.log) L.log.position.y = 0.16 + Math.sin(t * 1.6 + L.u * 6) * 0.05;
    }
    gal.group.position.y = 0.05 + Math.sin(t * 1.8) * 0.06;
    gal.group.rotation.z = Math.sin(t * 1.3) * 0.04;
    gal.row(t, 2.4);
  };
}

function shipsHill(ctx) {
  const { THREE, heroGroup, tbox, tcyl, toonMat } = ctx;
  // Clean trapezoid hill (no protruding rectangular corners behind the slopes)
  const hillShape = new THREE.Shape();
  hillShape.moveTo(-7.8, 0);
  hillShape.lineTo(-1.75, 3.05);
  hillShape.lineTo(1.75, 3.05);
  hillShape.lineTo(7.8, 0);
  hillShape.closePath();
  const hillGeo = new THREE.ExtrudeGeometry(hillShape, { depth: 4.4, bevelEnabled: false });
  hillGeo.translate(0, 0, -2.2);
  const hillMesh = new THREE.Mesh(hillGeo, toonMat('#4d8d3b'));
  hillMesh.castShadow = true;
  hillMesh.receiveShadow = true;
  heroGroup.add(hillMesh);

  // Darker terraced grass ridge cap along the crest
  const capShape = new THREE.Shape();
  capShape.moveTo(-7.9, 0);
  capShape.lineTo(-1.75, 3.18);
  capShape.lineTo(1.75, 3.18);
  capShape.lineTo(7.9, 0);
  capShape.lineTo(7.4, 0);
  capShape.lineTo(1.65, 2.92);
  capShape.lineTo(-1.65, 2.92);
  capShape.lineTo(-7.4, 0);
  capShape.closePath();
  const capGeo = new THREE.ExtrudeGeometry(capShape, { depth: 4.6, bevelEnabled: false });
  capGeo.translate(0, 0, -2.3);
  const capMesh = new THREE.Mesh(capGeo, toonMat('#5da447'));
  capMesh.castShadow = true;
  heroGroup.add(capMesh);

  // Subtle glowing moon & stars high in the night sky behind the ridge
  const moon = new THREE.Mesh(
    new THREE.SphereGeometry(0.72, 18, 14),
    new THREE.MeshBasicMaterial({ color: 0xfff3bf })
  );
  moon.position.set(5.4, 6.2, -4.5);
  moon.userData.skipNd = true;
  heroGroup.add(moon);
  const starMat = new THREE.MeshBasicMaterial({ color: 0xffe8a3 });
  for (const [sx, sy] of [[-5.2, 6.4], [-2.8, 6.9], [0.4, 7.1], [2.6, 6.6], [6.8, 5.4], [-6.8, 5.8], [3.9, 5.5]]) {
    const st = new THREE.Mesh(new THREE.SphereGeometry(0.08, 6, 6), starMat);
    st.position.set(sx, sy, -5.0);
    st.userData.skipNd = true;
    heroGroup.add(st);
  }

  // Greased log slipway path (logs cleanly riding atop the trapezoid slopes)
  const path = [];
  const pts = [[-7.4, 0.15], [-1.7, 3.05], [1.7, 3.05], [7.4, 0.15]];
  const segLen = (a, b) => Math.hypot(b[0] - a[0], b[1] - a[1]);
  const lens = [segLen(pts[0], pts[1]), segLen(pts[1], pts[2]), segLen(pts[2], pts[3])];
  const total = lens[0] + lens[1] + lens[2];
  function along(s) {
    let d = ((s % 1) + 1) % 1 * total;
    for (let k = 0; k < 3; k++) {
      if (d <= lens[k]) {
        const u = d / lens[k];
        const a = pts[k], b = pts[k + 1];
        return { x: a[0] + (b[0] - a[0]) * u, y: a[1] + (b[1] - a[1]) * u, ang: Math.atan2(b[1] - a[1], b[0] - a[0]) };
      }
      d -= lens[k];
    }
    return { x: pts[3][0], y: pts[3][1], ang: 0 };
  }
  const greaseLog = toonMat('#b07a3c');
  for (let i = 0; i <= 34; i++) {
    const p = along(i / 34.0001);
    const log = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.11, 1.6, 8), greaseLog);
    log.rotation.x = Math.PI / 2;
    log.position.set(p.x, p.y + 0.36, 1.2);
    log.castShadow = true;
    heroGroup.add(log);
    path.push(log);
  }
  // Galata tower on the left ridge
  const gt = new THREE.Group();
  gt.add(tcyl(0.75, 0.85, 4.8, 14, '#bfa77a', 0, 2.4, 0));
  gt.add(tbox(1.9, 0.18, 1.9, '#8b6b45', 0, 4.9, 0));
  const roof = new THREE.Mesh(new THREE.ConeGeometry(0.95, 1.6, 14), toonMat('#5c677d'));
  roof.position.set(0, 5.8, 0);
  roof.castShadow = true;
  gt.add(roof);
  gt.position.set(-6.8, 0, -2.6);
  heroGroup.add(gt);
  // 3 galleys travelling along the slipway (staggered)
  const ships = [0, 1, 2].map((k) => {
    const gal = makeGalley(ctx, { sail: k === 1 ? '#f8f9fa' : '#d62828' });
    gal.group.scale.setScalar(0.62);
    heroGroup.add(gal.group);
    return { gal, off: k / 3 };
  });
  return (t) => {
    for (const s of ships) {
      const p = along(t * 0.045 + s.off);
      s.gal.group.position.set(p.x, p.y + 0.5, 1.2);
      s.gal.group.rotation.set(0, 0, p.ang);
      s.gal.row(t, 5.0);
    }
  };
}

function cityWalls(ctx) {
  const { THREE, heroGroup, tbox, tcyl, toonMat } = ctx;
  const stone = '#c9b48a';
  heroGroup.add(tbox(20, 3.0, 1.0, stone, 0, 1.5, -1.0));
  for (let i = -9; i <= 9; i += 1.2) heroGroup.add(tbox(0.55, 0.45, 1.05, stone, i, 3.2, -1.0));
  for (const x of [-8, -4, 0, 4, 8]) {
    heroGroup.add(tbox(1.6, 4.4, 1.6, '#bfa77a', x, 2.2, -0.9));
    for (const dx of [-0.55, 0, 0.55]) heroGroup.add(tbox(0.4, 0.4, 1.65, '#bfa77a', x + dx, 4.6, -0.9));
  }
  // Hagia Sophia (no minarets in 1453): base + great dome + half domes
  const hs = new THREE.Group();
  hs.add(tbox(6.0, 3.0, 4.0, '#e8b4a0', 0, 1.5, 0));
  const dome = new THREE.Mesh(new THREE.SphereGeometry(2.0, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2), toonMat('#9aa5b1'));
  dome.position.set(0, 3.6, 0);
  dome.castShadow = true;
  hs.add(dome);
  hs.add(tcyl(2.1, 2.1, 0.7, 20, '#e8b4a0', 0, 3.3, 0));
  for (const sx of [-1, 1]) {
    const hd = new THREE.Mesh(new THREE.SphereGeometry(1.3, 16, 10, 0, Math.PI * 2, 0, Math.PI / 2), toonMat('#9aa5b1'));
    hd.position.set(sx * 2.6, 3.0, 0);
    hs.add(hd);
  }
  hs.position.set(1.5, 0, -6.5);
  hs.scale.setScalar(1.15);
  heroGroup.add(hs);
  // Byzantine banner on center tower
  heroGroup.add(tcyl(0.05, 0.05, 1.8, 6, '#495057', 0, 5.7, -0.9));
  const ban = tbox(1.0, 0.62, 0.04, '#7b2cbf', 0.52, 6.25, -0.9);
  heroGroup.add(ban);
  heroGroup.add(tbox(0.36, 0.36, 0.05, '#ffd60a', 0.52, 6.25, -0.86));
  // Şahi great bronze cannon in the foreground (aimed at the walls)
  const cannon = new THREE.Group();
  const barrel = tcyl(0.55, 0.7, 4.2, 18, '#c08a2e', 0, 0, 0);
  barrel.rotation.z = Math.PI / 2;
  cannon.add(barrel);
  const mouth = tcyl(0.68, 0.68, 0.3, 18, '#a8741f', -2.1, 0, 0);
  mouth.rotation.z = Math.PI / 2;
  cannon.add(mouth);
  cannon.add(tbox(3.6, 0.5, 1.4, '#6f4518', 0.2, -0.75, 0));
  cannon.position.set(-3.6, 1.2, 4.6);
  cannon.rotation.y = -0.5;
  cannon.rotation.z = -0.08;
  heroGroup.add(cannon);
  const smokeMat = toonMat('#f1f3f5');
  const puffs = [0, 1, 2].map((i) => {
    const p = new THREE.Mesh(new THREE.SphereGeometry(0.6, 12, 10), smokeMat);
    heroGroup.add(p);
    return { p, i };
  });
  return (t) => {
    ban.rotation.y = Math.sin(t * 2.4) * 0.25;
    const cyc = (t % 4.0) / 4.0;
    for (const P of puffs) {
      const k = Math.max(0, cyc * 3 - P.i * 0.25);
      const vis = cyc < 0.55;
      P.p.visible = vis;
      const s = 0.4 + k * 0.9;
      P.p.scale.setScalar(s);
      P.p.position.set(-3.6 - 1.9 * Math.cos(0.5) - k * 1.2, 1.3 + k * 0.6 + P.i * 0.2, 4.6 + 1.9 * Math.sin(0.5) - k * 0.8);
    }
    cannon.position.x = -3.6 + (cyc < 0.08 ? (0.08 - cyc) * 3.0 : 0);
  };
}

function goldenHornFleet(ctx) {
  const { THREE, heroGroup, tbox, toonMat } = ctx;
  const water = makeWater(THREE, toonMat, 24, 10, '#3388cc');
  water.position.set(0, 0.04, 1.5);
  heroGroup.add(water);
  // Sea walls behind (lower) with towers
  const stone = '#c9b48a';
  heroGroup.add(tbox(22, 2.2, 0.8, stone, 0, 1.1, -3.6));
  for (let i = -10; i <= 10; i += 1.1) heroGroup.add(tbox(0.5, 0.4, 0.85, stone, i, 2.4, -3.6));
  for (const x of [-7.5, -2.5, 2.5, 7.5]) heroGroup.add(tbox(1.4, 3.4, 1.3, '#bfa77a', x, 1.7, -3.5));
  const ships = [];
  const spots = [[-5.2, 1.6], [-1.6, 3.0], [2.0, 1.4], [5.4, 2.8]];
  spots.forEach(([x, z], k) => {
    const gal = makeGalley(ctx, { sail: k % 2 ? '#f8f9fa' : '#d62828' });
    gal.group.position.set(x, 0.05, z);
    gal.group.rotation.y = 0.15 * (k % 2 ? 1 : -1);
    gal.group.scale.setScalar(0.78);
    heroGroup.add(gal.group);
    ships.push({ gal, k, x, z });
  });
  return (t) => {
    for (const s of ships) {
      s.gal.group.position.y = 0.05 + Math.sin(t * 1.7 + s.k) * 0.07;
      s.gal.group.rotation.z = Math.sin(t * 1.2 + s.k) * 0.05;
      s.gal.group.position.x = s.x + Math.sin(t * 0.4 + s.k) * 0.3;
      s.gal.row(t, 3.0);
    }
  };
}

// === 1915 ÇANAKKALE DIORAMAS ===
function makeNavalMine(ctx, scale = 1.0) {
  const { THREE, toonMat } = ctx;
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.SphereGeometry(0.38 * scale, 12, 10), toonMat('#2b303a'));
  body.castShadow = true;
  g.add(body);
  const hornMat = toonMat('#e63946');
  const dirs = [[1,0,0],[-1,0,0],[0,1,0],[0,0,1],[0,0,-1],[0.7,0.7,0],[-0.7,0.7,0]];
  for (const [dx, dy, dz] of dirs) {
    const h = new THREE.Mesh(new THREE.CylinderGeometry(0.05 * scale, 0.07 * scale, 0.28 * scale, 6), hornMat);
    h.position.set(dx * 0.42 * scale, dy * 0.42 * scale, dz * 0.42 * scale);
    h.lookAt(dx * 2, dy * 2, dz * 2);
    h.rotateX(Math.PI / 2);
    g.add(h);
  }
  return g;
}

function makeBattleship(ctx, opts = {}) {
  const { THREE, tbox, tcyl } = ctx;
  const g = new THREE.Group();
  const hull = opts.hull || '#5c677d';
  const deck = opts.deck || '#7c8798';
  g.add(tbox(5.6, 0.85, 1.45, hull, 0, 0.42, 0));
  g.add(tbox(5.8, 0.14, 1.55, deck, 0, 0.9, 0));
  g.add(tbox(2.2, 0.75, 1.15, deck, 0.2, 1.32, 0));
  // Bridge + twin smokestacks
  g.add(tbox(0.8, 0.95, 0.85, hull, 1.1, 2.0, 0));
  g.add(tcyl(0.24, 0.26, 1.6, 10, '#343a40', 0.25, 2.35, 0));
  g.add(tcyl(0.24, 0.26, 1.5, 10, '#343a40', -0.55, 2.3, 0));
  // Front & rear turrets
  g.add(tbox(0.8, 0.42, 0.72, '#495057', 2.0, 1.15, 0));
  g.add(tbox(1.3, 0.12, 0.12, '#212529', 2.75, 1.22, -0.14));
  g.add(tbox(1.3, 0.12, 0.12, '#212529', 2.75, 1.22, 0.14));
  g.add(tbox(0.8, 0.42, 0.72, '#495057', -1.85, 1.15, 0));
  g.add(tbox(1.2, 0.12, 0.12, '#212529', -2.55, 1.22, 0));
  // Mast
  g.add(tcyl(0.06, 0.08, 2.8, 8, '#343a40', 1.1, 3.2, 0));
  return g;
}

function nusratMines(ctx) {
  const { THREE, heroGroup, tbox, tcyl, toonMat } = ctx;
  const water = makeWater(THREE, toonMat, 28, 14, '#1b4965');
  water.position.set(0, 0.04, 0.5);
  heroGroup.add(water);
  // Distant strait cliffs flanking Erenköy Bay
  heroGroup.add(tbox(7.5, 2.4, 3.6, '#3d5a45', -9.2, 1.2, -3.5));
  heroGroup.add(tbox(7.5, 2.8, 3.6, '#354f3d', 9.2, 1.4, -3.5));
  // Moon + sweeping searchlight beam from shore
  const moon = new THREE.Mesh(new THREE.SphereGeometry(0.65, 16, 12), new THREE.MeshBasicMaterial({ color: 0xfff3bf }));
  moon.position.set(-5.8, 6.2, -5.0);
  moon.userData.skipNd = true;
  heroGroup.add(moon);
  const beam = new THREE.Mesh(
    new THREE.ConeGeometry(1.6, 8.5, 12, 1, true),
    new THREE.MeshBasicMaterial({ color: 0xffe066, transparent: true, opacity: 0.22, side: THREE.DoubleSide })
  );
  beam.position.set(6.5, 3.5, -2.2);
  beam.rotation.z = 0.85;
  beam.userData.skipNd = true;
  heroGroup.add(beam);

  // Small stealth minelayer ship Nusrat (black hull, white cabin, red-banded smokestack, Turkish flag)
  const nusrat = new THREE.Group();
  nusrat.add(tbox(3.4, 0.65, 1.05, '#2b303a', 0, 0.35, 0));
  nusrat.add(tbox(1.3, 0.65, 0.85, '#f1f3f5', 0.25, 0.95, 0));
  nusrat.add(tcyl(0.18, 0.2, 1.25, 10, '#212529', -0.2, 1.65, 0));
  nusrat.add(tcyl(0.19, 0.19, 0.25, 10, '#c92a2a', -0.2, 1.85, 0));
  nusrat.add(tcyl(0.04, 0.05, 1.8, 6, '#adb5bd', 0.75, 1.8, 0));
  nusrat.add(tbox(0.65, 0.4, 0.04, '#c92a2a', -1.55, 1.15, 0));
  nusrat.position.set(1.5, 0.05, 0.6);
  heroGroup.add(nusrat);

  // Line of 7 bobbing contact mines laid parallel to shore behind Nusrat
  const mines = [];
  for (let i = 0; i < 7; i++) {
    const m = makeNavalMine(ctx, 0.85);
    const mx = -6.2 + i * 1.45;
    const mz = 2.2 - (i % 2) * 0.45;
    m.position.set(mx, 0.22, mz);
    heroGroup.add(m);
    mines.push({ m, i, mx });
  }
  return (t) => {
    nusrat.position.x = 1.5 + Math.sin(t * 0.45) * 1.4;
    nusrat.position.y = 0.05 + Math.sin(t * 2.1) * 0.06;
    nusrat.rotation.z = Math.sin(t * 1.6) * 0.04;
    beam.rotation.z = 0.85 + Math.sin(t * 0.9) * 0.28;
    for (const mn of mines) {
      mn.m.position.y = 0.22 + Math.sin(t * 2.3 + mn.i * 0.9) * 0.09;
      mn.m.rotation.y = t * 0.6 + mn.i;
    }
  };
}

function dardanellesFleet(ctx) {
  const { THREE, heroGroup, tbox, toonMat } = ctx;
  const water = makeWater(THREE, toonMat, 28, 14, '#2b7bb9');
  water.position.set(0, 0.04, 0.6);
  heroGroup.add(water);
  // 2 giant dreadnought battleships + explosion fire/smoke on the left ship (Bouvet/Ocean!)
  const shipL = makeBattleship(ctx, { hull: '#4a5568', deck: '#718096' });
  shipL.position.set(-3.4, 0.05, -0.4);
  shipL.rotation.y = 0.22;
  heroGroup.add(shipL);

  const shipR = makeBattleship(ctx, { hull: '#5c677d', deck: '#8d99ae' });
  shipR.position.set(3.6, 0.05, 0.8);
  shipR.rotation.y = -0.18;
  shipR.scale.setScalar(0.92);
  heroGroup.add(shipR);

  // Glowing cartoon explosion fireball + dark smoke plumes above hit battleship
  const fireMat = new THREE.MeshBasicMaterial({ color: 0xff922b });
  const fire = new THREE.Mesh(new THREE.SphereGeometry(0.95, 14, 12), fireMat);
  fire.position.set(-2.9, 2.0, -0.1);
  heroGroup.add(fire);
  const smokes = [0, 1, 2].map((i) => {
    const s = new THREE.Mesh(new THREE.SphereGeometry(0.75 + i * 0.2, 12, 10), toonMat('#343a40'));
    heroGroup.add(s);
    return { s, i };
  });
  // Mines floating in foreground
  const m1 = makeNavalMine(ctx, 0.9);
  m1.position.set(0.3, 0.22, 3.1);
  const m2 = makeNavalMine(ctx, 0.85);
  m2.position.set(-4.6, 0.22, 2.8);
  heroGroup.add(m1, m2);

  return (t) => {
    shipL.rotation.z = -0.18 - Math.sin(t * 1.4) * 0.05;
    shipL.position.y = -0.15 + Math.sin(t * 1.5) * 0.05;
    shipR.position.y = 0.05 + Math.sin(t * 1.8 + 1) * 0.06;
    const pulse = 0.85 + 0.25 * Math.sin(t * 9.0);
    fire.scale.setScalar(pulse);
    for (const sm of smokes) {
      const cyc = ((t * 0.55 + sm.i * 0.33) % 1);
      sm.s.position.set(-2.9 + cyc * 0.9, 2.4 + cyc * 2.8, -0.1);
      sm.s.scale.setScalar(0.55 + cyc * 0.9);
    }
    m1.position.y = 0.22 + Math.sin(t * 2.2) * 0.08;
    m2.position.y = 0.22 + Math.cos(t * 2.0) * 0.08;
  };
}

function mecidiyeBastion(ctx) {
  const { THREE, heroGroup, tbox, tcyl, toonMat } = ctx;
  // Rumeli Mecidiye Tabyası stone bastion + sandbags + 240mm Krupp coastal gun + broken crane + brass shells
  heroGroup.add(tbox(18, 2.2, 2.6, '#a69478', 0, 1.1, -1.6));
  heroGroup.add(tbox(18, 0.45, 2.8, '#8d7d64', 0, 2.35, -1.6));
  // Sandbag rows on parapet
  for (let i = -7; i <= 7; i += 1.2) {
    heroGroup.add(tbox(0.95, 0.42, 0.72, '#c9b48a', i, 2.75, -0.6));
  }
  // Giant 240mm coastal artillery cannon aiming toward the strait
  const gun = new THREE.Group();
  gun.add(tbox(2.6, 1.25, 1.8, '#495057', 0, 0.65, 0));
  const barrel = tcyl(0.38, 0.52, 5.2, 18, '#343a40', 1.4, 1.65, 0);
  barrel.rotation.z = Math.PI / 2 - 0.18;
  gun.add(barrel);
  gun.position.set(-1.6, 2.2, -1.4);
  heroGroup.add(gun);

  // Broken hoist crane arm dangling beside the cannon
  heroGroup.add(tcyl(0.14, 0.16, 3.6, 10, '#6c757d', -4.8, 3.9, -1.2));
  const brokenArm = tbox(2.2, 0.18, 0.18, '#495057', -3.9, 5.1, -1.2);
  brokenArm.rotation.z = -0.58;
  heroGroup.add(brokenArm);

  // Stacked gleaming 215kg brass shells on right bastion platform
  for (const sx of [3.4, 4.3, 5.2]) {
    heroGroup.add(tcyl(0.28, 0.30, 1.25, 14, '#d4a017', sx, 3.05, -1.3));
    const tip = new THREE.Mesh(new THREE.ConeGeometry(0.28, 0.52, 14), toonMat('#b85d19'));
    tip.position.set(sx, 3.92, -1.3);
    heroGroup.add(tip);
  }
  // Turkish flag flying behind bastion
  heroGroup.add(tcyl(0.06, 0.07, 4.2, 8, '#dee2e6', 6.8, 4.2, -2.4));
  const flag = tbox(1.5, 0.92, 0.05, '#c92a2a', 7.58, 5.75, -2.4);
  heroGroup.add(flag);

  // Cannon firing flash + smoke puff
  const flash = new THREE.Mesh(new THREE.SphereGeometry(0.75, 12, 10), new THREE.MeshBasicMaterial({ color: 0xffd43b }));
  const puff = new THREE.Mesh(new THREE.SphereGeometry(0.85, 12, 10), toonMat('#f1f3f5'));
  heroGroup.add(flash, puff);

  return (t) => {
    flag.rotation.y = Math.sin(t * 3.0) * 0.25;
    const cyc = (t % 3.5) / 3.5;
    gun.position.x = -1.6 - (cyc < 0.1 ? (0.1 - cyc) * 4.5 : 0);
    flash.visible = cyc < 0.14;
    flash.position.set(2.7, 4.35, -1.4);
    flash.scale.setScalar(0.8 + cyc * 4.5);
    puff.visible = cyc < 0.55;
    puff.position.set(2.9 + cyc * 3.6, 4.5 + cyc * 1.4, -1.4);
    puff.scale.setScalar(0.5 + cyc * 1.5);
  };
}

function canakkaleMonument(ctx) {
  const { THREE, heroGroup, tbox, tcyl, toonMat } = ctx;
  const water = makeWater(THREE, toonMat, 28, 9, '#2b7bb9');
  water.position.set(0, 0.04, 2.2);
  heroGroup.add(water);
  // Golden-hour hill + iconic 4-pillar Çanakkale Şehitler Abidesi
  heroGroup.add(tbox(18, 1.5, 5.5, '#5b8c42', 0, 0.75, -2.4));
  const stone = '#e9e2d0';
  for (const [px, pz] of [[-1.35, -1.6], [1.35, -1.6], [-1.35, -3.4], [1.35, -3.4]]) {
    heroGroup.add(tbox(0.82, 4.6, 0.82, stone, px, 3.8, pz));
  }
  heroGroup.add(tbox(4.2, 0.85, 3.2, stone, 0, 6.25, -2.5));
  // Large Turkish flag waving proudly beside monument
  heroGroup.add(tcyl(0.07, 0.08, 6.2, 8, '#f8f9fa', -5.6, 4.5, -2.2));
  const flag = tbox(2.1, 1.3, 0.06, '#c92a2a', -4.52, 6.85, -2.2);
  heroGroup.add(flag);
  const sunOrb = new THREE.Mesh(new THREE.SphereGeometry(1.4, 20, 14), new THREE.MeshBasicMaterial({ color: 0xffd166 }));
  sunOrb.position.set(5.8, 5.2, -6.5);
  sunOrb.userData.skipNd = true;
  heroGroup.add(sunOrb);
  return (t) => {
    flag.rotation.y = Math.sin(t * 2.6) * 0.28;
    sunOrb.position.y = 5.2 + Math.sin(t * 0.7) * 0.15;
  };
}

// === 1630'LAR HEZÂRFEN & LAGÂRİ DIORAMAS ===
function galataFlight(ctx) {
  const { THREE, heroGroup, tbox, tcyl, toonMat } = ctx;
  // Bosphorus water + iconic Galata Tower on left + Uskudar hill on right + soaring winged glider!
  const water = makeWater(THREE, toonMat, 28, 12, '#2d82c4');
  water.position.set(0, 0.04, 1.0);
  heroGroup.add(water);
  // Galata shore + Tower on left
  heroGroup.add(tbox(6.5, 1.2, 5.2, '#6b8e4e', -6.8, 0.6, -1.8));
  heroGroup.add(tcyl(1.15, 1.3, 5.8, 16, '#c9b48a', -5.8, 4.0, -1.5));
  heroGroup.add(tcyl(1.42, 1.38, 0.35, 16, '#8b6b45', -5.8, 6.95, -1.5));
  const roof = new THREE.Mesh(new THREE.ConeGeometry(1.38, 2.2, 16), toonMat('#5c677d'));
  roof.position.set(-5.8, 8.2, -1.5);
  roof.castShadow = true;
  heroGroup.add(roof);
  // Uskudar hillside + mosque silhouette on right
  heroGroup.add(tbox(7.2, 1.6, 5.2, '#5b9445', 7.2, 0.8, -2.0));
  heroGroup.add(tbox(2.4, 1.5, 1.8, '#e9e2d0', 6.8, 2.3, -2.2));
  const dome = new THREE.Mesh(new THREE.SphereGeometry(1.0, 16, 10, 0, Math.PI * 2, 0, Math.PI / 2), toonMat('#8d99ae'));
  dome.position.set(6.8, 3.05, -2.2);
  heroGroup.add(dome);
  // Soaring 3D Hezarfen glider moving across the Bosphorus
  const flyer = new THREE.Group();
  flyer.add(tbox(0.55, 0.35, 1.2, '#9b111e', 0, 0, 0));
  const wingL = tbox(2.0, 0.08, 0.85, '#a66b38', -1.2, 0.05, 0);
  const wingR = tbox(2.0, 0.08, 0.85, '#a66b38', 1.2, 0.05, 0);
  flyer.add(wingL, wingR);
  heroGroup.add(flyer);
  return (t) => {
    const u = (t * 0.11) % 1;
    flyer.position.set(-4.6 + u * 10.6, 6.6 - u * 3.4 + Math.sin(t * 3.5) * 0.22, -0.2);
    flyer.rotation.z = -0.15 + Math.sin(t * 2.8) * 0.08;
    wingL.rotation.z = Math.sin(t * 5.0) * 0.16;
    wingR.rotation.z = -Math.sin(t * 5.0) * 0.16;
  };
}

function okmeydaniTest(ctx) {
  const { THREE, heroGroup, tbox, tcyl, toonMat } = ctx;
  // Okmeydanı windy training ground + wooden launch minber/ramp + flapping wind pennants
  heroGroup.add(tbox(18, 0.5, 7, '#5b9445', 0, 0.25, -2.0));
  heroGroup.add(tbox(3.4, 2.6, 2.4, '#8b5a2b', -3.6, 1.5, -1.8));
  heroGroup.add(tbox(2.8, 0.22, 2.6, '#a66b38', -3.6, 2.9, -1.8));
  // Wind poles with red banners streaming in the lodos wind
  const flags = [];
  for (const fx of [-6.4, -0.5, 4.8]) {
    heroGroup.add(tcyl(0.08, 0.09, 4.8, 8, '#5c3a1a', fx, 2.5, -2.4));
    const fl = tbox(1.7, 0.55, 0.05, '#e63946', fx + 0.88, 4.5, -2.4);
    heroGroup.add(fl);
    flags.push({ fl, fx });
  }
  // Test wing frame perched on wooden stand
  const testWing = new THREE.Group();
  testWing.position.set(1.8, 2.4, -1.2);
  testWing.add(tbox(3.6, 0.12, 1.1, '#a66b38', 0, 0, 0));
  testWing.add(tbox(0.22, 2.0, 0.22, '#6f4518', 0, -1.0, 0));
  heroGroup.add(testWing);
  return (t) => {
    for (const f of flags) f.fl.rotation.y = 0.2 + Math.sin(t * 5.2 + f.fx) * 0.28;
    testWing.rotation.z = Math.sin(t * 3.1) * 0.18;
    testWing.rotation.x = Math.cos(t * 2.3) * 0.12;
  };
}

function lagariRocket(ctx) {
  const { THREE, heroGroup, tbox, tcyl, toonMat } = ctx;
  // Sarayburnu night sea + wooden pier + 7-nozzle conical Ottoman gunpowder rocket blasting skyward!
  const water = makeWater(THREE, toonMat, 28, 12, '#1b4965');
  water.position.set(0, 0.04, 1.0);
  heroGroup.add(water);
  heroGroup.add(tbox(7.5, 0.6, 3.2, '#6f4518', 0, 0.35, -1.2));
  // Sarayburnu palace pavilion on right
  heroGroup.add(tbox(4.6, 2.6, 2.6, '#d8c39e', 6.4, 1.4, -2.2));
  const pavDome = new THREE.Mesh(new THREE.SphereGeometry(1.7, 16, 10, 0, Math.PI * 2, 0, Math.PI / 2), toonMat('#5c677d'));
  pavDome.position.set(6.4, 2.75, -2.2);
  heroGroup.add(pavDome);
  // Moon & festival sparks
  const moon = new THREE.Mesh(new THREE.SphereGeometry(0.68, 16, 12), new THREE.MeshBasicMaterial({ color: 0xfff3bf }));
  moon.position.set(-6.0, 6.2, -5.0);
  moon.userData.skipNd = true;
  heroGroup.add(moon);
  // 7-nozzle conical gunpowder rocket
  const rocket = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.85, 2.6, 14), toonMat('#c92a2a'));
  body.castShadow = true;
  rocket.add(body);
  const cone = new THREE.Mesh(new THREE.ConeGeometry(0.38, 0.95, 14), toonMat('#ffd60a'));
  cone.position.set(0, 1.75, 0);
  rocket.add(cone);
  // 7 small booster nozzles around base
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    rocket.add(tcyl(0.14, 0.18, 0.65, 8, '#8b5a2b', Math.cos(a) * 0.72, -1.25, Math.sin(a) * 0.72));
  }
  const flame = new THREE.Mesh(new THREE.ConeGeometry(0.68, 2.2, 12), new THREE.MeshBasicMaterial({ color: 0xff922b }));
  flame.rotation.x = Math.PI;
  flame.position.set(0, -2.35, 0);
  rocket.add(flame);
  rocket.position.set(-0.5, 2.2, -1.0);
  heroGroup.add(rocket);

  const puffs = [0, 1, 2, 3].map((i) => {
    const p = new THREE.Mesh(new THREE.SphereGeometry(0.65, 10, 8), toonMat('#f1f3f5'));
    heroGroup.add(p);
    return { p, i };
  });
  return (t) => {
    const cyc = (t * 0.24) % 1;
    const alt = 1.8 + cyc * cyc * 6.8;
    rocket.position.set(-0.5 + Math.sin(t * 14) * 0.05, alt, -1.0);
    rocket.rotation.z = -0.14 * cyc;
    flame.scale.set(1, 0.8 + 0.35 * Math.sin(t * 24), 1);
    for (const P of puffs) {
      const k = (t * 0.9 + P.i * 0.25) % 1;
      P.p.position.set(-0.5 + (P.i - 1.5) * 0.55 * k, Math.max(0.5, alt - 2.0 - k * 2.2), -1.0);
      P.p.scale.setScalar(0.5 + k * 1.1);
    }
  };
}

function bosphorusPhysics(ctx) {
  const { THREE, heroGroup, tbox, tcyl, toonMat } = ctx;
  // Cross-section diagram: Galata 128m (left) -> 3,358m Bosphorus -> Uskudar 45m (right) + dotted glide arc!
  const water = makeWater(THREE, toonMat, 26, 10, '#2b7bb9');
  water.position.set(0, 0.04, 1.0);
  heroGroup.add(water);
  // Left Galata pillar (tall: 128m scale)
  heroGroup.add(tbox(3.2, 2.2, 2.6, '#6b8e4e', -6.4, 1.1, -1.6));
  heroGroup.add(tcyl(0.85, 0.95, 3.6, 14, '#c9b48a', -6.4, 4.0, -1.6));
  const roof = new THREE.Mesh(new THREE.ConeGeometry(1.0, 1.4, 14), toonMat('#5c677d'));
  roof.position.set(-6.4, 6.45, -1.6);
  heroGroup.add(roof);
  // Right Uskudar hill (45m scale)
  heroGroup.add(tbox(4.6, 1.8, 2.6, '#5b9445', 6.4, 0.9, -1.6));
  // 14 golden/red trajectory orbs comparing 41:1 legendary glide vs 15:1 modern delta wing!
  const orbs = [];
  for (let i = 0; i < 12; i++) {
    const u = i / 11;
    const o = new THREE.Mesh(new THREE.SphereGeometry(0.18, 10, 8), new THREE.MeshBasicMaterial({ color: 0xffd60a }));
    o.position.set(-5.4 + u * 10.8, 5.8 - u * 3.6 + Math.sin(u * Math.PI) * 0.45, -1.2);
    heroGroup.add(o);
    orbs.push({ o, i });
  }
  // Steep red 15:1 physics drop line splashing mid-strait
  for (let i = 0; i < 7; i++) {
    const u = i / 6;
    const r = new THREE.Mesh(new THREE.SphereGeometry(0.16, 10, 8), new THREE.MeshBasicMaterial({ color: 0xe63946 }));
    r.position.set(-5.4 + u * 5.2, 5.6 - u * 5.2, -0.7);
    heroGroup.add(r);
  }
  return (t) => {
    for (const O of orbs) {
      const s = 0.75 + 0.35 * Math.sin(t * 4.5 - O.i * 0.55);
      O.o.scale.setScalar(s);
    }
  };
}

export const EXTRA_HEROES = {
  halic_chain: halicChain,
  ships_hill: shipsHill,
  city_walls: cityWalls,
  golden_horn_fleet: goldenHornFleet,
  nusrat_mines: nusratMines,
  dardanelles_fleet: dardanellesFleet,
  mecidiye_bastion: mecidiyeBastion,
  canakkale_monument: canakkaleMonument,
  galata_flight: galataFlight,
  okmeydani_test: okmeydaniTest,
  lagari_rocket: lagariRocket,
  bosphorus_physics: bosphorusPhysics,
};
