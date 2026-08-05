/* Kurva equity + drawdown sebagai SVG inline.
 *
 * Digambar sendiri, tanpa pustaka: satu berkas kurang dari 150 baris jauh lebih
 * ringan daripada menarik pustaka chart, dan warnanya bisa ikut variabel CSS
 * sehingga mode terang/gelap tidak perlu diurus dua kali.
 */

const NS = 'http://www.w3.org/2000/svg';

function el(name, attrs = {}) {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  return node;
}

function niceTicks(min, max, count = 4) {
  const span = max - min;
  if (!(span > 0)) return [min];
  const rawStep = span / count;
  const mag = 10 ** Math.floor(Math.log10(rawStep));
  const norm = rawStep / mag;
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) ticks.push(v);
  return ticks;
}

function formatMoney(v) {
  if (Math.abs(v) >= 10000) return `${Math.round(v / 1000)}k`;
  return Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1);
}

function formatDate(ts) {
  return new Date(ts).toISOString().slice(0, 10);
}

/** Kurangi titik menjadi maksimal `target` supaya SVG tetap ringan pada data
 *  puluhan ribu bar. Ekstrem tiap bucket dipertahankan agar bentuk drawdown
 *  tidak hilang saat di-downsample. */
function downsample(ts, values, target) {
  const n = values.length;
  if (n <= target) {
    const pts = [];
    for (let i = 0; i < n; i += 1) pts.push([ts[i], values[i]]);
    return pts;
  }
  const bucket = Math.ceil(n / target);
  const pts = [];
  for (let start = 0; start < n; start += bucket) {
    const end = Math.min(n, start + bucket);
    let lo = Infinity;
    let hi = -Infinity;
    let loI = start;
    let hiI = start;
    for (let i = start; i < end; i += 1) {
      if (values[i] < lo) { lo = values[i]; loI = i; }
      if (values[i] > hi) { hi = values[i]; hiI = i; }
    }
    const first = Math.min(loI, hiI);
    const second = Math.max(loI, hiI);
    pts.push([ts[first], values[first]]);
    if (second !== first) pts.push([ts[second], values[second]]);
  }
  pts.push([ts[n - 1], values[n - 1]]);
  return pts;
}

/** Gambar kurva equity ke dalam sebuah <svg>. */
export function drawEquity(svg, ts, equity, initialEquity) {
  svg.replaceChildren();
  if (!equity || equity.length < 2) return;

  const width = 900;
  const height = 260;
  const pad = { top: 14, right: 14, bottom: 24, left: 52 };
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.setAttribute('preserveAspectRatio', 'none');

  const points = downsample(ts, equity, 900);

  let lo = Infinity;
  let hi = -Infinity;
  for (const [, v] of points) {
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  lo = Math.min(lo, initialEquity);
  hi = Math.max(hi, initialEquity);
  const padding = (hi - lo) * 0.08 || Math.max(1, Math.abs(hi) * 0.02);
  lo -= padding;
  hi += padding;

  const t0 = points[0][0];
  const t1 = points[points.length - 1][0];
  const x = (t) => pad.left + ((t - t0) / (t1 - t0 || 1)) * (width - pad.left - pad.right);
  const y = (v) => pad.top + (1 - (v - lo) / (hi - lo || 1)) * (height - pad.top - pad.bottom);

  for (const tick of niceTicks(lo, hi, 4)) {
    svg.append(
      el('line', {
        class: 'grid-line',
        x1: pad.left,
        x2: width - pad.right,
        y1: y(tick),
        y2: y(tick),
      }),
    );
    const label = el('text', {
      class: 'axis-text',
      x: pad.left - 6,
      y: y(tick) + 3.5,
      'text-anchor': 'end',
    });
    label.textContent = formatMoney(tick);
    svg.append(label);
  }

  // Garis modal awal: acuan untung/rugi yang paling sering dicari mata.
  svg.append(
    el('line', {
      class: 'baseline',
      x1: pad.left,
      x2: width - pad.right,
      y1: y(initialEquity),
      y2: y(initialEquity),
    }),
  );

  const d = points.map(([t, v], i) => `${i ? 'L' : 'M'}${x(t).toFixed(1)},${y(v).toFixed(1)}`).join('');
  svg.append(
    el('path', {
      class: 'equity-fill',
      d: `${d}L${x(t1).toFixed(1)},${y(initialEquity).toFixed(1)}L${x(t0).toFixed(1)},${y(initialEquity).toFixed(1)}Z`,
    }),
  );
  svg.append(el('path', { class: 'equity-line', d }));

  for (const [t, anchor] of [[t0, 'start'], [t1, 'end']]) {
    const label = el('text', {
      class: 'axis-text',
      x: x(t),
      y: height - 8,
      'text-anchor': anchor,
    });
    label.textContent = formatDate(t);
    svg.append(label);
  }
}

/** Gambar kurva drawdown (persen, selalu ≤ 0). */
export function drawDrawdown(svg, ts, equity) {
  svg.replaceChildren();
  if (!equity || equity.length < 2) return;

  const dd = new Float64Array(equity.length);
  let peak = -Infinity;
  for (let i = 0; i < equity.length; i += 1) {
    peak = Math.max(peak, equity[i]);
    dd[i] = peak > 0 ? ((equity[i] - peak) / peak) * 100 : 0;
  }

  const width = 900;
  const height = 140;
  const pad = { top: 12, right: 14, bottom: 20, left: 52 };
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.setAttribute('preserveAspectRatio', 'none');

  const points = downsample(ts, dd, 900);
  let lo = 0;
  for (const [, v] of points) lo = Math.min(lo, v);
  lo = Math.min(lo * 1.1, -0.5);

  const t0 = points[0][0];
  const t1 = points[points.length - 1][0];
  const x = (t) => pad.left + ((t - t0) / (t1 - t0 || 1)) * (width - pad.left - pad.right);
  const y = (v) => pad.top + (1 - (v - lo) / (0 - lo || 1)) * (height - pad.top - pad.bottom);

  for (const tick of niceTicks(lo, 0, 3)) {
    svg.append(
      el('line', { class: 'grid-line', x1: pad.left, x2: width - pad.right, y1: y(tick), y2: y(tick) }),
    );
    const label = el('text', { class: 'axis-text', x: pad.left - 6, y: y(tick) + 3.5, 'text-anchor': 'end' });
    label.textContent = `${tick.toFixed(0)}%`;
    svg.append(label);
  }

  const d = points.map(([t, v], i) => `${i ? 'L' : 'M'}${x(t).toFixed(1)},${y(v).toFixed(1)}`).join('');
  svg.append(el('path', { class: 'dd-line', d }));
}
