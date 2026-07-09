"""Generate a self-contained interactive HTML map of the transit network.

Embeds the graph (stops, route edges, transfer edges) and the per-stop
centrality scores into a single HTML file with no external dependencies:
pan by dragging, zoom with the mouse wheel or buttons, click a stop for its
node id, centrality scores and the lines serving it, and switch the metric
that drives colour and size.

Usage: python src/make_html_map.py   ->  output/network_map.html
"""

import json
from pathlib import Path

from build_network import add_transfer_edges, build_graph
from centrality_analysis import TRANSFER_WALK_DIST, compute_centralities

OUTPUT = Path(__file__).resolve().parent.parent / "output" / "network_map.html"

METRICS = ["hub_score", "betweenness", "closeness", "degree", "n_lines", "pagerank", "eigenvector"]


def collect_data(G=None, df=None):
    if G is None:
        G = build_graph()
        add_transfer_edges(G, TRANSFER_WALK_DIST)
    if df is None:
        df = compute_centralities(G)

    ids = list(df.index)
    index_of = {n: i for i, n in enumerate(ids)}
    nodes = [
        [
            int(n),
            round(float(r["x"]), 1),
            round(float(r["y"]), 1),
            int(r["degree"]),
            int(r["n_lines"]),
            round(float(r["betweenness"]), 6),
            round(float(r["closeness"]), 6),
            round(float(r["pagerank"]), 6),
            round(float(r["eigenvector"]), 6),
            round(float(r["hub_score"]), 4),
            r["lines"],
        ]
        for n, r in df.iterrows()
    ]
    edges = [
        [index_of[u], index_of[v], 1 if a.get("transfer") else 0]
        for u, v, a in G.edges(data=True)
    ]
    return nodes, edges


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root {
    --surface: #fcfcfb; --panel: #f9f9f7; --ink: #0b0b0b; --ink2: #52514e;
    --muted: #898781; --grid: #e1e0d9; --baseline: #c3c2b7; --accent: #2a78d6;
    --border: rgba(11,11,11,0.10); --edge: #c3c2b7; --edge-transfer: #e1e0d9;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --surface: #1a1a19; --panel: #0d0d0d; --ink: #ffffff; --ink2: #c3c2b7;
      --muted: #898781; --grid: #2c2c2a; --baseline: #383835; --accent: #3987e5;
      --border: rgba(255,255,255,0.10); --edge: #383835; --edge-transfer: #2c2c2a;
    }
  }
  * { box-sizing: border-box; margin: 0; }
  html, body { height: 100%; }
  body {
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    background: var(--panel); color: var(--ink); overflow: hidden;
    display: flex; flex-direction: column;
  }
  header {
    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
    padding: 10px 16px; border-bottom: 1px solid var(--border); background: var(--surface);
  }
  header h1 { font-size: 15px; font-weight: 600; }
  header .sub { font-size: 12px; color: var(--muted); }
  select {
    font: inherit; font-size: 13px; color: var(--ink); background: var(--surface);
    border: 1px solid var(--baseline); border-radius: 6px; padding: 4px 8px;
  }
  label { font-size: 12px; color: var(--ink2); }
  #legend { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--muted); }
  #legend .bar {
    width: 120px; height: 10px; border-radius: 5px; border: 1px solid var(--border);
    background: linear-gradient(90deg,#cde2fb,#9ec5f4,#6da7ec,#3987e5,#256abf,#184f95,#0d366b);
  }
  #wrap { position: relative; flex: 1; }
  canvas { position: absolute; inset: 0; width: 100%; height: 100%; cursor: grab; }
  canvas.dragging { cursor: grabbing; }
  #zoombtns {
    position: absolute; top: 12px; left: 12px; display: flex; flex-direction: column; gap: 6px;
  }
  #zoombtns button {
    width: 32px; height: 32px; font-size: 16px; color: var(--ink2); cursor: pointer;
    background: var(--surface); border: 1px solid var(--baseline); border-radius: 6px;
  }
  #zoombtns button:hover { border-color: var(--accent); color: var(--accent); }
  #tooltip {
    position: absolute; pointer-events: none; display: none; z-index: 5;
    background: var(--surface); color: var(--ink); font-size: 12px;
    border: 1px solid var(--border); border-radius: 6px; padding: 4px 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15); white-space: nowrap;
  }
  #detail {
    position: absolute; top: 12px; right: 12px; width: 260px; max-height: calc(100% - 24px);
    overflow-y: auto; display: none; z-index: 4;
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 14px; box-shadow: 0 4px 16px rgba(0,0,0,0.18);
  }
  #detail h2 { font-size: 15px; margin-bottom: 2px; }
  #detail .rank { font-size: 12px; color: var(--muted); margin-bottom: 10px; }
  #detail table { width: 100%; border-collapse: collapse; font-size: 12px; }
  #detail td { padding: 3px 0; border-bottom: 1px solid var(--grid); }
  #detail td:first-child { color: var(--ink2); }
  #detail td:last-child { text-align: right; font-variant-numeric: tabular-nums; }
  #detail h3 { font-size: 11px; color: var(--muted); font-weight: 600; margin: 10px 0 6px; text-transform: uppercase; letter-spacing: .04em; }
  #detail .chips { display: flex; flex-wrap: wrap; gap: 4px; }
  #detail .chip {
    font-size: 11px; color: var(--ink2); background: var(--panel);
    border: 1px solid var(--grid); border-radius: 10px; padding: 1px 7px;
  }
  #detail .close {
    position: absolute; top: 8px; right: 10px; border: 0; background: none;
    color: var(--muted); font-size: 16px; cursor: pointer;
  }
  #hint {
    position: absolute; bottom: 10px; left: 12px; font-size: 11px; color: var(--muted);
    background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 3px 8px;
  }
