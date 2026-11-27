// engine/kit/story_runtime.js — 10-Scene Seamless-Loop Story Runtime + 3D HeroProp Library
// Drives AKILALMAZ v9–v20 exact 10-scene narrative rhythm synced to spoken word timestamps:
//   s0 (hook x=0) -> s1 (flash to final board x=180 + badge) -> s2 (? mark x=0)
//   -> s3 (year card + intro x=0) -> s4 (Board 1 x=60 + badge)
//   -> s5/s6 (Board 2 x=120 + badge) -> s7/s8 (Final Board 3 x=180 + record badge + sparkles)
//   -> s9 (seamless loop return to exact s0 camera & framing!)

import * as THREE from '../lib/three.module.js';
import {
  FPS,
  createToonStage,
  easeOutCubic,
  easeOutBack,
  easeInOutQuad,
  lerp,
  lerpVec,
} from './toonbase.js';
import { EXTRA_HEROES } from './heroes_extra.js';

/**
 * Builds story-specific 3D heroProps at Zone 0 (z = -8.6).
 * Returns an animate(t) callback for living 3D motion on every frame.
 */
function buildHeroProp(stage, heroSpec, group = null) {
  const { tbox, tcyl, toonMat } = stage;
  const heroGroup = group || stage.heroGroup;
  const kind = (heroSpec && heroSpec.kind) || 'clock';
  const animators = [];

  if (EXTRA_HEROES[kind]) {
    animators.push(EXTRA_HEROES[kind]({ THREE, heroGroup, tbox, tcyl, toonMat, spec: heroSpec }));
    return (t) => {
      for (const fn of animators) fn(t);
    };
  }

  if (kind === 'reactor') {
    // Giant 3D Chicago Pile-1 Graphite Nuclear Reactor + Overhead Safety Rope & Red Fire Axe!
    // Concrete stadium floor plinth
    heroGroup.add(tbox(7.8, 0.5, 4.6, '#6c757d', 0, 0.25, 0));

    // Layered dark graphite octagonal/stepped reactor pile (400 tons of black graphite bricks!)
    const g1 = tbox(6.4, 1.35, 3.6, '#2b2d38', 0, 1.15, 0);
    const g2 = tbox(5.4, 1.35, 3.1, '#343a46', 0, 2.45, 0);
    const g3 = tbox(4.2, 1.15, 2.5, '#2b2d38', 0, 3.65, 0);
    heroGroup.add(g1, g2, g3);

    // Bright yellow/black radiation warning stripes on reactor front
    heroGroup.add(tbox(4.6, 0.34, 0.14, '#ffd60a', 0, 2.45, 1.56));
    heroGroup.add(tbox(1.1, 0.36, 0.16, '#1b141c', -1.4, 2.45, 1.58));
    heroGroup.add(tbox(1.1, 0.36, 0.16, '#1b141c', 1.4, 2.45, 1.58));

    // Glowing green uranium/neutron core windows on the reactor front
    const coreMat = new THREE.MeshBasicMaterial({ color: 0x51cf66 });
    const cores = [];
    for (const cx of [-1.5, 0, 1.5]) {
      const w = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.62, 0.16), coreMat);
      w.position.set(cx, 1.25, 1.82);
      heroGroup.add(w);
      cores.push(w);
    }

    // Control rods sticking out the top (gently rising/falling)
    const rods = [];
    for (const rx of [-1.1, 0, 1.1]) {
      const rod = tcyl(0.14, 0.14, 2.2, 12, '#adb5bd', rx, 4.9, 0);
      const cap = tcyl(0.22, 0.22, 0.28, 12, '#e63946', rx, 6.05, 0);
      heroGroup.add(rod, cap);
      rods.push({ rod, cap, baseY: 4.9, phase: rx * 1.3 });
    }

    // Wooden safety gantry frame above reactor + taut yellow rope + giant dangling red SCRAM axe!
    heroGroup.add(tbox(0.28, 7.6, 0.28, '#6f4518', -3.5, 3.8, 0.8));
    heroGroup.add(tbox(0.28, 7.6, 0.28, '#6f4518', 3.5, 3.8, 0.8));
    heroGroup.add(tbox(7.6, 0.34, 0.34, '#8b5a2b', 0, 7.55, 0.8));

    // Vertical yellow safety rope from gantry down into center control rod
    const rope = tcyl(0.06, 0.06, 2.6, 8, '#ffd60a', 0, 6.2, 0.8);
    heroGroup.add(rope);

    // Oversized swinging 3D Red Fire Axe suspended beside the rope (iconic visual hook!)
    const axePivot = new THREE.Group();
    axePivot.position.set(1.85, 7.35, 1.05);
    const axeHandle = tbox(0.18, 2.1, 0.18, '#a66b38', 0, -1.05, 0);
    const axeHead = tbox(0.95, 0.68, 0.24, '#e03131', -0.35, -1.85, 0);
    const axeEdge = tbox(0.22, 0.72, 0.26, '#f1f3f5', -0.82, -1.85, 0);
    axePivot.add(axeHandle, axeHead, axeEdge);
    heroGroup.add(axePivot);

    // Floating glowing atomic rings / neutron orbs orbiting softly
    const orbs = [];
    for (let i = 0; i < 4; i++) {
      const orb = new THREE.Mesh(
        new THREE.SphereGeometry(0.2, 12, 10),
        new THREE.MeshBasicMaterial({ color: i % 2 === 0 ? 0x69db7c : 0xffd43b })
      );
      heroGroup.add(orb);
      orbs.push({ orb, i });
    }

    animators.push((t) => {
      // Rods pulse smoothly like live reactor control
      for (const r of rods) {
        const dy = Math.sin(t * 2.2 + r.phase) * 0.24;
        r.rod.position.y = r.baseY + dy;
        r.cap.position.y = r.baseY + 1.15 + dy;
      }
      // Axe gently swings like a pendulum ready to cut the rope!
      axePivot.rotation.z = Math.sin(t * 2.6) * 0.16;
      // Core glow brightness pulse
      const glow = 0.72 + 0.28 * Math.sin(t * 4.5);
      coreMat.color.setRGB(0.28 * glow, 0.88 * glow, 0.42 * glow);
      // Orbiting neutron orbs
      for (const o of orbs) {
        const a = t * 1.4 + o.i * (Math.PI / 2);
        o.orb.position.set(Math.cos(a) * 3.1, 4.4 + Math.sin(a * 2) * 0.6, Math.sin(a) * 1.4 + 1.1);
      }
    });
  } else if (kind === 'clock') {
    // Classic v20 giant golden stopwatch / clock
    const ring = tcyl(3.7, 3.7, 0.7, 32, '#f2b705', 0, 4.1, 0);
    ring.rotation.x = Math.PI / 2;
    const face = tcyl(3.1, 3.1, 0.76, 32, '#f9e596', 0, 4.1, 0.02);
    face.rotation.x = Math.PI / 2;
    const knob = tcyl(0.68, 0.68, 0.9, 16, '#f2b705', 0, 8.1, 0);
    heroGroup.add(ring, face, knob);

    const handMin = new THREE.Group();
    handMin.position.set(0, 4.1, 0.5);
    handMin.add(tbox(0.28, 2.2, 0.18, '#d62828', 0, 1.0, 0));
    const handHr = new THREE.Group();
    handHr.position.set(0, 4.1, 0.46);
    handHr.add(tbox(1.7, 0.28, 0.18, '#1d2d44', 0.78, 0, 0));
    heroGroup.add(handMin, handHr);

    animators.push((t) => {
      handMin.rotation.z = -t * 0.45;
      handHr.rotation.z = -t * 0.06;
    });
  } else if (kind === 'sariyer_lion') {
    // Sarıyer Uskumruköy Forest + Giant Stylized 3D Lion Emblem + Patrolling Thermal Search Drone + CCTV Pole!
    // Pine trees flanking the Belgrad Forest backdrop
    for (const [tx, tz, sc] of [[-4.2, -0.4, 1.0], [4.1, -0.3, 1.1], [-2.8, -1.6, 0.85], [2.9, -1.5, 0.9]]) {
      heroGroup.add(tcyl(0.28 * sc, 0.34 * sc, 1.8 * sc, 10, '#6f4518', tx, 0.9 * sc, tz));
      const c1 = new THREE.Mesh(new THREE.ConeGeometry(1.35 * sc, 2.4 * sc, 10), toonMat('#2b7a3d'));
      c1.position.set(tx, 2.5 * sc, tz);
      c1.castShadow = true;
      const c2 = new THREE.Mesh(new THREE.ConeGeometry(1.05 * sc, 2.1 * sc, 10), toonMat('#37964d'));
      c2.position.set(tx, 3.8 * sc, tz);
      c2.castShadow = true;
      heroGroup.add(c1, c2);
    }

    // Giant 3D Golden Lion Silhouette / Medallion looming behind the trees (the "phantom lion"!)
    const lionGroup = new THREE.Group();
    lionGroup.position.set(0.3, 3.9, 0);
    // Spiky golden mane ring (12 chunky wedges around face)
    const maneDisc = tcyl(3.15, 3.15, 0.52, 16, '#d97706', 0, 0, -0.1);
    maneDisc.rotation.x = Math.PI / 2;
    lionGroup.add(maneDisc);
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2;
      const spike = tbox(0.82, 0.82, 0.56, '#e85d04', Math.cos(a) * 2.9, Math.sin(a) * 2.9, -0.1);
      spike.rotation.z = a + Math.PI / 4;
      lionGroup.add(spike);
    }
    // Lion face disc + ears + eyes + snout
    const faceDisc = tcyl(2.35, 2.35, 0.65, 24, '#f59f00', 0, 0, 0.14);
    faceDisc.rotation.x = Math.PI / 2;
    lionGroup.add(faceDisc);
    for (const sx of [-1.5, 1.5]) {
      const ear = tcyl(0.55, 0.55, 0.5, 16, '#f59f00', sx, 1.85, 0.1);
      ear.rotation.x = Math.PI / 2;
      lionGroup.add(ear);
      const eye = tcyl(0.24, 0.24, 0.25, 12, '#1b141c', sx * 0.52, 0.42, 0.48);
      eye.rotation.x = Math.PI / 2;
      lionGroup.add(eye);
    }
    const snout = tcyl(0.72, 0.82, 0.35, 16, '#ffd89b', 0, -0.45, 0.45);
    snout.rotation.x = Math.PI / 2;
    const nose = tbox(0.58, 0.42, 0.3, '#5c2c16', 0, -0.12, 0.58);
    lionGroup.add(snout, nose);
    heroGroup.add(lionGroup);

    // Tall CCTV Security Camera Pole on right side (the famous camera angle!)
    heroGroup.add(tcyl(0.12, 0.14, 5.2, 10, '#495057', 2.8, 2.6, 1.8));
    const camHead = new THREE.Group();
    camHead.position.set(2.8, 5.25, 1.8);
    camHead.add(tbox(0.95, 0.46, 0.52, '#f1f3f5', -0.3, 0, 0));
    const recLed = new THREE.Mesh(
      new THREE.SphereGeometry(0.12, 10, 8),
      new THREE.MeshBasicMaterial({ color: 0xff2b2b })
    );
    recLed.position.set(-0.78, 0.1, 0.22);
    camHead.add(recLed);
    heroGroup.add(camHead);

    // Patrolling Thermal Search Drone hovering across the sky!
    const drone = new THREE.Group();
    drone.add(tbox(1.15, 0.24, 0.55, '#212529', 0, 0, 0));
    drone.add(tbox(2.1, 0.08, 0.12, '#ffd60a', 0, 0.08, 0));
    const rotorL = tcyl(0.45, 0.45, 0.05, 12, '#adb5bd', -1.0, 0.16, 0);
    const rotorR = tcyl(0.45, 0.45, 0.05, 12, '#adb5bd', 1.0, 0.16, 0);
    const beamMat = new THREE.MeshBasicMaterial({ color: 0xffe066, transparent: true, opacity: 0.32, side: THREE.DoubleSide });
    const beam = new THREE.Mesh(new THREE.ConeGeometry(1.1, 2.6, 12, 1, true), beamMat);
    beam.position.set(0, -1.4, 0);
    drone.add(rotorL, rotorR, beam);
    heroGroup.add(drone);

    animators.push((t) => {
      lionGroup.rotation.z = Math.sin(t * 1.4) * 0.05;
      lionGroup.position.y = 3.9 + Math.sin(t * 2.1) * 0.14;
      camHead.rotation.y = Math.sin(t * 1.8) * 0.38;
      recLed.visible = Math.floor(t * 3.0) % 2 === 0;
      drone.position.set(Math.sin(t * 1.25) * 2.3, 6.7 + Math.cos(t * 2.5) * 0.22, 1.4);
      drone.rotation.z = -Math.cos(t * 1.25) * 0.12;
      rotorL.rotation.y = t * 18;
      rotorR.rotation.y = -t * 18;
    });
  } else {
    // Generic monumental pedestal + glowing emblem
    heroGroup.add(tbox(5.4, 2.4, 3.0, heroSpec?.colorA || '#495057', 0, 1.2, 0));
    const topObj = tcyl(1.8, 2.2, 3.2, 16, heroSpec?.colorB || '#ffd60a', 0, 4.0, 0);
    heroGroup.add(topObj);
    animators.push((t) => {
      topObj.rotation.y = t * 0.6;
    });
  }

  return (t) => {
    for (const fn of animators) fn(t);
  };
}

