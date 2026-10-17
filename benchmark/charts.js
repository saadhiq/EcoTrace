// Slide-ready charts (1600x900 PNG) from benchmark/results/*.json. Plain SVG rendered with Playwright.
// Usage: node benchmark/charts.js   (needs Playwright)
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const DIR = __dirname;
const gem = JSON.parse(fs.readFileSync(path.join(DIR, 'results/live_gemini.json'), 'utf8'));
const load = JSON.parse(fs.readFileSync(path.join(DIR, 'results/load_health.json'), 'utf8'));
const W = 1600, H = 900, M = { l: 150, r: 80, t: 170, b: 120 };
const INK = '#17201b', MUTED = '#5b6b62', GRID = '#dce3de', BAR = '#1f7a4d', REF = '#a15c00';

function page(title, subtitle, svg) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;width:${W}px;height:${H}px;background:#fff;font-family:"Segoe UI",Arial,sans-serif;color:${INK}}
h1{position:absolute;left:${M.l - 90}px;top:36px;margin:0;font-size:40px}
p{position:absolute;left:${M.l - 90}px;top:94px;margin:0;font-size:22px;color:${MUTED}}
svg{position:absolute;left:0;top:0}text{font-family:"Segoe UI",Arial,sans-serif}</style></head>
<body><h1>${title}</h1><p>${subtitle}</p><svg width="${W}" height="${H}">${svg}</svg></body></html>`;
}

function latencyChart() {
  const rows = gem.records.filter((r) => r.latencyMs != null);
  const max = 4000, pw = W - M.l - M.r, ph = H - M.t - M.b;
  const bh = Math.min(70, (ph / rows.length) * 0.62), step = ph / rows.length;
  const x = (v) => M.l + (v / max) * pw;
  let s = '';
  for (let v = 0; v <= max; v += 1000) {
    s += `<line x1="${x(v)}" x2="${x(v)}" y1="${M.t}" y2="${H - M.b}" stroke="${GRID}"/>`;
    s += `<text x="${x(v)}" y="${H - M.b + 34}" font-size="20" fill="${MUTED}" text-anchor="middle">${v / 1000} s</text>`;
  }
  for (const [label, v] of [[`avg ${(gem.summary.avgLatencyMs / 1000).toFixed(2)} s`, gem.summary.avgLatencyMs], [`p95 ${(gem.summary.p95LatencyMs / 1000).toFixed(2)} s`, gem.summary.p95LatencyMs]]) {
    s += `<line x1="${x(v)}" x2="${x(v)}" y1="${M.t - 18}" y2="${H - M.b}" stroke="${REF}" stroke-width="2" stroke-dasharray="8 6"/>`;
    s += `<text x="${x(v) + 6}" y="${M.t - 26}" font-size="20" fill="${INK}" font-weight="600">${label}</text>`;
  }
  rows.forEach((r, i) => {
    const y = M.t + i * step + (step - bh) / 2;
    s += `<rect x="${M.l}" y="${y}" width="${x(r.latencyMs) - M.l}" height="${bh}" rx="4" fill="${BAR}"/>`;
    s += `<text x="${M.l - 14}" y="${y + bh / 2 + 7}" font-size="20" fill="${INK}" text-anchor="end">Bag ${i + 1}</text>`;
    const label = `${(r.latencyMs / 1000).toFixed(2)} s · ${r.aiItems} items`;
    s += `<rect x="${x(r.latencyMs) + 6}" y="${y + bh / 2 - 16}" width="${label.length * 10.5 + 12}" height="32" fill="#fff"/>`;
    s += `<text x="${x(r.latencyMs) + 12}" y="${y + bh / 2 + 7}" font-size="20" fill="${INK}">${label}</text>`;
  });
  s += `<text x="${M.l + pw / 2}" y="${H - 30}" font-size="20" fill="${MUTED}" text-anchor="middle">Server-measured Gemini call time per bag photo (gemini-3.5-flash, thinking minimal, asia-south1)</text>`;
  return page('Gemini classification latency per bag', `${rows.length} real Gemini runs on live Cloud Run (development + smoke tests) · 0 invalid outputs`, s);
}

function healthChart() {
  const lat = load.latencies_ms, binW = 20, maxV = 420;
  const bins = Array(Math.ceil(maxV / binW)).fill(0);
  lat.forEach((v) => { bins[Math.min(bins.length - 1, Math.floor(v / binW))] += 1; });
  const pw = W - M.l - M.r, ph = H - M.t - M.b, top = Math.max(...bins);
  const ymax = Math.ceil(top / 500) * 500;
  const x = (v) => M.l + (v / maxV) * pw, y = (n) => H - M.b - (n / ymax) * ph;
  let s = '';
  for (let n = 0; n <= ymax; n += 500) {
    s += `<line x1="${M.l}" x2="${W - M.r}" y1="${y(n)}" y2="${y(n)}" stroke="${GRID}"/>`;
    s += `<text x="${M.l - 14}" y="${y(n) + 7}" font-size="20" fill="${MUTED}" text-anchor="end">${n}</text>`;
  }
  bins.forEach((n, i) => {
    if (!n) return;
    const bw = (binW / maxV) * pw - 2;
    s += `<rect x="${x(i * binW) + 1}" y="${y(n)}" width="${bw}" height="${H - M.b - y(n)}" rx="3" fill="${BAR}"/>`;
  });
  for (let v = 0; v <= maxV; v += 60) s += `<text x="${x(v)}" y="${H - M.b + 34}" font-size="20" fill="${MUTED}" text-anchor="middle">${v} ms</text>`;
  [['p50', load.p50_ms], ['p95', load.p95_ms], ['p99', load.p99_ms]].forEach(([k, v], i) => {
    s += `<line x1="${x(v)}" x2="${x(v)}" y1="${M.t - 10 + i * 30}" y2="${H - M.b}" stroke="${REF}" stroke-width="2" stroke-dasharray="8 6"/>`;
    s += `<text x="${x(v) + 6}" y="${M.t - 16 + i * 30}" font-size="20" fill="${INK}" font-weight="600">${k} ${Math.round(v)} ms</text>`;
  });
  s += `<text x="${M.l + pw / 2}" y="${H - 30}" font-size="20" fill="${MUTED}" text-anchor="middle">Round-trip time per GET /health from a laptop in Sri Lanka (includes network), 20 ms bins · y = requests</text>`;
  return page('Cloud Run under load: GET /health', `${load.users} concurrent users × ${load.seconds} s · ${load.requests.toLocaleString('en')} requests · ${load.rps} req/s · ${load.errors} errors`, s);
}

(async () => {
  const browser = await chromium.launch();
  const p = await browser.newPage({ viewport: { width: W, height: H } });
  for (const [name, html] of [['gemini-latency', latencyChart()], ['health-load', healthChart()]]) {
    await p.setContent(html);
    await p.screenshot({ path: path.join(DIR, 'results', `${name}.png`) });
    console.log(name, 'ok');
  }
  await browser.close();
})();