</style>
</head>
<body>
<header>
  <div>
    <h1>__TITLE__</h1>
    <div class="sub" id="stats"></div>
  </div>
  <label>colour &amp; size by
    <select id="metric">__METRIC_OPTIONS__</select>
  </label>
  <div id="legend"><span>low</span><div class="bar"></div><span>high (percentile)</span></div>
</header>
<div id="wrap">
  <canvas id="cv"></canvas>
  <div id="zoombtns">
    <button id="zin" title="zoom in">+</button>
    <button id="zout" title="zoom out">−</button>
    <button id="zfit" title="fit to view" style="font-size:12px">⤢</button>
  </div>
  <div id="tooltip"></div>
  <div id="detail">
    <button class="close" id="closeDetail">✕</button>
    <h2 id="dTitle"></h2>
    <div class="rank" id="dRank"></div>
    <table id="dTable"></table>
    <h3 id="dLinesHead"></h3>
    <div class="chips" id="dLines"></div>
  </div>
  <div id="hint">drag to pan · scroll to zoom · click a stop for details</div>
</div>
<script>
const NODES = __NODES__;
const EDGES = __EDGES__;
const METRICS = __METRICS__;
const COL = {id:0, x:1, y:2, degree:3, n_lines:4, betweenness:5, closeness:6,
             pagerank:7, eigenvector:8, hub_score:9, lines:10};
const RAMP = ['#cde2fb','#9ec5f4','#6da7ec','#3987e5','#256abf','#184f95','#0d366b'];

const cv = document.getElementById('cv');
const ctx = cv.getContext('2d');
const tooltip = document.getElementById('tooltip');
const detail = document.getElementById('detail');

let metric = 'hub_score';
let pct = [];              // percentile 0..1 per node for current metric
let scale = 1, tx = 0, ty = 0;
let hoverIdx = -1, selectedIdx = -1;

const minX = Math.min(...NODES.map(n => n[COL.x]));
const maxX = Math.max(...NODES.map(n => n[COL.x]));
const minY = Math.min(...NODES.map(n => n[COL.y]));
const maxY = Math.max(...NODES.map(n => n[COL.y]));

function computePercentiles() {
  const c = COL[metric];
  const order = NODES.map((n, i) => [n[c], i]).sort((a, b) => a[0] - b[0]);
  pct = new Array(NODES.length);
  order.forEach(([, i], rank) => { pct[i] = order.length > 1 ? rank / (order.length - 1) : 1; });
}

function rampColor(t) {
  const s = Math.min(Math.max(t, 0), 1) * (RAMP.length - 1);
  const i = Math.min(Math.floor(s), RAMP.length - 2), f = s - i;
  const a = RAMP[i], b = RAMP[i + 1];
  const ch = (h, k) => parseInt(h.slice(k, k + 2), 16);
  const mix = k => Math.round(ch(a, k) + (ch(b, k) - ch(a, k)) * f);
  return `rgb(${mix(1)},${mix(3)},${mix(5)})`;
}

