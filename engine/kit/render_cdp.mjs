#!/usr/bin/env node
// engine/kit/render_cdp.mjs — Headless Chromium SwiftShader CDP Frame Renderer
// Exact v9–v20 contract:
//   VW=540, VH=960, WORKERS=2, RESUME=1, CHUNK_SIZE=850
//   Spawns Chrome (--headless=new --no-sandbox --use-angle=swiftshader --enable-unsafe-swiftshader)
//   Waits for window.ready === true, calls window.renderFrame(f) & saves canvas.toDataURL('image/jpeg', 0.92) -> frames/f0000.jpg
//   Uses Node 22 built-in WebSocket + HTTP server (zero external npm packages required).

import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { spawn } from 'node:child_process';

const args = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const [k, ...rest] = a.replace(/^--/, '').split('=');
    return [k, rest.length ? rest.join('=') : '1'];
  })
);

const SCENE_DIR = path.resolve(args.scene || '.');
const ENGINE_ROOT = path.resolve(args.root || path.dirname(path.dirname(new URL(import.meta.url).pathname)));
const OUT_DIR = path.resolve(args.out || path.join(SCENE_DIR, 'frames'));
const START = Number(args.start ?? 0);
const END = Number(args.end ?? 100);
const WORKERS = Number(process.env.WORKERS || args.workers || 2);
const RESUME = String(process.env.RESUME ?? args.resume ?? '1') === '1';
const VW = Number(process.env.VW || args.vw || 540);
const VH = Number(process.env.VH || args.vh || 960);
const CHUNK_SIZE = Number(process.env.CHUNK_SIZE || args.chunk || 850);
const CHROME = process.env.CHROME_BIN || '/usr/bin/google-chrome';

fs.mkdirSync(OUT_DIR, { recursive: true });

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
};

// Local static server exposing both /scene/* and /engine/*
function startServer() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const cleanPath = decodeURIComponent((req.url || '/').split('?')[0]);
      let filePath = null;
      if (cleanPath.startsWith('/engine/')) {
        filePath = path.join(ENGINE_ROOT, cleanPath.slice('/engine/'.length));
      } else if (cleanPath.startsWith('/scene/')) {
        filePath = path.join(SCENE_DIR, cleanPath.slice('/scene/'.length));
      } else {
        filePath = path.join(SCENE_DIR, cleanPath.replace(/^\/+/, '') || 'index.html');
      }
      if (!filePath || !fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
        res.writeHead(404);
        res.end('Not found: ' + cleanPath);
        return;
      }
      const ext = path.extname(filePath).toLowerCase();
      res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
      fs.createReadStream(filePath).pipe(res);
    });
    server.listen(0, '127.0.0.1', () => {
      resolve({ server, port: server.address().port });
    });
  });
}

class CDPClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.id = 0;
    this.pending = new Map();
  }
  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    await new Promise((resolve, reject) => {
      this.ws.addEventListener('open', resolve, { once: true });
      this.ws.addEventListener('error', reject, { once: true });
    });
    this.ws.addEventListener('message', (ev) => {
      const msg = JSON.parse(String(ev.data));
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve(msg.result);
      }
    });
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (r.exceptionDetails) {
      throw new Error('JS exception: ' + JSON.stringify(r.exceptionDetails));
    }
    return r.result?.value;
  }
  close() {
    try { this.ws.close(); } catch {}
  }
}

