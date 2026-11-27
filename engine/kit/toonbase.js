// engine/kit/toonbase.js — Exact AKILALMAZ v9–v20 3D Toon + 8-tap Ink + 6-tap DoF Engine
// WebGL Canvas: W=540, H=960, 30 FPS, PerspectiveCamera(40, W/H, 0.08, 1500)
// 4 Zones on X-axis (0, 60, 120, 180), 2-tone Cel Gradient, 2D Inked Card (CW=600, CH=1000, CM=2.25)
// 3-Stage Post-Processing: rtColor -> rtNd (normal+depth) -> rtInk (8-tap ink + sat + vig + flash) -> dofScene (6-tap Poisson bokeh)

import * as THREE from '../lib/three.module.js';
import {
  makeGroundTex,
  makeStonePathTex,
  makePlankTex,
  makePlasterTex,
  makeDarkWoodTex,
  paintSign,
  paintBoard,
  makeShadowBlobTex,
  paintFxYear,
  paintFxBadge,
  paintFxMark,
  paintFxSparkle,
} from './paint.js';
import { CW, CH, drawCharacter } from './toon.js';

export const W = 540;
export const H = 960;
export const FPS = 30;
export const CM = 2.25;

// 2-Tone Cel Gradient: [92,92,92,255, 255,255,255,255] (2x1 DataTexture, NearestFilter)
export function makeCelGradient() {
  const data = new Uint8Array([92, 92, 92, 255, 255, 255, 255, 255]);
  const tex = new THREE.DataTexture(data, 2, 1, THREE.RGBAFormat);
  tex.minFilter = THREE.NearestFilter;
  tex.magFilter = THREE.NearestFilter;
  tex.generateMipmaps = false;
  tex.needsUpdate = true;
  return tex;
}

// Normal + Linear-Depth shader for rtNd pass (opaque 3D geometry)
const ND_VERT = `
varying vec3 vNormal;
varying float vDepth;
void main() {
  vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
  vNormal = normalize(normalMatrix * normal);
  vDepth = -mvPos.z;
  gl_Position = projectionMatrix * mvPos;
}
`;

const ND_FRAG = `
varying vec3 vNormal;
varying float vDepth;
void main() {
  vec3 n = normalize(vNormal) * 0.5 + 0.5;
  gl_FragColor = vec4(n, vDepth);
}
`;

// Alpha-discard Normal+Depth shader for 2D Character Cards (cardNd)
const CARD_ND_VERT = `
varying vec2 vUv;
varying vec3 vNormal;
varying float vDepth;
void main() {
  vUv = uv;
  vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
  vNormal = normalize(normalMatrix * normal);
  vDepth = -mvPos.z;
  gl_FragColor;
  gl_Position = projectionMatrix * mvPos;
}
`.replace('  gl_FragColor;\n', '');

const CARD_ND_FRAG = `
uniform sampler2D map;
varying vec2 vUv;
varying vec3 vNormal;
varying float vDepth;
void main() {
  vec4 c = texture2D(map, vUv);
  if (c.a < 0.02) discard;
  vec3 n = normalize(vNormal) * 0.5 + 0.5;
  gl_FragColor = vec4(n, vDepth);
}
`;

// Stage 3a: 8-Tap Normal+Depth Ink Outline + Saturation + Vignette + White Flash (rtInk)
const FULLSCREEN_VERT = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}
`;

const INK_FRAG = `
uniform sampler2D tColor;
uniform sampler2D tNd;
uniform vec2 uTexel;
uniform float uSat;
uniform float uVig;
uniform float uFlash;
varying vec2 vUv;