// world (ITM metres, y north-up) -> screen px
const sx = x => x * scale + tx;
const sy = y => -y * scale + ty;

function fit() {
  const w = cv.clientWidth, h = cv.clientHeight, pad = 40;
  scale = Math.min((w - 2 * pad) / (maxX - minX), (h - 2 * pad) / (maxY - minY));
  tx = (w - (maxX + minX) * scale) / 2;
  ty = (h + (maxY + minY) * scale) / 2;
}

function radius(i) { return 2 + 6 * pct[i] + (i === selectedIdx ? 2 : 0); }

function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

function draw() {
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth, h = cv.clientHeight;
  if (cv.width !== w * dpr || cv.height !== h * dpr) { cv.width = w * dpr; cv.height = h * dpr; }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = css('--surface');
  ctx.fillRect(0, 0, w, h);

  const edgeCol = css('--edge'), transferCol = css('--edge-transfer');
  ctx.lineWidth = 0.8;
  for (const [u, v, t] of EDGES) {
    const x1 = sx(NODES[u][COL.x]), y1 = sy(NODES[u][COL.y]);
    const x2 = sx(NODES[v][COL.x]), y2 = sy(NODES[v][COL.y]);
    if ((x1 < -50 && x2 < -50) || (x1 > w + 50 && x2 > w + 50) ||
        (y1 < -50 && y2 < -50) || (y1 > h + 50 && y2 > h + 50)) continue;
    ctx.strokeStyle = t ? transferCol : edgeCol;
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
  }

  // low percentile first so hubs draw on top
  const order = NODES.map((_, i) => i).sort((a, b) => pct[a] - pct[b]);
  for (const i of order) {
    const x = sx(NODES[i][COL.x]), y = sy(NODES[i][COL.y]);
    if (x < -20 || x > w + 20 || y < -20 || y > h + 20) continue;
    const r = radius(i);
    ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI);
    ctx.fillStyle = rampColor(pct[i]);
    ctx.fill();
    if (i === selectedIdx || i === hoverIdx) {
      ctx.lineWidth = 2; ctx.strokeStyle = css('--ink'); ctx.stroke(); ctx.lineWidth = 0.8;
    }
  }
}

function hitTest(mx, my) {
  // among nodes under the pointer prefer the topmost-drawn (highest
  // percentile) one, so dense overlaps select the node the user sees
  let top = -1, near = -1, nearD = 1e9;
  for (let i = 0; i < NODES.length; i++) {
    const dx = sx(NODES[i][COL.x]) - mx, dy = sy(NODES[i][COL.y]) - my;
    const d = dx * dx + dy * dy, r = radius(i);
    if (d < r * r && (top < 0 || pct[i] > pct[top])) top = i;
    const hit = Math.max(r, 7);
    if (d < hit * hit && d < nearD) { nearD = d; near = i; }
  }
  return top >= 0 ? top : near;
}

const fmt = (v, digits) => Number(v).toLocaleString('en-US', {maximumFractionDigits: digits});

function showDetail(i) {
  selectedIdx = i;
  const n = NODES[i];
  const c = COL[metric];
  const rank = NODES.map((m, j) => [m[c], j]).sort((a, b) => b[0] - a[0]).findIndex(p => p[1] === i) + 1;
  document.getElementById('dTitle').textContent = 'Stop ' + n[COL.id];
  document.getElementById('dRank').textContent = `rank ${rank} of ${NODES.length} by ${metric.replace('_',' ')}`;
  const rows = [
    ['hub score', fmt(n[COL.hub_score], 3)],
    ['betweenness', fmt(n[COL.betweenness], 4)],
    ['closeness (1/km)', fmt(n[COL.closeness], 4)],
    ['degree', n[COL.degree]],
    ['lines served', n[COL.n_lines]],
    ['pagerank', fmt(n[COL.pagerank], 5)],
    ['eigenvector', fmt(n[COL.eigenvector], 4)],
    ['X / Y (ITM)', fmt(n[COL.x], 0) + ' / ' + fmt(n[COL.y], 0)],
  ];
  document.getElementById('dTable').innerHTML =
    rows.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join('');
  const lines = n[COL.lines] ? n[COL.lines].split(', ') : [];
  document.getElementById('dLinesHead').textContent = `lines (${lines.length})`;
  document.getElementById('dLines').innerHTML =
    lines.map(l => `<span class="chip">${l.replace(/&/g,'&amp;').replace(/</g,'&lt;')}</span>`).join('');
  detail.style.display = 'block';
  draw();
}