/**
 * Mounts an entire 10-scene episode onto window.renderFrame(f) & sets window.ready = true.
 */
export function bootEpisode(episode) {
  try {
    const canvas = document.getElementById('c');
    const stageCfg = Object.assign({}, episode.stage || {});
    if (episode.width) stageCfg.width = episode.width;
    if (episode.height) stageCfg.height = episode.height;
    const stage = createToonStage(canvas, stageCfg);
    const heroAnimators = [buildHeroProp(stage, episode.heroProp || { kind: 'reactor' })];
    for (const oz of stage.outdoorHeroGroups || []) {
      heroAnimators.push(buildHeroProp(stage, oz.spec, oz.group));
    }
    const animateHero = (t) => {
      for (const fn of heroAnimators) fn(t);
    };
    const defaultSky = [
      stageCfg.skyTop || '#d4a34a',
      stageCfg.skyMid || '#f7d060',
      stageCfg.skyBot || '#f0b429',
      stageCfg.fogColor || '#f2c652',
      1.0,
    ];
    let lastSkyKey = '';

    // Create 2D character cards
    const cards = {};
    for (const ch of episode.characters || []) {
      cards[ch.id] = stage.createCard(ch);
    }

    // Create floating FX cards declared in episode.fx
    const fxMeshes = {};
    const fxSpec = episode.fx || {};
    if (fxSpec.year) {
      fxMeshes.year = stage.fxFactory.year(fxSpec.year.year, fxSpec.year.place);
    }
    if (fxSpec.mark) {
      fxMeshes.mark = stage.fxFactory.mark(fxSpec.mark.symbol || '?', fxSpec.mark.bg || '#ffd60a');
    }
    for (const [k, b] of Object.entries(fxSpec.badges || {})) {
      fxMeshes[k] = stage.fxFactory.badge(b.top, b.bottom, b.bg, b.fg);
    }
    // 4 golden sparkles for finale scene (matches v15/v20!)
    const sparkles = [0, 1, 2, 3].map((i) => stage.fxFactory.sparkle(i % 2 === 0 ? '#ffd60a' : '#fff3bf'));

    const scenes = episode.scenes || [];
    const totalFrames = episode.totalFrames || Math.ceil((episode.duration || 48) * FPS);

    window.totalFrames = totalFrames;
    window.renderFrame = function renderFrame(frameIdx) {
      const f = Math.max(0, Math.min(totalFrames - 1, frameIdx | 0));
      const t = f / FPS;

      // Locate active scene segment
      let sc = scenes[scenes.length - 1];
      let scIdx = scenes.length - 1;
      for (let i = 0; i < scenes.length; i++) {
        if (t >= scenes[i].t0 && t < scenes[i].t1) {
          sc = scenes[i];
          scIdx = i;
          break;
        }
      }

      const dur = Math.max(0.05, sc.t1 - sc.t0);
      const localT = Math.max(0, t - sc.t0);
      const u = Math.min(1, localT / dur);
      const uSmooth = easeInOutQuad(u);

      // White flash cut at scene starts (sharp 0.14s decay just like v2/v15/v20!)
      let flash = 0.0;
      if (sc.flash !== false && scIdx > 0 && localT < 0.15) {
        flash = Math.pow(1 - localT / 0.15, 1.8) * (sc.flashStrength ?? 0.85);
      }

      // Camera interpolation
      const camPos = lerpVec(sc.camA, sc.camB || sc.camA, uSmooth);
      const camLook = lerpVec(sc.lookA, sc.lookB || sc.lookA, uSmooth);
      // Subtle handheld breathing micro-sway so frame is never frozen
      camPos[0] += Math.sin(t * 1.9) * 0.035;
      camPos[1] += Math.cos(t * 2.3) * 0.025;

      // Per-scene sky/fog/light override (e.g. night haul) — falls back to stage defaults
      const skyArgs = sc.sky || defaultSky;
      const skyKey = skyArgs.join('|');
      if (skyKey !== lastSkyKey) {
        stage.setSky(...skyArgs);
        lastSkyKey = skyKey;
      }

      // Animate 3D Hero Prop
      animateHero(t);

      // Update Characters
      for (const [cid, card] of Object.entries(cards)) {
        const actor = (sc.actors && sc.actors[cid]) || null;
        if (!actor || actor.hidden) {
          card.update({ hidden: true }, camPos);
          continue;
        }
        const x = actor.x1 !== undefined ? lerp(actor.x, actor.x1, easeOutCubic(u)) : actor.x;
        const z = actor.z1 !== undefined ? lerp(actor.z, actor.z1, easeOutCubic(u)) : actor.z;
        const hop = actor.hop ? Math.abs(Math.sin(t * 7.5)) * actor.hop : 0;
        card.update(
          {
            x,
            y: actor.y || 0,
            z,
            s: actor.s || 1.0,
            face: actor.face || 'neutral',
            armL: actor.armL || 'hang',
            armR: actor.armR || 'hang',
            sweat: Boolean(actor.sweat),
            talk: actor.talk !== undefined ? Boolean(actor.talk) : true,
            propL: actor.propL || null,
            propR: actor.propR || null,
            hop,
            lean: actor.lean || 0,
            shadow: actor.shadow !== false,
            t,
          },
          camPos
        );
      }

      // Update Floating FX Cards
      stage.hideAllFx();
      for (const fxCall of sc.fx || []) {
        const delay = fxCall.delay || 0.12;
        const ft = localT - delay;
        if (ft < 0) continue;
        const pop = easeOutBack(Math.min(1, ft / 0.28));
        const bob = Math.sin(t * 4.5 + (fxCall.phase || 0)) * 0.06;
        const mesh = fxMeshes[fxCall.id];
        if (mesh) {
          const p = [fxCall.pos[0], fxCall.pos[1] + bob, fxCall.pos[2]];
          stage.placeFx(mesh, p, (fxCall.scale || 1.0) * pop, camPos, Math.sin(t * 3.0) * 0.04);
        }
      }

      // Finale golden sparkles (matches v15/v20 s8 around finale badge!)
      if (sc.sparkles) {
        const spBase = sc.sparkles; // [x, y, z]
        const offsets = [
          [-0.95, 0.24, 0.15],
          [0.95, 0.22, 0.15],
          [-0.82, -0.22, 0.18],
          [0.84, -0.20, 0.18],
        ];
        for (let i = 0; i < sparkles.length; i++) {
          const pulse = 0.55 + 0.45 * Math.sin(t * 6.5 + i * 1.55);
          const pos = [
            spBase[0] + offsets[i][0],
            spBase[1] + offsets[i][1] + Math.sin(t * 3.8 + i) * 0.08,
            spBase[2] + offsets[i][2],
          ];
          stage.placeFx(sparkles[i], pos, pulse * 0.85, camPos, t * 1.6 + i);
        }
      }

      // Execute 3-stage post-processing (rtColor -> rtNd -> rtInk 8-tap -> dofScene 6-tap)
      stage.renderPost({
        camPos,
        camLook,
        fov: sc.fov || episode.defaultFov || 40,
        sat: sc.sat ?? 1.08,
        vig: sc.vig ?? 0.34,
        flash,
        focusDist: sc.focusDist ?? 5.4,
        focusRange: sc.focusRange ?? 3.4,
        maxBlur: sc.maxBlur ?? 2.4,
      });
    };

    // Warm-up frame 0 so shaders compile before window.ready = true
    window.renderFrame(0);
    window.ready = true;
  } catch (err) {
    window.__bootError = String(err && err.stack ? err.stack : err);
    console.error(err);
  }
}