void main() {
  vec4 col = texture2D(tColor, vUv);
  vec4 nd0 = texture2D(tNd, vUv);
  vec3 n0 = nd0.rgb * 2.0 - 1.0;
  float d0 = nd0.a;

  // 8-tap Sobel/Ring neighbor check for crisp dark cartoon ink outlines
  vec2 offs[8];
  offs[0] = vec2(-1.0,  0.0);
  offs[1] = vec2( 1.0,  0.0);
  offs[2] = vec2( 0.0, -1.0);
  offs[3] = vec2( 0.0,  1.0);
  offs[4] = vec2(-1.0, -1.0);
  offs[5] = vec2( 1.0, -1.0);
  offs[6] = vec2(-1.0,  1.0);
  offs[7] = vec2( 1.0,  1.0);

  float edgeD = 0.0;
  float edgeN = 0.0;
  float scale = 1.15;
  for (int i = 0; i < 8; i++) {
    vec4 ndi = texture2D(tNd, vUv + offs[i] * uTexel * scale);
    float di = ndi.a;
    vec3 ni = ndi.rgb * 2.0 - 1.0;

    // Depth discontinuity (strong silhouette edges)
    float dd = abs(d0 - di) / max(1.0, min(d0, di) * 0.14);
    edgeD = max(edgeD, dd);

    // Normal discontinuity (3D crease & box corner edges)
    if (d0 > 0.05 && di > 0.05 && abs(d0 - di) < 1.2) {
      float dn = length(n0 - ni);
      edgeN = max(edgeN, dn);
    }
  }

  float inkD = smoothstep(0.45, 1.05, edgeD);
  float inkN = smoothstep(0.55, 1.15, edgeN) * 0.85;
  float ink = clamp(max(inkD, inkN), 0.0, 1.0);

  // Subtle saturation boost matching vibrant toon palette
  vec3 rgb = col.rgb;
  float luma = dot(rgb, vec3(0.299, 0.587, 0.114));
  rgb = mix(vec3(luma), rgb, uSat);

  // Ink color: vec3(0.012, 0.01, 0.014) in linear space
  vec3 inkCol = vec3(0.012, 0.01, 0.014);
  rgb = mix(rgb, inkCol, ink * 0.92);

  // Gentle vignette
  vec2 p = vUv - 0.5;
  float vig = 1.0 - dot(p, p) * uVig;
  rgb *= clamp(vig, 0.72, 1.0);

  // White flash cut transition
  rgb = mix(rgb, vec3(1.0), clamp(uFlash, 0.0, 1.0));

  gl_FragColor = vec4(rgb, 1.0);
}
`;

// Stage 3b: 6-Tap Poisson Bokeh DoF + linearToOutputTexel (dofScene)
const DOF_FRAG = `
uniform sampler2D tInk;
uniform sampler2D tNd;
uniform vec2 uTexel;
uniform float uFocusDist;
uniform float uFocusRange;
uniform float uMaxBlur;
varying vec2 vUv;

