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

export const EXTRA_HEROES = {
  halic_chain: halicChain,
  ships_hill: shipsHill,
  city_walls: cityWalls,
  golden_horn_fleet: goldenHornFleet,
};
