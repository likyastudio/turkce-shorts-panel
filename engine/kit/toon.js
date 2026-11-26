// engine/kit/toon.js — 600x1000 2D Thick-Inked Character Renderer
// Exact AKILALMAZ v9–v20 proportions:
// cx=300, sole=975, u=2.08, W=74*u, TH=94*u, LL=104*u, ow=9.2, limb=6.2*u, INK="#1b141c"

import { INK, roundRectPath, shadeHex } from './paint.js';

export const CW = 600;
export const CH = 1000;

const CX = 300;
const SOLE = 975;
const U = 2.08;
const W = 74 * U;      // ~153.92
const TH = 94 * U;     // ~195.52
const LL = 104 * U;    // ~216.32
const OW = 9.2;
const LIMB = 6.2 * U;  // ~12.9

export const FACE_ALIAS = {
  gleeful: 'grin',
  shocked: 'shock',
  confused: 'nervous',
  done: 'pained',
  happy: 'smile',
  worried: 'nervous',
  angry: 'stern',
  surprised: 'shock',
};

export function resolveFace(f) {
  if (!f) return 'neutral';
  return FACE_ALIAS[f] || f;
}

// Deterministic eye blink check
export function blinkAt(t, seed = 0) {
  const period = 3.1 + (seed % 5) * 0.37;
  const phase = (t + seed * 1.13) % period;
  return phase > period - 0.13;
}