void main() {
  float d0 = texture2D(tNd, vUv).a;
  // Sky/background pixels have d0 == 0 -> treat as far distance
  float dist = d0 < 0.01 ? 18.0 : d0;
  float coc = clamp((abs(dist - uFocusDist) - uFocusRange) / max(0.5, uFocusRange * 1.4), 0.0, 1.0);
  float radius = coc * uMaxBlur;

  vec3 acc = texture2D(tInk, vUv).rgb;
  float wSum = 1.0;

  if (radius > 0.15) {
    vec2 taps[6];
    taps[0] = vec2( 0.95,  0.12);
    taps[1] = vec2( 0.38,  0.90);
    taps[2] = vec2(-0.56,  0.80);
    taps[3] = vec2(-0.96, -0.18);
    taps[4] = vec2(-0.34, -0.92);
    taps[5] = vec2( 0.58, -0.78);

    for (int i = 0; i < 6; i++) {
      vec2 uv2 = clamp(vUv + taps[i] * uTexel * radius, vec2(0.002), vec2(0.998));
      float d2 = texture2D(tNd, uv2).a;
      float dist2 = d2 < 0.01 ? 18.0 : d2;
      // Avoid sharp foreground bleeding into blurred background
      float w = (dist2 >= uFocusDist - uFocusRange * 0.4 || dist < uFocusDist + uFocusRange * 0.4) ? 1.0 : 0.25;
      acc += texture2D(tInk, uv2).rgb * w;
      wSum += w;
    }
  }

  vec4 outColor = vec4(acc / wSum, 1.0);
  gl_FragColor = linearToOutputTexel(outColor);
}
`;

// Sky dome vertical gradient shader
const SKY_VERT = `
varying vec3 vWorldDir;
void main() {
  vWorldDir = normalize(position);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const SKY_FRAG = `
uniform vec3 uTop;
uniform vec3 uMid;
uniform vec3 uBot;
varying vec3 vWorldDir;
void main() {
  float h = clamp(vWorldDir.y * 0.5 + 0.5, 0.0, 1.0);
  vec3 col = h < 0.52
    ? mix(uBot, uMid, smoothstep(0.28, 0.52, h))
    : mix(uMid, uTop, smoothstep(0.52, 0.88, h));
  gl_FragColor = vec4(col, 1.0);
}
`;

export function easeOutCubic(x) {
  const t = Math.max(0, Math.min(1, x));
  return 1 - Math.pow(1 - t, 3);
}

export function easeOutBack(x) {
  const t = Math.max(0, Math.min(1, x));
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
}

export function easeInOutQuad(x) {
  const t = Math.max(0, Math.min(1, x));
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

export function lerp(a, b, t) {
  return a + (b - a) * t;
}

export function lerpVec(a, b, t) {
  return [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
}

/**
 * Creates the full 4-zone AKILALMAZ 3D-Toon stage + post-processing pipeline.
 */
export function createToonStage(canvas, config) {
  // Default = exact v9–v20 Shorts 540x960; long-form 16:9 passes width=960, height=540
  const SW = config.width || W;
  const SH = config.height || H;
  canvas.width = SW;
  canvas.height = SH;

  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: false,
    preserveDrawingBuffer: true,
    powerPreference: 'high-performance',
  });
  renderer.setSize(SW, SH, false);
  renderer.setPixelRatio(1);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NoToneMapping;

  const scene = new THREE.Scene();
  const fogColor = new THREE.Color(config.fogColor || '#f2c652');
  const sceneFog = new THREE.Fog(fogColor, 18, 56);
  scene.fog = sceneFog;

  const camera = new THREE.PerspectiveCamera(40, SW / SH, 0.08, 1500);

  // 2-Tone Cel Gradient
  const celGrad = makeCelGradient();

  function toonMat(colorHex, map = null) {
    const opts = { color: new THREE.Color(colorHex), gradientMap: celGrad };
    if (map) opts.map = map;
    return new THREE.MeshToonMaterial(opts);
  }

  function tbox(w, h, d, colorOrMat, x = 0, y = 0, z = 0, shadow = true) {
    const mat = typeof colorOrMat === 'string' || typeof colorOrMat === 'number'
      ? toonMat(colorOrMat)
      : colorOrMat;
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
    mesh.position.set(x, y, z);
    mesh.castShadow = shadow;
    mesh.receiveShadow = shadow;
    return mesh;
  }

  function tcyl(rt, rb, h, seg, colorOrMat, x = 0, y = 0, z = 0, shadow = true) {
    const mat = typeof colorOrMat === 'string' || typeof colorOrMat === 'number'
      ? toonMat(colorOrMat)
      : colorOrMat;
    const mesh = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, seg), mat);
    mesh.position.set(x, y, z);
    mesh.castShadow = shadow;
    mesh.receiveShadow = shadow;
    return mesh;
  }

  // Lighting (warm key sun + sky hemisphere fill)
  const hemi = new THREE.HemisphereLight(0xfff6dd, 0x6b5842, 0.92);
  scene.add(hemi);

  const sun = new THREE.DirectionalLight(0xfff4d6, 1.38);
  sun.position.set(6, 14, 10);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  sun.shadow.camera.near = 1;
  sun.shadow.camera.far = 48;
  sun.shadow.camera.left = -12;
  sun.shadow.camera.right = 12;
  sun.shadow.camera.top = 12;
  sun.shadow.camera.bottom = -12;
  sun.shadow.bias = -0.0008;
  scene.add(sun);
  scene.add(sun.target);

  // Sky Dome (follows camera.position in rtColor, hidden in rtNd)
  const skyGeo = new THREE.SphereGeometry(260, 24, 16);
  const skyMat = new THREE.ShaderMaterial({
    vertexShader: SKY_VERT,
    fragmentShader: SKY_FRAG,
    side: THREE.BackSide,
    depthWrite: false,
    fog: false,
    uniforms: {
      uTop: { value: new THREE.Color(config.skyTop || '#d4a34a') },
      uMid: { value: new THREE.Color(config.skyMid || '#f7d060') },
      uBot: { value: new THREE.Color(config.skyBot || '#f0b429') },
    },
  });
  const sky = new THREE.Mesh(skyGeo, skyMat);
  sky.userData.skipNd = true;
  scene.add(sky);

  // === ZONE 0 (x = 0): Outdoor Main Scene ===
  const z0 = new THREE.Group();
  scene.add(z0);

  const groundTex = makeGroundTex(config.groundA || '#7a8a3e', config.groundB || '#627030', 19);
  const groundMat = toonMat('#ffffff', groundTex);
  const groundMesh = new THREE.Mesh(new THREE.PlaneGeometry(56, 56), groundMat);
  groundMesh.rotation.x = -Math.PI / 2;
  groundMesh.position.set(0, -0.02, -4);
  groundMesh.receiveShadow = true;
  z0.add(groundMesh);

  // Stone/cobblestone path tbox(6.5, 0.22, 14, 2)
  const stoneTex = makeStonePathTex(
    config.stoneA || '#7d6e4a',
    config.stoneB || '#615538',
    config.stoneGrout || '#352d1d',
    29
  );
  const stoneMat = toonMat('#ffffff', stoneTex);
  const pathMesh = tbox(6.5, 0.22, 14, stoneMat, 0, -0.11, -1.5, true);
  pathMesh.castShadow = false;
  z0.add(pathMesh);

  // Low perimeter backdrop wall/curb behind heroProp (no overlap with heroGroup at z=-8.6)
  if (config.horizonWall !== false) {
    const curb = tbox(32, 1.35, 0.8, config.curbColor || '#c2983b', 0, 0.65, -11.6, true);
    z0.add(curb);
  }

  // Outdoor Signpost (paintSign 1024x320) cleanly framed on left side of Zone 0
  const signGroup = new THREE.Group();
  const post = tbox(0.18, 3.6, 0.18, '#4f2c15', -0.78, 1.75, -3.55, true);
  signGroup.add(post);
  const signTex = paintSign(config.sign || {});
  const signBack = tbox(2.18, 0.72, 0.14, '#d4a017', -0.78, 3.22, -3.38, true);
  signGroup.add(signBack);
  const signFace = new THREE.Mesh(
    new THREE.PlaneGeometry(2.10, 0.66),
    new THREE.MeshBasicMaterial({ map: signTex })
  );
  signFace.position.set(-0.78, 3.22, -3.29);
  signGroup.add(signFace);
  z0.add(signGroup);

  // Hero 3D Prop Container at z = -8.6
  const heroGroup = new THREE.Group();
  heroGroup.position.set(0, 0, -8.6);
  z0.add(heroGroup);

  // === ZONES 1, 2, 3 (x = 60, 120, 180): Indoor Boards & Desk ===
  const plankTex = makePlankTex('#b57c41', '#9f6a34', '#3d2410', 41);
  const plasterTex = makePlasterTex(
    config.plasterA || '#c2a666',
    config.plasterB || '#b39553',
    config.plasterSpot || '#9d7f3e',
    57
  );
  const darkWoodTex = makeDarkWoodTex('#4e2c16', '#331b0b', 73);

  const plankMat = toonMat('#ffffff', plankTex);
  const plasterMat = toonMat('#ffffff', plasterTex);
  const darkWoodMat = toonMat('#ffffff', darkWoodTex);
  const goldFrameMat = toonMat('#e6a800');

  const zoneOffsets = [60, 120, 180];
  const zoneGroups = [z0];
  const boardsCfg = config.boards || [];
  const nBoards = Math.max(3, boardsCfg.length);
  for (let zi = 3; zi < nBoards; zi++) zoneOffsets.push(60 * (zi + 1));

  for (let zi = 0; zi < nBoards; zi++) {
    const gx = zoneOffsets[zi];
    const zg = new THREE.Group();
    zg.position.set(gx, 0, 0);
    scene.add(zg);
    zoneGroups.push(zg);

    // Plank floor: 18 x 0.2 x 18
    const floor = tbox(18, 0.2, 18, plankMat, 0, -0.1, 0, true);
    floor.castShadow = false;
    zg.add(floor);

    // Plaster back wall: 18 x 6.4 x 0.4 at z = -5.0
    const wall = tbox(18, 6.4, 0.4, plasterMat, 0, 3.2, -5.0, true);
    wall.castShadow = false;
    zg.add(wall);

    // Baseboard trim
    const trim = tbox(18, 0.35, 0.48, darkWoodMat, 0, 0.18, -4.92, false);
    zg.add(trim);

    // Gold frame: 3.9 x 2.75 x 0.16 at z = -4.62
    const bCfg = boardsCfg[zi] || {
      header: `PANO ${zi + 1}`,
      line1: 'DETAY SATIRI',
      line2: 'ALT BİLGİ',
      line3: 'ÖZET',
      bg: ['#0c3c78', '#9b111e', '#114b34'][zi],
      accent: ['#4dabf7', '#ff6b6b', '#40c057'][zi],
    };
    const frame = tbox(3.9, 2.75, 0.16, goldFrameMat, 0, 3.28, -4.62, true);
    zg.add(frame);

    const boardTex = paintBoard(bCfg);
    const boardPlane = new THREE.Mesh(
      new THREE.PlaneGeometry(3.66, 2.52),
      new THREE.MeshBasicMaterial({ map: boardTex })
    );
    boardPlane.position.set(0, 3.28, -4.53);
    zg.add(boardPlane);

    // Front dark wood desk: 3.2 x 0.92 x 1.2 at z = -1.55 (optional per zone)
    if (bCfg.desk !== false) {
      const desk = tbox(3.2, 0.92, 1.2, darkWoodMat, 0, 0.46, -1.55, true);
      zg.add(desk);
      // Desk top overhang lip
      const deskTop = tbox(3.38, 0.12, 1.32, '#5e361c', 0, 0.96, -1.55, true);
      zg.add(deskTop);
    }
  }

  // === EXTRA OUTDOOR DIORAMA ZONES (long-form): config.outdoor = [{ x, groundA, groundB, path }] ===
  const outdoorHeroGroups = [];
  for (const oz of config.outdoor || []) {
    const og = new THREE.Group();
    og.position.set(oz.x, 0, 0);
    scene.add(og);
    zoneGroups.push(og);
    const gTex = makeGroundTex(oz.groundA || config.groundA || '#7a8a3e', oz.groundB || config.groundB || '#627030', 19 + oz.x);
    const g = new THREE.Mesh(new THREE.PlaneGeometry(56, 56), toonMat('#ffffff', gTex));
    g.rotation.x = -Math.PI / 2;
    g.position.set(0, -0.02, -4);
    g.receiveShadow = true;
    og.add(g);
    if (oz.path !== false) {
      const p = tbox(6.5, 0.22, 14, stoneMat, 0, -0.11, -1.5, true);
      p.castShadow = false;
      og.add(p);
    }
    const hg = new THREE.Group();
    hg.position.set(0, 0, -8.6);
    og.add(hg);
    outdoorHeroGroups.push({ x: oz.x, spec: oz.hero || {}, group: hg });
  }

  // === 2D INKED CHARACTER CARD CLASS ===
  const blobTex = makeShadowBlobTex();
  const blobMat = new THREE.MeshBasicMaterial({
    map: blobTex,
    transparent: true,
    depthWrite: false,
  });

  const ndMat = new THREE.ShaderMaterial({
    vertexShader: ND_VERT,
    fragmentShader: ND_FRAG,
  });

  function createCard(spec) {
    const c = document.createElement('canvas');
    c.width = CW;
    c.height = CH;
    const ctx = c.getContext('2d');

    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.minFilter = THREE.LinearFilter;
    tex.magFilter = THREE.LinearFilter;

    // PlaneGeometry(CM * 0.6, CM) translated so feet rest at y = 0
    const geo = new THREE.PlaneGeometry(CM * 0.6, CM);
    geo.translate(0, CM / 2 - CM * 0.025, 0);

    const mat = new THREE.MeshBasicMaterial({
      map: tex,
      transparent: true,
      alphaTest: 0.02,
      side: THREE.DoubleSide,
      fog: true,
    });

    const depthMat = new THREE.MeshDepthMaterial({
      depthPacking: THREE.RGBADepthPacking,
      map: tex,
      alphaTest: 0.02,
    });

    const cardNdMat = new THREE.ShaderMaterial({
      vertexShader: CARD_ND_VERT,
      fragmentShader: CARD_ND_FRAG,
      side: THREE.DoubleSide,
      uniforms: { map: { value: tex } },
    });

    const mesh = new THREE.Mesh(geo, mat);
    mesh.castShadow = true;
    mesh.receiveShadow = false;
    mesh.customDepthMaterial = depthMat;
    mesh.userData.cardNdMat = cardNdMat;
    scene.add(mesh);

    // Soft elliptical ground shadow blob at y = 0.02
    const blob = new THREE.Mesh(new THREE.PlaneGeometry(1.25, 0.85), blobMat);
    blob.rotation.x = -Math.PI / 2;
    blob.position.y = 0.02;
    blob.userData.skipNd = true;
    scene.add(blob);

    return {
      spec,
      canvas: c,
      ctx,
      tex,
      mesh,
      blob,
      update(pose, camPos) {
        if (!pose || pose.hidden) {
          mesh.visible = false;
          blob.visible = false;
          return;
        }
        mesh.visible = true;
        blob.visible = pose.shadow !== false;

        const s = pose.s || 1.0;
        const x = pose.x || 0;
        const y = pose.y || 0;
        const z = pose.z || 0;

        mesh.position.set(x, y, z);
        mesh.scale.set(s, s, s);
        mesh.lookAt(camPos[0], y, camPos[2]);

        blob.position.set(x, 0.02, z);
        blob.scale.set(s, s, 1);

        drawCharacter(ctx, spec, pose);
        tex.needsUpdate = true;
      },
    };
  }

  // === FLOATING FX CARDS (fxYear, fxBadge, fxMark, fxSparkles) ===
  const fxPool = [];

  function makeFxPlane(tex, w, h) {
    const mat = new THREE.MeshBasicMaterial({
      map: tex,
      transparent: true,
      alphaTest: 0.02,
      side: THREE.DoubleSide,
      depthTest: true,
    });
    const fxNdMat = new THREE.ShaderMaterial({
      vertexShader: CARD_ND_VERT,
      fragmentShader: CARD_ND_FRAG,
      side: THREE.DoubleSide,
      uniforms: { map: { value: tex } },
    });
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
    mesh.visible = false;
    mesh.userData.cardNdMat = fxNdMat;
    scene.add(mesh);
    fxPool.push(mesh);
    return mesh;
  }

  const fxFactory = {
    year(year, place) {
      return makeFxPlane(paintFxYear(year, place), 1.35, 1.35);
    },
    badge(top, bottom, bg, fg) {
      return makeFxPlane(paintFxBadge(top, bottom, bg, fg), 1.48, 0.74);
    },
    mark(sym, bg, fg) {
      return makeFxPlane(paintFxMark(sym, bg, fg), 0.92, 0.92);
    },
    sparkle(color) {
      return makeFxPlane(paintFxSparkle(color), 0.55, 0.55);
    },
  };

  function placeFx(mesh, pos, scale, camPos, rotZ = 0) {
    if (!mesh) return;
    if (scale <= 0.001) {
      mesh.visible = false;
      return;
    }
    mesh.visible = true;
    mesh.position.set(pos[0], pos[1], pos[2]);
    mesh.scale.set(scale, scale, scale);
    mesh.lookAt(camPos[0], pos[1], camPos[2]);
    if (rotZ) mesh.rotateZ(rotZ);
  }

  // === 3-STAGE POST-PROCESSING PIPELINE ===
  const rtColor = new THREE.WebGLRenderTarget(SW, SH, {
    type: THREE.HalfFloatType,
    minFilter: THREE.LinearFilter,
    magFilter: THREE.LinearFilter,
    depthBuffer: true,
  });

  const rtNd = new THREE.WebGLRenderTarget(SW, SH, {
    type: THREE.HalfFloatType,
    minFilter: THREE.NearestFilter,
    magFilter: THREE.NearestFilter,
    depthBuffer: true,
  });

  const rtInk = new THREE.WebGLRenderTarget(SW, SH, {
    type: THREE.HalfFloatType,
    minFilter: THREE.LinearFilter,
    magFilter: THREE.LinearFilter,
    depthBuffer: false,
  });

  const fsGeo = new THREE.PlaneGeometry(2, 2);
  const fsCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

  const inkUniforms = {
    tColor: { value: rtColor.texture },
    tNd: { value: rtNd.texture },
    uTexel: { value: new THREE.Vector2(1 / SW, 1 / SH) },
    uSat: { value: 1.08 },
    uVig: { value: 0.36 },
    uFlash: { value: 0.0 },
  };
  const inkScene = new THREE.Scene();
  inkScene.add(new THREE.Mesh(fsGeo, new THREE.ShaderMaterial({
    vertexShader: FULLSCREEN_VERT,
    fragmentShader: INK_FRAG,
    uniforms: inkUniforms,
    depthTest: false,
    depthWrite: false,
  })));

  const dofUniforms = {
    tInk: { value: rtInk.texture },
    tNd: { value: rtNd.texture },
    uTexel: { value: new THREE.Vector2(1 / SW, 1 / SH) },
    uFocusDist: { value: 5.5 },
    uFocusRange: { value: 3.2 },
    uMaxBlur: { value: 2.8 },
  };
  const dofScene = new THREE.Scene();
  dofScene.add(new THREE.Mesh(fsGeo, new THREE.ShaderMaterial({
    vertexShader: FULLSCREEN_VERT,
    fragmentShader: DOF_FRAG,
    uniforms: dofUniforms,
    depthTest: false,
    depthWrite: false,
  })));

  function renderPost({
    camPos,
    camLook,
    fov = 40,
    sat = 1.08,
    vig = 0.36,
    flash = 0.0,
    focusDist = 5.5,
    focusRange = 3.2,
    maxBlur = 2.6,
  }) {
    camera.fov = fov;
    camera.updateProjectionMatrix();
    camera.position.set(camPos[0], camPos[1], camPos[2]);
    camera.lookAt(camLook[0], camLook[1], camLook[2]);

    // Move directional light to follow active zone X so shadows stay sharp in all 4 zones
    const zoneX = Math.round(camLook[0] / 60) * 60;
    sun.position.set(zoneX + 5.5, 13.5, 8.5);
    sun.target.position.set(zoneX, 0, -2.5);
    sun.target.updateMatrixWorld();

    // Pass 1: rtColor
    sky.position.copy(camera.position);
    sky.visible = true;
    scene.fog = sceneFog;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.autoUpdate = true;
    renderer.setClearColor(fogColor, 1);
    renderer.setRenderTarget(rtColor);
    renderer.clear();
    renderer.render(scene, camera);

    // Pass 2: rtNd (Normal + Depth, sky & blobs hidden, fog & shadows off)
    const saved = [];
    scene.traverse((obj) => {
      if (!obj.isMesh) return;
      if (obj.userData.skipNd) {
        if (obj.visible) {
          saved.push({ obj, vis: true });
          obj.visible = false;
        }
      } else if (obj.visible) {
        saved.push({ obj, mat: obj.material });
        obj.material = obj.userData.cardNdMat || ndMat;
      }
    });

    scene.fog = null;
    renderer.shadowMap.enabled = false;
    renderer.shadowMap.autoUpdate = false;
    renderer.setClearColor(0x000000, 0);
    renderer.setRenderTarget(rtNd);
    renderer.clear();
    renderer.render(scene, camera);

    // Restore materials & visibility
    for (const s of saved) {
      if (s.vis !== undefined) s.obj.visible = s.vis;
      if (s.mat !== undefined) s.obj.material = s.mat;
    }

    // Pass 3a: rtInk (8-tap normal+depth outline + sat + vig + flash)
    inkUniforms.uSat.value = sat;
    inkUniforms.uVig.value = vig;
    inkUniforms.uFlash.value = flash;
    renderer.setRenderTarget(rtInk);
    renderer.render(inkScene, fsCam);

    // Pass 3b: dofScene (6-tap Poisson bokeh + linearToOutputTexel) to screen canvas
    dofUniforms.uFocusDist.value = focusDist;
    dofUniforms.uFocusRange.value = focusRange;
    dofUniforms.uMaxBlur.value = maxBlur;
    renderer.setRenderTarget(null);
    renderer.render(dofScene, fsCam);
  }

  return {
    THREE,
    scene,
    camera,
    renderer,
    celGrad,
    toonMat,
    tbox,
    tcyl,
    heroGroup,
    outdoorHeroGroups,
    zoneGroups,
    setSky(top, mid, bot, fog, light = 1.0) {
      skyMat.uniforms.uTop.value.set(top);
      skyMat.uniforms.uMid.value.set(mid);
      skyMat.uniforms.uBot.value.set(bot);
      if (fog) {
        fogColor.set(fog);
        sceneFog.color.set(fog);
      }
      hemi.intensity = 0.92 * light;
      sun.intensity = 1.38 * light;
    },
    createCard,
    fxFactory,
    placeFx,
    hideAllFx() {
      for (const m of fxPool) m.visible = false;
    },
    renderPost,
  };
}