// --- interactions ---------------------------------------------------------
let dragging = false, moved = false, lastX = 0, lastY = 0;

cv.addEventListener('mousedown', e => {
  dragging = true; moved = false; lastX = e.clientX; lastY = e.clientY;
  cv.classList.add('dragging');
});
window.addEventListener('mouseup', () => { dragging = false; cv.classList.remove('dragging'); });
cv.addEventListener('mousemove', e => {
  const rect = cv.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  if (dragging) {
    const dx = e.clientX - lastX, dy = e.clientY - lastY;
    if (Math.abs(dx) + Math.abs(dy) > 2) moved = true;
    tx += dx; ty += dy; lastX = e.clientX; lastY = e.clientY;
    tooltip.style.display = 'none';
    draw();
    return;
  }
  const i = hitTest(mx, my);
  if (i !== hoverIdx) { hoverIdx = i; draw(); }
  if (i >= 0) {
    tooltip.textContent = `stop ${NODES[i][COL.id]} — ${metric.replace('_',' ')} ${fmt(NODES[i][COL[metric]], 4)}`;
    tooltip.style.left = (mx + 12) + 'px';
    tooltip.style.top = (my - 8) + 'px';
    tooltip.style.display = 'block';
    cv.style.cursor = 'pointer';
  } else {
    tooltip.style.display = 'none';
    cv.style.cursor = 'grab';
  }
});
cv.addEventListener('click', e => {
  if (moved) return;
  const rect = cv.getBoundingClientRect();
  const i = hitTest(e.clientX - rect.left, e.clientY - rect.top);
  if (i >= 0) showDetail(i);
  else { selectedIdx = -1; detail.style.display = 'none'; draw(); }
});
cv.addEventListener('wheel', e => {
  e.preventDefault();
  const rect = cv.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  const f = Math.exp(-e.deltaY * 0.0015);
  tx = mx - (mx - tx) * f;
  ty = my - (my - ty) * f;
  scale *= f;
  draw();
}, { passive: false });

function zoom(f) {
  const mx = cv.clientWidth / 2, my = cv.clientHeight / 2;
  tx = mx - (mx - tx) * f; ty = my - (my - ty) * f; scale *= f; draw();
}
document.getElementById('zin').onclick = () => zoom(1.4);
document.getElementById('zout').onclick = () => zoom(1 / 1.4);
document.getElementById('zfit').onclick = () => { fit(); draw(); };
document.getElementById('closeDetail').onclick = () => {
  selectedIdx = -1; detail.style.display = 'none'; draw();
};
document.getElementById('metric').onchange = e => {
  metric = e.target.value;
  computePercentiles();
  if (selectedIdx >= 0) showDetail(selectedIdx);
  draw();
};
window.addEventListener('resize', draw);
if (window.matchMedia) {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', draw);
}

const nRoute = EDGES.filter(e => !e[2]).length;
document.getElementById('stats').textContent =
  `${NODES.length} stops · ${nRoute} route edges · ${EDGES.length - nRoute} walking-transfer edges`;

computePercentiles();
fit();
draw();
</script>
</body>
</html>
"""


def render_map(out_path: Path, G=None, df=None,
               title: str = "Transit network — stop centrality") -> None:
    nodes, edges = collect_data(G, df)
    options = "".join(
        f'<option value="{m}"{" selected" if m == "hub_score" else ""}>{m.replace("_", " ")}</option>'
        for m in METRICS
    )
    html = (
        HTML_TEMPLATE
        .replace("__TITLE__", title)
        .replace("__METRIC_OPTIONS__", options)
        .replace("__NODES__", json.dumps(nodes, separators=(",", ":")))
        .replace("__EDGES__", json.dumps(edges, separators=(",", ":")))
        .replace("__METRICS__", json.dumps(METRICS))
    )
    out_path.write_text(html, encoding="utf-8")
    print(f"wrote {out_path} ({out_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    render_map(OUTPUT)