async function waitForDevTools(port, timeoutMs = 15000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/list`);
      if (res.ok) {
        const list = await res.json();
        const page = list.find((t) => t.type === 'page' && t.webSocketDebuggerUrl);
        if (page) return page.webSocketDebuggerUrl;
      }
    } catch {}
    await new Promise((r) => setTimeout(r, 150));
  }
  throw new Error(`Chrome DevTools did not respond on port ${port}`);
}

async function runWorker(workerIdx, frames, url) {
  if (!frames.length) return;
  const userDir = `/tmp/akil_cdp_${process.pid}_${workerIdx}_${Date.now()}`;
  const debugPort = 29000 + ((process.pid + workerIdx * 37) % 10000);

  const proc = spawn(CHROME, [
    '--headless=new',
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--use-angle=swiftshader',
    '--enable-unsafe-swiftshader',
    '--enable-webgl',
    '--ignore-gpu-blocklist',
    `--window-size=${VW},${VH}`,
    `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=${userDir}`,
    'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] });

  let stderrBuf = '';
  proc.stderr.on('data', (d) => { stderrBuf += String(d).slice(-400); });

  let cdp = null;
  try {
    const wsUrl = await waitForDevTools(debugPort);
    cdp = new CDPClient(wsUrl);
    await cdp.connect();
    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: VW,
      height: VH,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await cdp.send('Page.navigate', { url });

    // Wait for window.ready === true
    const tReady = Date.now();
    while (true) {
      const ready = await cdp.eval('Boolean(window.ready)');
      if (ready) break;
      const err = await cdp.eval('window.__bootError || ""');
      if (err) throw new Error('Scene boot error: ' + err);
      if (Date.now() - tReady > 25000) {
        throw new Error(`Timed out waiting for window.ready on worker ${workerIdx}`);
      }
      await new Promise((r) => setTimeout(r, 120));
    }

    let done = 0;
    const t0 = Date.now();
    for (const f of frames) {
      const fname = path.join(OUT_DIR, `f${String(f).padStart(4, '0')}.jpg`);
      if (RESUME && fs.existsSync(fname) && fs.statSync(fname).size > 2500) {
        done++;
        continue;
      }
      const dataUrl = await cdp.eval(
        `(function(){ window.renderFrame(${f}); return document.querySelector('canvas').toDataURL('image/jpeg', 0.92); })()`
      );
      const comma = dataUrl.indexOf(',');
      const buf = Buffer.from(dataUrl.slice(comma + 1), 'base64');
      fs.writeFileSync(fname, buf);
      done++;
      if (done % 100 === 0 || done === frames.length) {
        const dt = (Date.now() - t0) / 1000;
        const fps = (done / Math.max(0.1, dt)).toFixed(1);
        console.log(`  [W${workerIdx}] ${done}/${frames.length} frames (${fps} fps)`);
      }
    }
  } finally {
    if (cdp) cdp.close();
    proc.kill('SIGKILL');
    try { fs.rmSync(userDir, { recursive: true, force: true }); } catch {}
  }
}

async function main() {
  const { server, port } = await startServer();
  const url = `http://127.0.0.1:${port}/scene/index.html`;

  try {
    if (args.frames) {
      const pick = args.frames.split(',').map((s) => Number(s.trim())).filter((n) => Number.isFinite(n));
      console.log(`[CDP] Preview rendering ${pick.length} selected frames (${VW}x${VH})...`);
      await runWorker(0, pick, url);
      console.log(`[CDP] Preview done in ${OUT_DIR}`);
      return;
    }
    // Process in chunks of CHUNK_SIZE (default 850) to keep SwiftShader memory fresh
    for (let cStart = START; cStart < END; cStart += CHUNK_SIZE) {
      const cEnd = Math.min(END, cStart + CHUNK_SIZE);
      const todo = [];
      for (let f = cStart; f < cEnd; f++) {
        const fname = path.join(OUT_DIR, `f${String(f).padStart(4, '0')}.jpg`);
        if (RESUME && fs.existsSync(fname) && fs.statSync(fname).size > 2500) continue;
        todo.push(f);
      }
      if (!todo.length) {
        console.log(`[CDP] Chunk ${cStart}..${cEnd - 1} already rendered (RESUME=1).`);
        continue;
      }
      console.log(`[CDP] Rendering chunk ${cStart}..${cEnd - 1} (${todo.length} frames, ${WORKERS} workers, ${VW}x${VH})...`);
      const buckets = Array.from({ length: WORKERS }, () => []);
      todo.forEach((f, idx) => buckets[idx % WORKERS].push(f));
      await Promise.all(buckets.map((b, wi) => runWorker(wi, b, url)));
    }
    console.log(`[CDP] Done: ${END - START} frames in ${OUT_DIR}`);
  } finally {
    server.close();
  }
}

main().catch((err) => {
  console.error('[CDP ERROR]', err);
  process.exit(1);
});