// Organic bean/oval head contour (blobPts)
function drawBlobHead(ctx, cx, cy, rx, ry) {
  ctx.beginPath();
  const N = 36;
  for (let i = 0; i <= N; i++) {
    const a = (i / N) * Math.PI * 2;
    // Slight subtle cheek fullness & tapered top like hand-drawn bean/oval
    const wobble = 1.0 + 0.025 * Math.sin(a) - 0.018 * Math.cos(a * 2);
    const x = cx + Math.cos(a) * rx * wobble;
    const y = cy + Math.sin(a) * ry * (1.0 + 0.015 * Math.sin(a));
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
}

// Two-pass cartoon inked curved limb (outer INK stroke + inner coat stroke)
function drawInkedArm(ctx, x0, y0, cpx, cpy, x1, y1, coatColor, handColor) {
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  // Outer ink stroke
  ctx.beginPath();
  ctx.moveTo(x0, y0);
  ctx.quadraticCurveTo(cpx, cpy, x1, y1);
  ctx.strokeStyle = INK;
  ctx.lineWidth = LIMB + OW * 1.45;
  ctx.stroke();

  // Inner sleeve fill stroke
  ctx.beginPath();
  ctx.moveTo(x0, y0);
  ctx.quadraticCurveTo(cpx, cpy, x1, y1);
  ctx.strokeStyle = coatColor;
  ctx.lineWidth = LIMB;
  ctx.stroke();

  // Round hand circle (matches v20 clean peach circle hand)
  ctx.beginPath();
  ctx.arc(x1, y1, 22, 0, Math.PI * 2);
  ctx.fillStyle = handColor;
  ctx.fill();
  ctx.strokeStyle = INK;
  ctx.lineWidth = 4.2;
  ctx.stroke();
}

// Optional handheld prop (e.g., axe for SCRAM safety guard, clipboard, megaphone)
function drawHeldProp(ctx, prop, hx, hy, side, t) {
  if (!prop) return;
  ctx.save();
  ctx.translate(hx, hy);
  const swing = Math.sin(t * 5.2) * 0.14;
  ctx.rotate((side < 0 ? -0.35 : 0.35) + swing);

  if (prop === 'axe') {
    // Wooden handle
    ctx.fillStyle = '#8b5a2b';
    ctx.strokeStyle = INK;
    ctx.lineWidth = 7;
    roundRectPath(ctx, -9, -118, 18, 138, 6);
    ctx.fill();
    ctx.stroke();
    // Steel axe head (red-edged fire axe)
    ctx.beginPath();
    ctx.moveTo(4, -112);
    ctx.quadraticCurveTo(56, -126, 62, -74);
    ctx.quadraticCurveTo(32, -62, 4, -76);
    ctx.closePath();
    ctx.fillStyle = '#c92a2a';
    ctx.fill();
    ctx.stroke();
    // Bright silver blade edge
    ctx.beginPath();
    ctx.moveTo(48, -114);
    ctx.quadraticCurveTo(64, -95, 58, -74);
    ctx.strokeStyle = '#e9ecef';
    ctx.lineWidth = 8;
    ctx.stroke();
    ctx.strokeStyle = INK;
    ctx.lineWidth = 5;
    ctx.stroke();
  } else if (prop === 'clipboard') {
    ctx.fillStyle = '#a66b38';
    ctx.strokeStyle = INK;
    ctx.lineWidth = 7;
    roundRectPath(ctx, -36, -64, 72, 92, 8);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#fff9db';
    ctx.fillRect(-26, -50, 52, 66);
    ctx.strokeStyle = '#495057';
    ctx.lineWidth = 4;
    for (let i = 0; i < 4; i++) {
      ctx.beginPath();
      ctx.moveTo(-18, -36 + i * 14);
      ctx.lineTo(18, -36 + i * 14);
      ctx.stroke();
    }
  } else if (prop === 'chalk') {
    ctx.fillStyle = '#f8f9fa';
    ctx.strokeStyle = INK;
    ctx.lineWidth = 5;
    roundRectPath(ctx, -6, -42, 12, 44, 4);
    ctx.fill();
    ctx.stroke();
  } else if (prop === 'geiger') {
    ctx.fillStyle = '#ffd43b';
    ctx.strokeStyle = INK;
    ctx.lineWidth = 7;
    roundRectPath(ctx, -30, -48, 60, 56, 10);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#f8f9fa';
    ctx.fillRect(-20, -38, 40, 22);
    ctx.strokeStyle = '#e03131';
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(0, -18);
    ctx.lineTo(Math.sin(t * 14) * 14, -34);
    ctx.stroke();
  } else if (prop === 'binoculars') {
    ctx.fillStyle = '#2b303a';
    ctx.strokeStyle = INK;
    ctx.lineWidth = 6.5;
    roundRectPath(ctx, -38, -28, 32, 48, 10);
    ctx.fill();
    ctx.stroke();
    roundRectPath(ctx, 6, -28, 32, 48, 10);
    ctx.fill();
    ctx.stroke();
    ctx.fillRect(-8, -12, 16, 14);
    ctx.fillStyle = '#74c0fc';
    ctx.beginPath();
    ctx.arc(-22, -26, 10, 0, Math.PI * 2);
    ctx.arc(22, -26, 10, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
  ctx.restore();
}

function armTargets(pose, side, sx, sy, t, headX, headY, torsoX, torsoY) {
  // side: -1 = left arm on screen, +1 = right arm on screen
  const wave = Math.sin(t * 7.5 + (side > 0 ? 1.2 : 0));
  const subtle = Math.sin(t * 3.1 + side) * 6;
  switch (pose) {
    case 'up':
      return {
        cpx: sx + side * 44,
        cpy: sy - 42,
        x1: sx + side * 66 + subtle * 0.5,
        y1: sy - 118 + wave * 10,
      };
    case 'wave':
      return {
        cpx: sx + side * 52,
        cpy: sy - 34,
        x1: sx + side * 86 + wave * 18,
        y1: sy - 110 + Math.abs(wave) * 12,
      };
    case 'point':
      return {
        cpx: sx + side * 72,
        cpy: sy - 16,
        x1: sx + side * 142,
        y1: sy - 42 + subtle * 0.6,
      };
    case 'hip':
      return {
        cpx: sx + side * 68,
        cpy: sy + 52,
        x1: sx + side * 26,
        y1: sy + 106,
      };
    case 'shrug':
      return {
        cpx: sx + side * 60,
        cpy: sy + 44,
        x1: sx + side * 98,
        y1: sy - 10 + subtle * 0.5,
      };
    case 'facepalm':
      return {
        cpx: sx + side * 62,
        cpy: sy + 20,
        x1: headX + side * 22,
        y1: headY + 14,
      };
    case 'hang':
    default:
      return {
        cpx: sx + side * 34,
        cpy: sy + 64,
        x1: sx + side * 28 + subtle * 0.4,
        y1: sy + 132,
      };
  }
}

function drawFace(ctx, faceName, hx, hy, blink, talkAmp, t) {
  const f = resolveFace(faceName);
  const eyeY = hy - 14;
  const ex = 30;

  ctx.strokeStyle = INK;
  ctx.fillStyle = INK;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  const drawEyeWhites = (r = 19, pupilR = 6.5, lookX = 0, lookY = 0) => {
    for (const s of [-1, 1]) {
      ctx.beginPath();
      ctx.arc(hx + s * ex, eyeY, r, 0, Math.PI * 2);
      ctx.fillStyle = '#ffffff';
      ctx.fill();
      ctx.lineWidth = 4.6;
      ctx.strokeStyle = INK;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(hx + s * ex + lookX, eyeY + lookY, pupilR, 0, Math.PI * 2);
      ctx.fillStyle = INK;
      ctx.fill();
    }
  };

  const drawClosedArcs = (happy = true) => {
    ctx.strokeStyle = INK;
    ctx.lineWidth = 6.5;
    for (const s of [-1, 1]) {
      ctx.beginPath();
      if (happy) {
        ctx.arc(hx + s * ex, eyeY + 6, 14, Math.PI * 1.12, Math.PI * 1.88);
      } else {
        ctx.moveTo(hx + s * ex - 13, eyeY);
        ctx.lineTo(hx + s * ex + 13, eyeY);
      }
      ctx.stroke();
    }
  };

  const drawBrows = (mode) => {
    ctx.strokeStyle = INK;
    ctx.lineWidth = 6.2;
    for (const s of [-1, 1]) {
      const bx = hx + s * ex;
      const by = eyeY - 29;
      ctx.beginPath();
      if (mode === 'angry') {
        ctx.moveTo(bx - 16, by - s * 7);
        ctx.lineTo(bx + 16, by + s * 8);
      } else if (mode === 'worried') {
        ctx.moveTo(bx - 15, by + s * 8);
        ctx.lineTo(bx + 15, by - s * 6);
      } else if (mode === 'raised') {
        ctx.arc(bx, by + 10, 18, Math.PI * 1.18, Math.PI * 1.82);
      } else if (mode === 'flat') {
        ctx.moveTo(bx - 15, by + 2);
        ctx.lineTo(bx + 15, by + 2);
      }
      ctx.stroke();
    }
  };

  // Eyes
  if (blink && f !== 'shock' && f !== 'dazed') {
    drawClosedArcs(f === 'smile' || f === 'grin' || f === 'laugh' || f === 'relief' || f === 'smile_closed');
  } else if (f === 'smile' || f === 'smile_closed' || f === 'relief' || f === 'laugh') {
    drawClosedArcs(true);
    drawBrows('raised');
  } else if (f === 'shock') {
    drawEyeWhites(22, 6.2, 0, 1);
    drawBrows('raised');
  } else if (f === 'nervous') {
    drawEyeWhites(18, 5.5, 3 * Math.sin(t * 3), 2);
    drawBrows('worried');
  } else if (f === 'stern') {
    for (const s of [-1, 1]) {
      ctx.beginPath();
      ctx.arc(hx + s * ex, eyeY + 2, 7.5, 0, Math.PI * 2);
      ctx.fillStyle = INK;
      ctx.fill();
    }
    drawBrows('angry');
  } else if (f === 'pained') {
    ctx.lineWidth = 6.5;
    for (const s of [-1, 1]) {
      ctx.beginPath();
      ctx.moveTo(hx + s * ex - 13, eyeY + 2);
      ctx.lineTo(hx + s * ex + 13, eyeY + 2);
      ctx.stroke();
    }
    drawBrows('worried');
  } else if (f === 'dazed') {
    ctx.lineWidth = 5.5;
    for (const s of [-1, 1]) {
      const exx = hx + s * ex;
      ctx.beginPath();
      ctx.moveTo(exx - 11, eyeY - 11);
      ctx.lineTo(exx + 11, eyeY + 11);
      ctx.moveTo(exx + 11, eyeY - 11);
      ctx.lineTo(exx - 11, eyeY + 11);
      ctx.stroke();
    }
  } else {
    // neutral, grin, whistle, lick
    for (const s of [-1, 1]) {
      ctx.beginPath();
      ctx.arc(hx + s * ex, eyeY, 8.2, 0, Math.PI * 2);
      ctx.fillStyle = INK;
      ctx.fill();
    }
    if (f === 'grin') drawBrows('raised');
  }

  // Mouth
  const my = hy + 34;
  const openExtra = talkAmp * 11;

  if (f === 'shock') {
    ctx.beginPath();
    ctx.ellipse(hx, my + 4, 17, 22 + openExtra * 0.5, 0, 0, Math.PI * 2);
    ctx.fillStyle = '#6f1d1b';
    ctx.fill();
    ctx.strokeStyle = INK;
    ctx.lineWidth = 6;
    ctx.stroke();
  } else if (f === 'laugh' || f === 'grin') {
    ctx.beginPath();
    ctx.arc(hx, my - 6, 26, 0.08 * Math.PI, 0.92 * Math.PI);
    ctx.closePath();
    ctx.fillStyle = '#ffffff';
    ctx.fill();
    ctx.strokeStyle = INK;
    ctx.lineWidth = 6;
    ctx.stroke();
  } else if (f === 'smile') {
    if (openExtra > 4) {
      ctx.beginPath();
      ctx.arc(hx, my - 4, 21, 0.06 * Math.PI, 0.94 * Math.PI);
      ctx.closePath();
      ctx.fillStyle = '#ffffff';
      ctx.fill();
      ctx.strokeStyle = INK;
      ctx.lineWidth = 5.6;
      ctx.stroke();
    } else {
      ctx.beginPath();
      ctx.arc(hx, my - 8, 22, 0.14 * Math.PI, 0.86 * Math.PI);
      ctx.strokeStyle = INK;
      ctx.lineWidth = 6.2;
      ctx.stroke();
    }
  } else if (f === 'smile_closed' || f === 'relief') {
    ctx.beginPath();
    ctx.arc(hx, my - 8, 20, 0.15 * Math.PI, 0.85 * Math.PI);
    ctx.strokeStyle = INK;
    ctx.lineWidth = 6.2;
    ctx.stroke();
  } else if (f === 'nervous' || f === 'dazed') {
    // Classic wavy zigzag mouth (seen in v20_z1.jpg!)
    ctx.beginPath();
    const mw = 36;
    ctx.moveTo(hx - mw / 2, my + 2);
    for (let i = 1; i <= 4; i++) {
      const px = hx - mw / 2 + (mw * i) / 4;
      const py = my + (i % 2 === 1 ? -6 : 6);
      ctx.lineTo(px, py);
    }
    ctx.strokeStyle = INK;
    ctx.lineWidth = 5.6;
    ctx.stroke();
  } else if (f === 'pained') {
    // Clenched teeth rectangle (seen in v20_z3.jpg!)
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = INK;
    ctx.lineWidth = 5.4;
    roundRectPath(ctx, hx - 22, my - 8, 44, 20, 7);
    ctx.fill();
    ctx.stroke();
    ctx.lineWidth = 3.2;
    for (const tx of [-10, 0, 10]) {
      ctx.beginPath();
      ctx.moveTo(hx + tx, my - 8);
      ctx.lineTo(hx + tx, my + 12);
      ctx.stroke();
    }
  } else if (f === 'stern') {
    ctx.beginPath();
    ctx.moveTo(hx - 18, my + 5);
    ctx.quadraticCurveTo(hx, my - 4, hx + 18, my + 5);
    ctx.strokeStyle = INK;
    ctx.lineWidth = 6;
    ctx.stroke();
  } else if (f === 'whistle') {
    ctx.beginPath();
    ctx.arc(hx + 6, my + 2, 10, 0, Math.PI * 2);
    ctx.fillStyle = '#6f1d1b';
    ctx.fill();
    ctx.strokeStyle = INK;
    ctx.lineWidth = 5.5;
    ctx.stroke();
  } else if (f === 'lick') {
    ctx.beginPath();
    ctx.arc(hx, my - 6, 20, 0.1 * Math.PI, 0.9 * Math.PI);
    ctx.strokeStyle = INK;
    ctx.lineWidth = 6;
    ctx.stroke();
    ctx.beginPath();
    ctx.ellipse(hx + 10, my + 10, 10, 12, 0.2, 0, Math.PI * 2);
    ctx.fillStyle = '#ff6b81';
    ctx.fill();
    ctx.lineWidth = 4.5;
    ctx.stroke();
  } else {
    // neutral with subtle talking mouth
    if (openExtra > 4) {
      ctx.beginPath();
      ctx.ellipse(hx, my + 2, 13, 6 + openExtra * 0.55, 0, 0, Math.PI * 2);
      ctx.fillStyle = '#6f1d1b';
      ctx.fill();
      ctx.strokeStyle = INK;
      ctx.lineWidth = 5.2;
      ctx.stroke();
    } else {
      ctx.beginPath();
      ctx.moveTo(hx - 16, my + 2);
      ctx.quadraticCurveTo(hx, my + 9, hx + 16, my + 2);
      ctx.strokeStyle = INK;
      ctx.lineWidth = 5.8;
      ctx.stroke();
    }
  }
}

function drawGlasses(ctx, type, hx, hy) {
  if (!type) return;
  const eyeY = hy - 14;
  const ex = 32;
  ctx.strokeStyle = INK;
  ctx.lineWidth = 6.2;

  for (const s of [-1, 1]) {
    ctx.beginPath();
    if (type === 'sunglasses') {
      roundRectPath(ctx, hx + s * ex - 24, eyeY - 16, 48, 32, 8);
      ctx.fillStyle = '#1d242b';
      ctx.fill();
      ctx.stroke();
      ctx.strokeStyle = 'rgba(255,255,255,0.45)';
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.moveTo(hx + s * ex - 12, eyeY - 9);
      ctx.lineTo(hx + s * ex - 2, eyeY + 6);
      ctx.stroke();
      ctx.strokeStyle = INK;
      ctx.lineWidth = 6.2;
    } else {
      ctx.arc(hx + s * ex, eyeY, 22, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(220, 245, 255, 0.28)';
      ctx.fill();
      ctx.stroke();
    }
  }
  // Bridge
  ctx.beginPath();
  ctx.moveTo(hx - 10, eyeY);
  ctx.lineTo(hx + 10, eyeY);
  ctx.stroke();
}

function drawHat(ctx, hat, hatColor, hatAccent, hx, hy, hr) {
  if (!hat || hat === 'none') return;
  const topY = hy - hr + 12;
  ctx.strokeStyle = INK;
  ctx.lineWidth = OW;
  ctx.lineJoin = 'round';

  if (hat === 'fedora' || hat === 'admiral') {
    // Classic v20 navy hat with bright yellow band!
    ctx.fillStyle = hatColor || '#1d3557';
    // Crown
    ctx.beginPath();
    ctx.moveTo(hx - 64, topY + 24);
    ctx.lineTo(hx - 50, topY - 46);
    ctx.lineTo(hx + 50, topY - 46);
    ctx.lineTo(hx + 64, topY + 24);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    // Accent ribbon band
    ctx.fillStyle = hatAccent || '#ffd60a';
    ctx.fillRect(hx - 58, topY - 2, 116, 20);
    ctx.strokeRect(hx - 58, topY - 2, 116, 20);
    // Brim
    ctx.fillStyle = hatColor || '#1d3557';
    roundRectPath(ctx, hx - 92, topY + 14, 184, 24, 10);
    ctx.fill();
    ctx.stroke();
  } else if (hat === 'beanie' || hat === 'turban') {
    ctx.fillStyle = hatColor || '#f8f9fa';
    ctx.beginPath();
    ctx.ellipse(hx, topY + 14, 88, 44, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(hx - 6, topY - 34, 22, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  } else if (hat === 'bobby' || hat === 'helmet' || hat === 'hardhat') {
    ctx.fillStyle = hatColor || '#ffd60a';
    ctx.beginPath();
    ctx.arc(hx, topY + 22, 84, Math.PI, 0);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    // Visor / brim
    ctx.fillStyle = hatAccent || shadeHex(hatColor || '#ffd60a', -18);
    roundRectPath(ctx, hx - 96, topY + 14, 192, 20, 9);
    ctx.fill();
    ctx.stroke();
    if (hat === 'bobby') {
      ctx.fillStyle = '#ffd60a';
      ctx.beginPath();
      ctx.arc(hx, topY - 12, 14, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    }
  } else if (hat === 'crown') {
    ctx.fillStyle = '#ffd60a';
    ctx.beginPath();
    ctx.moveTo(hx - 66, topY + 24);
    ctx.lineTo(hx - 74, topY - 40);
    ctx.lineTo(hx - 28, topY - 6);
    ctx.lineTo(hx, topY - 54);
    ctx.lineTo(hx + 28, topY - 6);
    ctx.lineTo(hx + 74, topY - 40);
    ctx.lineTo(hx + 66, topY + 24);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  } else if (hat === 'bandana' || hat === 'headband') {
    ctx.fillStyle = hatColor || '#e63946';
    roundRectPath(ctx, hx - 86, topY + 4, 172, 28, 12);
    ctx.fill();
    ctx.stroke();
  } else if (hat === 'bicorne') {
    ctx.fillStyle = hatColor || '#1d2d44';
    ctx.beginPath();
    ctx.moveTo(hx - 102, topY + 24);
    ctx.quadraticCurveTo(hx, topY - 76, hx + 102, topY + 24);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#ffd60a';
    ctx.beginPath();
    ctx.arc(hx, topY - 8, 15, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  } else if (hat === 'laurel') {
    ctx.fillStyle = '#52b788';
    for (const s of [-1, 1]) {
      for (let i = 0; i < 4; i++) {
        ctx.save();
        ctx.translate(hx + s * (32 + i * 16), topY + 4 + i * 6);
        ctx.rotate(s * (0.4 + i * 0.25));
        ctx.beginPath();
        ctx.ellipse(0, 0, 18, 9, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.lineWidth = 4.5;
        ctx.stroke();
        ctx.restore();
      }
    }
  } else if (hat === 'hair') {
    // Classic scientist/Fermi swept hair tuft
    ctx.fillStyle = hatColor || '#495057';
    ctx.beginPath();
    ctx.arc(hx, topY + 24, 82, Math.PI * 1.08, Math.PI * 1.92);
    ctx.quadraticCurveTo(hx + 22, topY - 12, hx - 20, topY + 6);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }
}

function drawSweatDrop(ctx, hx, hy, t) {
  const dropY = hy - 58 + ((t * 48) % 28);
  const dx = hx + 76;
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(dx, dropY - 22);
  ctx.bezierCurveTo(dx + 16, dropY, dx + 14, dropY + 18, dx, dropY + 18);
  ctx.bezierCurveTo(dx - 14, dropY + 18, dx - 16, dropY, dx, dropY - 22);
  ctx.closePath();
  ctx.fillStyle = '#74c0fc';
  ctx.fill();
  ctx.strokeStyle = INK;
  ctx.lineWidth = 5;
  ctx.stroke();
  ctx.restore();
}

function drawCatCharacter(ctx, spec, state) {
  ctx.clearRect(0, 0, CW, CH);
  const t = state.t || 0;
  const seed = spec.seed || 2;
  const idleBob = Math.sin(t * 4.4 + seed) * 6;
  const hop = state.hop || 0;

  const fur = spec.fur || '#f08c2b';
  const furDark = shadeHex(fur, -18);
  const belly = spec.belly || '#fff3d6';
  const baseY = SOLE - hop;
  const bodyY = baseY - 210 + idleBob;
  const headY = bodyY - 125;

  ctx.save();
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';

  // Swishing curved cat tail behind body
  const tailWag = Math.sin(t * 5.2) * 32;
  ctx.beginPath();
  ctx.moveTo(CX + 58, bodyY + 125);
  ctx.bezierCurveTo(CX + 150, bodyY + 95, CX + 175 + tailWag, bodyY - 10, CX + 130 + tailWag, bodyY - 55);
  ctx.strokeStyle = INK;
  ctx.lineWidth = 34;
  ctx.stroke();
  ctx.strokeStyle = fur;
  ctx.lineWidth = 17;
  ctx.stroke();

  // Four cute paws / legs
  for (const lx of [CX - 48, CX + 48]) {
    ctx.beginPath();
    ctx.moveTo(lx, bodyY + 130);
    ctx.lineTo(lx, baseY - 24);
    ctx.strokeStyle = INK;
    ctx.lineWidth = 32;
    ctx.stroke();
    ctx.strokeStyle = fur;
    ctx.lineWidth = 16;
    ctx.stroke();

    ctx.beginPath();
    ctx.ellipse(lx, baseY - 18, 26, 15, 0, 0, Math.PI * 2);
    ctx.fillStyle = belly;
    ctx.fill();
    ctx.strokeStyle = INK;
    ctx.lineWidth = 7;
    ctx.stroke();
  }

  // Plump rounded cat body + cream belly patch
  ctx.save();
  roundRectPath(ctx, CX - 76, bodyY - 15, 152, 170, 62);
  ctx.fillStyle = fur;
  ctx.fill();
  ctx.clip();
  ctx.fillStyle = furDark;
  ctx.fillRect(CX + 18, bodyY - 15, 80, 170);
  // Tabby side stripes
  ctx.fillStyle = '#c85a0b';
  for (const sy of [35, 72, 108]) {
    roundRectPath(ctx, CX - 80, bodyY + sy, 36, 13, 6);
    ctx.fill();
    roundRectPath(ctx, CX + 44, bodyY + sy, 36, 13, 6);
    ctx.fill();
  }
  ctx.beginPath();
  ctx.ellipse(CX, bodyY + 86, 46, 62, 0, 0, Math.PI * 2);
  ctx.fillStyle = belly;
  ctx.fill();
  ctx.restore();

  roundRectPath(ctx, CX - 76, bodyY - 15, 152, 170, 62);
  ctx.strokeStyle = INK;
  ctx.lineWidth = OW;
  ctx.stroke();

  // Raised cute cat paw when excited
  if (state.armL === 'up' || state.armR === 'up' || state.armL === 'wave' || state.armR === 'wave') {
    const wave = Math.sin(t * 7.5) * 14;
    ctx.beginPath();
    ctx.moveTo(CX - 64, bodyY + 26);
    ctx.quadraticCurveTo(CX - 115, bodyY - 22, CX - 102 + wave, bodyY - 76);
    ctx.strokeStyle = INK;
    ctx.lineWidth = 30;
    ctx.stroke();
    ctx.strokeStyle = fur;
    ctx.lineWidth = 15;
    ctx.stroke();
  }

  // Optional comedic fluffy fake lion-mane ring (when spec.mane or state.propL === 'mane')
  if (spec.mane || state.propL === 'mane') {
    ctx.beginPath();
    const spikes = 14;
    for (let i = 0; i <= spikes * 2; i++) {
      const a = (i / (spikes * 2)) * Math.PI * 2;
      const r = i % 2 === 0 ? 136 : 112;
      const x = CX + Math.cos(a) * r;
      const y = headY + Math.sin(a) * (r * 0.94);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fillStyle = '#d97706';
    ctx.fill();
    ctx.strokeStyle = INK;
    ctx.lineWidth = OW;
    ctx.stroke();
  }

  // Pointy Cat Ears
  for (const s of [-1, 1]) {
    ctx.beginPath();
    ctx.moveTo(CX + s * 22, headY - 74);
    ctx.lineTo(CX + s * 84, headY - 134);
    ctx.lineTo(CX + s * 86, headY - 34);
    ctx.closePath();
    ctx.fillStyle = fur;
    ctx.fill();
    ctx.strokeStyle = INK;
    ctx.lineWidth = OW;
    ctx.stroke();

    // Inner pink ear
    ctx.beginPath();
    ctx.moveTo(CX + s * 38, headY - 68);
    ctx.lineTo(CX + s * 74, headY - 108);
    ctx.lineTo(CX + s * 74, headY - 46);
    ctx.closePath();
    ctx.fillStyle = '#ff9aa2';
    ctx.fill();
  }

  // Cat Head
  ctx.save();
  drawBlobHead(ctx, CX, headY, 96, 84);
  ctx.fillStyle = fur;
  ctx.fill();
  ctx.clip();
  ctx.fillStyle = furDark;
  ctx.beginPath();
  ctx.arc(CX + 44, headY + 12, 92, 0, Math.PI * 2);
  ctx.fill();
  // Forehead tabby M stripes
  ctx.fillStyle = '#b45309';
  for (const sx of [-18, 0, 18]) {
    roundRectPath(ctx, CX + sx - 5, headY - 82, 10, 30, 5);
    ctx.fill();
  }
  // Cute cream muzzle cheeks
  ctx.fillStyle = belly;
  ctx.beginPath();
  ctx.ellipse(CX - 22, headY + 28, 30, 22, 0, 0, Math.PI * 2);
  ctx.ellipse(CX + 22, headY + 28, 30, 22, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  drawBlobHead(ctx, CX, headY, 96, 84);
  ctx.strokeStyle = INK;
  ctx.lineWidth = OW;
  ctx.stroke();

  // Whiskers
  ctx.strokeStyle = INK;
  ctx.lineWidth = 4.5;
  for (const s of [-1, 1]) {
    for (const wy of [-6, 8, 22]) {
      ctx.beginPath();
      ctx.moveTo(CX + s * 56, headY + 22 + wy * 0.4);
      ctx.lineTo(CX + s * 116, headY + 16 + wy);
      ctx.stroke();
    }
  }

  // Big bright cartoon cat eyes
  const f = resolveFace(state.face || 'smile');
  const blink = blinkAt(t, seed);
  if (blink || f === 'smile' || f === 'laugh' || f === 'relief') {
    ctx.strokeStyle = INK;
    ctx.lineWidth = 6.5;
    for (const s of [-1, 1]) {
      ctx.beginPath();
      ctx.arc(CX + s * 34, headY - 6, 15, Math.PI * 1.12, Math.PI * 1.88);
      ctx.stroke();
    }
  } else {
    for (const s of [-1, 1]) {
      ctx.beginPath();
      ctx.arc(CX + s * 34, headY - 12, 22, 0, Math.PI * 2);
      ctx.fillStyle = '#ffffff';
      ctx.fill();
      ctx.lineWidth = 5;
      ctx.strokeStyle = INK;
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(CX + s * 34, headY - 11, 9.5, 0, Math.PI * 2);
      ctx.fillStyle = INK;
      ctx.fill();
      ctx.beginPath();
      ctx.arc(CX + s * 34 - 4, headY - 16, 3.8, 0, Math.PI * 2);
      ctx.fillStyle = '#ffffff';
      ctx.fill();
    }
  }

  // Pink triangle cat nose + ':3' cat mouth (or tongue lick!)
  ctx.beginPath();
  ctx.moveTo(CX - 12, headY + 10);
  ctx.lineTo(CX + 12, headY + 10);
  ctx.lineTo(CX, headY + 24);
  ctx.closePath();
  ctx.fillStyle = '#ff6b81';
  ctx.fill();
  ctx.strokeStyle = INK;
  ctx.lineWidth = 4.5;
  ctx.stroke();

  ctx.strokeStyle = INK;
  ctx.lineWidth = 5.5;
  ctx.beginPath();
  ctx.arc(CX - 12, headY + 28, 12, 0.1 * Math.PI, 0.92 * Math.PI);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(CX + 12, headY + 28, 12, 0.08 * Math.PI, 0.9 * Math.PI);
  ctx.stroke();

  if (f === 'lick' || f === 'grin') {
    ctx.beginPath();
    ctx.ellipse(CX, headY + 46, 11, 13, 0, 0, Math.PI * 2);
    ctx.fillStyle = '#ff6b81';
    ctx.fill();
    ctx.lineWidth = 4.5;
    ctx.stroke();
  }

  if (state.sweat) drawSweatDrop(ctx, CX, headY, t);
  ctx.restore();
}

/**
 * Draws a single 2D inked character onto a 600x1000 canvas.
 * @param {CanvasRenderingContext2D} ctx
 * @param {object} spec - Character identity (coat, pants, skin, hat, hatColor, hatAccent, glasses, sash, tie, collar, seed, species)
 * @param {object} state - Frame pose ({ face, armL, armR, sweat, talk, propL, propR, hop, lean, t })
 */
export function drawCharacter(ctx, spec, state) {
  if (spec && spec.species === 'cat') {
    drawCatCharacter(ctx, spec, state);
    return;
  }
  ctx.clearRect(0, 0, CW, CH);

  const t = state.t || 0;
  const seed = spec.seed || 1;
  const idleBob = Math.sin(t * 4.1 + seed) * 5.5;
  const hop = state.hop || 0;
  const lean = state.lean || 0;

  const coat = spec.coat || '#2b4c7e';
  const coatShade = shadeHex(coat, -16);
  const pants = spec.pants || '#23293a';
  const skin = spec.skin || '#f4be91';
  const skinShade = shadeHex(skin, -11);

  const hipY = SOLE - LL - hop;
  const torsoTop = hipY - TH + idleBob;
  const torsoX = CX - W / 2;

  const headR = 96;
  const headX = CX + lean * 12;
  const headY = torsoTop - headR + 12;

  const shY = torsoTop + 34;
  const shL = torsoX + 12;
  const shR = torsoX + W - 12;

  ctx.save();
  if (lean) {
    ctx.translate(CX, SOLE);
    ctx.rotate(lean * 0.08);
    ctx.translate(-CX, -SOLE);
  }

  // 1. LEGS & SHOES
  const legOff = 38;
  for (const s of [-1, 1]) {
    const lx = CX + s * legOff;
    ctx.beginPath();
    ctx.moveTo(lx, hipY - 8);
    ctx.lineTo(lx, SOLE - 14);
    ctx.lineCap = 'round';
    ctx.strokeStyle = INK;
    ctx.lineWidth = LIMB + OW * 1.45;
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(lx, hipY - 8);
    ctx.lineTo(lx, SOLE - 14);
    ctx.strokeStyle = pants;
    ctx.lineWidth = LIMB;
    ctx.stroke();

    // Shoe
    ctx.beginPath();
    ctx.ellipse(lx + s * 10, SOLE - 12, 26, 12, 0, Math.PI, 0);
    ctx.closePath();
    ctx.fillStyle = '#3b2417';
    ctx.fill();
    ctx.strokeStyle = INK;
    ctx.lineWidth = 6.5;
    ctx.stroke();
  }

  // 2. ARMS (drawn behind torso unless facepalm/point in front)
  const poseL = state.armL || 'hang';
  const poseR = state.armR || 'hang';
  const aL = armTargets(poseL, -1, shL, shY, t, headX, headY, CX, torsoTop);
  const aR = armTargets(poseR, 1, shR, shY, t, headX, headY, CX, torsoTop);

  if (poseL !== 'facepalm') {
    drawInkedArm(ctx, shL, shY, aL.cpx, aL.cpy, aL.x1, aL.y1, coat, skin);
    if (state.propL) drawHeldProp(ctx, state.propL, aL.x1, aL.y1, -1, t);
  }
  if (poseR !== 'facepalm') {
    drawInkedArm(ctx, shR, shY, aR.cpx, aR.cpy, aR.x1, aR.y1, coat, skin);
    if (state.propR) drawHeldProp(ctx, state.propR, aR.x1, aR.y1, 1, t);
  }

  // 3. TORSO (rounded rectangle with vertical cel shading + collar/tie/sash)
  ctx.save();
  roundRectPath(ctx, torsoX, torsoTop, W, TH, 46);
  ctx.fillStyle = coat;
  ctx.fill();
  ctx.clip();

  // Cel shade right strip
  ctx.fillStyle = coatShade;
  ctx.fillRect(CX + 16, torsoTop, W, TH);

  // V-neck collar
  if (spec.collar !== false) {
    ctx.beginPath();
    ctx.moveTo(CX - 30, torsoTop - 4);
    ctx.lineTo(CX, torsoTop + 56);
    ctx.lineTo(CX + 30, torsoTop - 4);
    ctx.closePath();
    ctx.fillStyle = spec.collarColor || '#f1f3f5';
    ctx.fill();
    ctx.strokeStyle = INK;
    ctx.lineWidth = 5.5;
    ctx.stroke();
  }

  // Tie
  if (spec.tie) {
    ctx.beginPath();
    ctx.moveTo(CX - 11, torsoTop + 26);
    ctx.lineTo(CX + 11, torsoTop + 26);
    ctx.lineTo(CX + 15, torsoTop + 120);
    ctx.lineTo(CX, torsoTop + 144);
    ctx.lineTo(CX - 15, torsoTop + 120);
    ctx.closePath();
    ctx.fillStyle = spec.tie;
    ctx.fill();
    ctx.strokeStyle = INK;
    ctx.lineWidth = 5;
    ctx.stroke();
  }

  // Diagonal sash (like v20 Sultan & Admiral!)
  if (spec.sash) {
    ctx.beginPath();
    ctx.moveTo(torsoX - 10, torsoTop + 14);
    ctx.lineTo(torsoX + 26, torsoTop - 10);
    ctx.lineTo(torsoX + W + 14, torsoTop + TH - 22);
    ctx.lineTo(torsoX + W - 26, torsoTop + TH + 10);
    ctx.closePath();
    ctx.fillStyle = spec.sash;
    ctx.fill();
    ctx.strokeStyle = INK;
    ctx.lineWidth = 5.5;
    ctx.stroke();
  }

  // Lab coat center line & pocket
  if (spec.labcoat) {
    ctx.strokeStyle = INK;
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.moveTo(CX, torsoTop + 54);
    ctx.lineTo(CX, torsoTop + TH);
    ctx.stroke();
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(CX + 22, torsoTop + 78, 34, 26);
    ctx.strokeRect(CX + 22, torsoTop + 78, 34, 26);
  }
  ctx.restore();

  // Torso outer ink contour
  roundRectPath(ctx, torsoX, torsoTop, W, TH, 46);
  ctx.strokeStyle = INK;
  ctx.lineWidth = OW;
  ctx.stroke();

  // 4. HEAD (organic oval blobPts + cel shade crescent + ink contour)
  ctx.save();
  drawBlobHead(ctx, headX, headY, headR * 1.03, headR * 0.94);
  ctx.fillStyle = skin;
  ctx.fill();
  ctx.clip();

  // Right-side curved cel shadow
  ctx.fillStyle = skinShade;
  ctx.beginPath();
  ctx.arc(headX + 46, headY + 12, headR * 0.96, 0, Math.PI * 2);
  ctx.fill();
  // Subtle forehead light highlight
  ctx.fillStyle = 'rgba(255,255,255,0.16)';
  ctx.beginPath();
  ctx.ellipse(headX - 32, headY - 36, 26, 15, -0.45, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  drawBlobHead(ctx, headX, headY, headR * 1.03, headR * 0.94);
  ctx.strokeStyle = INK;
  ctx.lineWidth = OW;
  ctx.stroke();

  // 5. FACE & GLASSES
  const blink = blinkAt(t, seed);
  const talkAmp = state.talk ? (0.45 + 0.55 * Math.abs(Math.sin(t * 17.5 + seed))) : 0;
  drawFace(ctx, state.face || 'neutral', headX, headY, blink, talkAmp, t);
  if (spec.glasses) drawGlasses(ctx, spec.glasses, headX, headY);

  // 6. HAT
  drawHat(ctx, spec.hat, spec.hatColor, spec.hatAccent, headX, headY, headR * 0.94);

  // 7. FACEPALM ARM (in front of head)
  if (poseL === 'facepalm') {
    drawInkedArm(ctx, shL, shY, aL.cpx, aL.cpy, aL.x1, aL.y1, coat, skin);
  }
  if (poseR === 'facepalm') {
    drawInkedArm(ctx, shR, shY, aR.cpx, aR.cpy, aR.x1, aR.y1, coat, skin);
  }

  // 8. ANIMATED SWEAT DROP
  if (state.sweat) drawSweatDrop(ctx, headX, headY, t);

  ctx.restore();
}
