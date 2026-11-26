// engine/kit/paint.js — Procedural 2D Canvas textures, boards, signs & floating FX cards
// Matches AKILALMAZ v9–v20 exact visual identity (paintSign 1024x320, paintBoard 900x620, fxYear, fxBadge, fxMark)

import * as THREE from '../lib/three.module.js';

export const INK = '#1b141c';
const FONT_STACK = '"DejaVu Sans", Arial, sans-serif';

function makeCanvas(w, h) {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  return c;
}

function toTex(canvas, repeatX = 1, repeatY = 1, srgb = true) {
  const tex = new THREE.CanvasTexture(canvas);
  if (srgb) tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = repeatX > 1 ? THREE.RepeatWrapping : THREE.ClampToEdgeWrapping;
  tex.wrapT = repeatY > 1 ? THREE.RepeatWrapping : THREE.ClampToEdgeWrapping;
  if (repeatX > 1 || repeatY > 1) tex.repeat.set(repeatX, repeatY);
  tex.anisotropy = 4;
  tex.needsUpdate = true;
  return tex;
}

// Seeded PRNG for deterministic procedural textures
function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function roundRectPath(ctx, x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

// Outdoor ground base texture (subtle grass/sand/concrete mottled plane)
export function makeGroundTex(baseHex = '#52a447', accentHex = '#3f8a37', seed = 11) {
  const c = makeCanvas(512, 512);
  const ctx = c.getContext('2d');
  const rng = mulberry32(seed);
  ctx.fillStyle = baseHex;
  ctx.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 160; i++) {
    ctx.fillStyle = rng() > 0.5 ? accentHex : 'rgba(255,255,255,0.08)';
    ctx.globalAlpha = 0.28 + rng() * 0.25;
    const x = rng() * 512;
    const y = rng() * 512;
    const rx = 18 + rng() * 44;
    const ry = 8 + rng() * 20;
    ctx.beginPath();
    ctx.ellipse(x, y, rx, ry, rng() * Math.PI, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
  return toTex(c, 10, 10);
}

// Cobblestone / brick path texture (matches v20 olive-brown staggered brick path)
export function makeStonePathTex(baseHex = '#756846', darkHex = '#594e33', groutHex = '#332b1c', seed = 23) {
  const c = makeCanvas(512, 512);
  const ctx = c.getContext('2d');
  const rng = mulberry32(seed);
  ctx.fillStyle = groutHex;
  ctx.fillRect(0, 0, 512, 512);

  const rows = 12;
  const cols = 6;
  const rh = 512 / rows;
  const cw = 512 / cols;
  for (let r = 0; r < rows; r++) {
    const off = (r % 2) * (cw * 0.5);
    for (let col = -1; col <= cols; col++) {
      const x = col * cw + off + 3;
      const y = r * rh + 3;
      const w = cw - 6;
      const h = rh - 6;
      ctx.fillStyle = rng() > 0.45 ? baseHex : darkHex;
      roundRectPath(ctx, x, y, w, h, 6);
      ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.07)';
      ctx.fillRect(x + 4, y + 3, w - 8, 5);
    }
  }
  return toTex(c, 3, 6);
}

// Wooden plank floor (Zones 1, 2, 3)
export function makePlankTex(baseHex = '#b57c41', altHex = '#9e6832', seamHex = '#3c2411', seed = 37) {
  const c = makeCanvas(512, 512);
  const ctx = c.getContext('2d');
  const rng = mulberry32(seed);
  const planks = 8;
  const pw = 512 / planks;
  for (let i = 0; i < planks; i++) {
    ctx.fillStyle = i % 2 === 0 ? baseHex : altHex;
    ctx.fillRect(i * pw, 0, pw, 512);
    // Subtle grain streaks
    ctx.strokeStyle = 'rgba(60, 32, 10, 0.16)';
    ctx.lineWidth = 2;
    for (let g = 0; g < 6; g++) {
      const gx = i * pw + 6 + rng() * (pw - 12);
      ctx.beginPath();
      ctx.moveTo(gx, 0);
      ctx.bezierCurveTo(gx + 5, 170, gx - 5, 340, gx, 512);
      ctx.stroke();
    }
    // Dark seam
    ctx.fillStyle = seamHex;
    ctx.fillRect(i * pw, 0, 3, 512);
    // Horizontal board joint
    const jy = Math.floor(rng() * 380) + 60;
    ctx.fillRect(i * pw, jy, pw, 3);
  }
  return toTex(c, 5, 5);
}

// Warm ochre/cream plaster wall with subtle horizontal bands & mottling (matches v20_z3.jpg)
export function makePlasterTex(baseHex = '#bfa260', bandHex = '#b09350', spotHex = '#9c7f3d', seed = 53) {
  const c = makeCanvas(512, 512);
  const ctx = c.getContext('2d');
  const rng = mulberry32(seed);
  ctx.fillStyle = baseHex;
  ctx.fillRect(0, 0, 512, 512);

  // Subtle horizontal stone/plaster course bands
  const bands = 6;
  const bh = 512 / bands;
  for (let i = 0; i < bands; i++) {
    ctx.fillStyle = i % 2 === 0 ? baseHex : bandHex;
    ctx.globalAlpha = 0.45;
    ctx.fillRect(0, i * bh, 512, bh);
    ctx.fillStyle = 'rgba(70,52,20,0.14)';
    ctx.fillRect(0, i * bh, 512, 4);
  }

  // Soft organic plaster mottling spots
  for (let i = 0; i < 65; i++) {
    ctx.fillStyle = rng() > 0.35 ? spotHex : 'rgba(255,244,210,0.22)';
    ctx.globalAlpha = 0.16 + rng() * 0.14;
    ctx.beginPath();
    ctx.ellipse(rng() * 512, rng() * 512, 16 + rng() * 44, 10 + rng() * 22, rng() * 0.4, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
  return toTex(c, 3, 2);
}

// Dark wood desk texture
export function makeDarkWoodTex(baseHex = '#4b2a14', streakHex = '#331b0b', seed = 71) {
  const c = makeCanvas(512, 256);
  const ctx = c.getContext('2d');
  const rng = mulberry32(seed);
  ctx.fillStyle = baseHex;
  ctx.fillRect(0, 0, 512, 256);
  for (let i = 0; i < 28; i++) {
    ctx.strokeStyle = streakHex;
    ctx.globalAlpha = 0.25 + rng() * 0.25;
    ctx.lineWidth = 3 + rng() * 4;
    const y = rng() * 256;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.bezierCurveTo(170, y + (rng() - 0.5) * 18, 340, y + (rng() - 0.5) * 18, 512, y);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
  return toTex(c, 1, 1);
}

// Outdoor Signboard (1024x320) — matches v15/v20 crisp blue/red sign with double yellow border
export function paintSign({
  title = 'CHICAGO • 1942',
  subtitle = '2 ARALIK • İLK NÜKLEER REAKTÖR',
  bg = '#0b4da2',
  border = '#ffd60a',
  titleColor = '#ffd60a',
  subColor = '#ffffff',
}) {
  const c = makeCanvas(1024, 320);
  const ctx = c.getContext('2d');

  // Outer frame
  ctx.fillStyle = border;
  roundRectPath(ctx, 4, 4, 1016, 312, 22);
  ctx.fill();

  ctx.fillStyle = bg;
  roundRectPath(ctx, 18, 18, 988, 284, 14);
  ctx.fill();

  // Inner thin line
  ctx.strokeStyle = border;
  ctx.lineWidth = 6;
  roundRectPath(ctx, 30, 30, 964, 260, 10);
  ctx.stroke();

  // Title text auto-fit
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  let tSize = 86;
  ctx.font = `900 ${tSize}px ${FONT_STACK}`;
  while (ctx.measureText(title).width > 900 && tSize > 42) {
    tSize -= 4;
    ctx.font = `900 ${tSize}px ${FONT_STACK}`;
  }
  ctx.fillStyle = 'rgba(0,0,0,0.28)';
  ctx.fillText(title, 516, 126);
  ctx.fillStyle = titleColor;
  ctx.fillText(title, 512, 122);

  // Subtitle text auto-fit
  let sSize = 44;
  ctx.font = `800 ${sSize}px ${FONT_STACK}`;
  while (ctx.measureText(subtitle).width > 900 && sSize > 24) {
    sSize -= 2;
    ctx.font = `800 ${sSize}px ${FONT_STACK}`;
  }
  ctx.fillStyle = subColor;
  ctx.fillText(subtitle, 512, 228);

  return toTex(c, 1, 1);
}

// Indoor Wall Board (900x620) — matches exact v9–v20 paintBoard spec:
// Header: #ffd60a (or custom) 900 76px
// Line 1: #fff 900 54px
// Line 2: #a8dadc 800 42px
// Line 3: #ffd60a 900 44px
export function paintBoard({
  header = 'BAŞLIK',
  line1 = 'SATIR 1',
  line2 = 'SATIR 2',
  line3 = 'SATIR 3',
  bg = '#0c3c78',
  accent = '#4dabf7',
  headerColor = '#ffd60a',
}) {
  const c = makeCanvas(900, 620);
  const ctx = c.getContext('2d');

  // Subtle vertical gradient background
  const grad = ctx.createLinearGradient(0, 0, 0, 620);
  grad.addColorStop(0, bg);
  grad.addColorStop(1, shadeHex(bg, -18));
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 900, 620);

  // Clean bright inner border (just like v15/v20 boards!)
  ctx.strokeStyle = accent;
  ctx.lineWidth = 14;
  ctx.strokeRect(22, 22, 856, 576);

  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  const drawFit = (text, y, maxPx, weight, color, maxW = 816) => {
    if (!text) return;
    let sz = maxPx;
    ctx.font = `${weight} ${sz}px ${FONT_STACK}`;
    while (ctx.measureText(text).width > maxW && sz > 24) {
      sz -= 2;
      ctx.font = `${weight} ${sz}px ${FONT_STACK}`;
    }
    ctx.fillStyle = 'rgba(0,0,0,0.32)';
    ctx.fillText(text, 453, y + 4);
    ctx.fillStyle = color;
    ctx.fillText(text, 450, y);
  };

  drawFit(header, 128, 76, 900, headerColor);
  drawFit(line1, 258, 54, 900, '#ffffff');
  drawFit(line2, 384, 42, 800, '#a8dadc');
  drawFit(line3, 496, 44, 900, '#ffd60a');

  return toTex(c, 1, 1);
}

// Soft elliptical ground shadow blob texture
export function makeShadowBlobTex() {
  const c = makeCanvas(256, 256);
  const ctx = c.getContext('2d');
  const g = ctx.createRadialGradient(128, 128, 10, 128, 128, 120);
  g.addColorStop(0, 'rgba(20, 14, 22, 0.55)');
  g.addColorStop(0.55, 'rgba(20, 14, 22, 0.28)');
  g.addColorStop(1, 'rgba(20, 14, 22, 0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 256, 256);
  return toTex(c, 1, 1);
}

// Floating FX: Calendar Year Card (matches v15/v20 fxYear)
export function paintFxYear(year = '1942', place = 'CHİCAGO') {
  const c = makeCanvas(360, 360);
  const ctx = c.getContext('2d');

  // Shadow
  ctx.fillStyle = 'rgba(0,0,0,0.22)';
  roundRectPath(ctx, 28, 44, 312, 284, 26);
  ctx.fill();

  // White card body
  ctx.fillStyle = '#ffffff';
  roundRectPath(ctx, 20, 34, 312, 284, 26);
  ctx.fill();

  // Top blue/dark header bar
  ctx.save();
  roundRectPath(ctx, 20, 34, 312, 284, 26);
  ctx.clip();
  ctx.fillStyle = '#1b4965';
  ctx.fillRect(20, 34, 312, 86);
  ctx.restore();

  // Thick dark ink outline
  ctx.strokeStyle = INK;
  ctx.lineWidth = 10;
  roundRectPath(ctx, 20, 34, 312, 284, 26);
  ctx.stroke();

  // Divider line
  ctx.beginPath();
  ctx.moveTo(20, 120);
  ctx.lineTo(332, 120);
  ctx.lineWidth = 7;
  ctx.stroke();

  // Place header
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  let ps = 34;
  ctx.font = `900 ${ps}px ${FONT_STACK}`;
  while (ctx.measureText(place).width > 270 && ps > 18) {
    ps -= 2;
    ctx.font = `900 ${ps}px ${FONT_STACK}`;
  }
  ctx.fillStyle = '#ffd60a';
  ctx.fillText(place, 176, 78);

  // Big bold year
  ctx.font = `900 102px ${FONT_STACK}`;
  ctx.fillStyle = INK;
  ctx.fillText(String(year), 176, 224);

  return toTex(c, 1, 1);
}

// Floating FX: Colored Badge Card (matches v20 "38 DK! / EN KISA SAVAŞ", "REKOR! / 38 DAKİKA")
export function paintFxBadge(top = '2 ARALIK', bottom = 'İLK REAKTÖR', bg = '#e63946', fg = '#ffffff') {
  const c = makeCanvas(440, 220);
  const ctx = c.getContext('2d');

  // Drop shadow
  ctx.fillStyle = 'rgba(0,0,0,0.25)';
  roundRectPath(ctx, 26, 30, 396, 168, 28);
  ctx.fill();

  // Badge pill
  ctx.fillStyle = bg;
  roundRectPath(ctx, 18, 20, 396, 168, 28);
  ctx.fill();
  ctx.strokeStyle = INK;
  ctx.lineWidth = 10;
  roundRectPath(ctx, 18, 20, 396, 168, 28);
  ctx.stroke();

  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  let ts = 64;
  ctx.font = `900 ${ts}px ${FONT_STACK}`;
  while (ctx.measureText(top).width > 350 && ts > 26) {
    ts -= 2;
    ctx.font = `900 ${ts}px ${FONT_STACK}`;
  }
  ctx.fillStyle = fg;
  ctx.fillText(top, 216, bottom ? 82 : 104);

  if (bottom) {
    let bs = 34;
    ctx.font = `800 ${bs}px ${FONT_STACK}`;
    while (ctx.measureText(bottom).width > 356 && bs > 18) {
      bs -= 2;
      ctx.font = `800 ${bs}px ${FONT_STACK}`;
    }
    ctx.fillStyle = fg;
    ctx.globalAlpha = 0.94;
    ctx.fillText(bottom, 216, 144);
    ctx.globalAlpha = 1;
  }

  return toTex(c, 1, 1);
}

// Floating FX: Circle Mark ("?" or "!") — matches v15/v20 yellow circle "?"
export function paintFxMark(symbol = '?', bg = '#ffd60a', fg = INK) {
  const c = makeCanvas(280, 280);
  const ctx = c.getContext('2d');

  ctx.fillStyle = 'rgba(0,0,0,0.22)';
  ctx.beginPath();
  ctx.arc(146, 148, 110, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = bg;
  ctx.beginPath();
  ctx.arc(140, 140, 110, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = INK;
  ctx.lineWidth = 12;
  ctx.stroke();

  ctx.fillStyle = fg;
  ctx.font = `900 144px ${FONT_STACK}`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(symbol, 140, 148);

  return toTex(c, 1, 1);
}

// Floating FX: 4-point cartoon sparkle star (matches v15/v20 finale sparkles)
export function paintFxSparkle(color = '#ffd60a') {
  const c = makeCanvas(180, 180);
  const ctx = c.getContext('2d');
  const cx = 90, cy = 90, outer = 72, inner = 20;
  ctx.beginPath();
  for (let i = 0; i < 8; i++) {
    const r = i % 2 === 0 ? outer : inner;
    const a = (i * Math.PI) / 4 - Math.PI / 2;
    const x = cx + Math.cos(a) * r;
    const y = cy + Math.sin(a) * r;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
  ctx.strokeStyle = INK;
  ctx.lineWidth = 9;
  ctx.lineJoin = 'round';
  ctx.stroke();
  return toTex(c, 1, 1);
}

export function shadeHex(hex, percent) {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map(x => x + x).join('') : h, 16);
  const r = Math.max(0, Math.min(255, ((n >> 16) & 255) + Math.round(2.55 * percent)));
  const g = Math.max(0, Math.min(255, ((n >> 8) & 255) + Math.round(2.55 * percent)));
  const b = Math.max(0, Math.min(255, (n & 255) + Math.round(2.55 * percent)));
  return '#' + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
}
