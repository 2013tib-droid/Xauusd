/* Indikator teknikal — port 1:1 dari xauusd/indicators.py.
 *
 * Semua fungsi menerima objek bar `{ open, high, low, close, ts, … }` berisi
 * Float64Array sejajar, dan tidak melihat data masa depan kecuali disebut
 * eksplisit.
 */

import { and, boolArray, diff, ewm, ewmSpan, ffill, gt, gte, lt, lte, shift } from './series.js';

export const ema = ewmSpan;

/** True Range. Bar pertama memakai high−low, karena prev_close belum ada. */
export function trueRange(df) {
  const { high, low, close } = df;
  const n = high.length;
  const out = new Float64Array(n);
  for (let i = 0; i < n; i += 1) {
    const hl = high[i] - low[i];
    if (i === 0) {
      out[i] = hl;
      continue;
    }
    const pc = close[i - 1];
    out[i] = Math.max(hl, Math.abs(high[i] - pc), Math.abs(low[i] - pc));
  }
  return out;
}

/** Average True Range dengan smoothing Wilder. */
export function atr(df, period = 14) {
  return ewm(trueRange(df), 1 / period);
}

/** Average Directional Index — kekuatan tren, bukan arahnya. */
export function adx(df, period = 14) {
  const n = df.high.length;
  const up = diff(df.high);
  const down = diff(df.low);

  const plusDm = new Float64Array(n);
  const minusDm = new Float64Array(n);
  for (let i = 0; i < n; i += 1) {
    const u = up[i];
    const d = -down[i];
    // Perbandingan yang melibatkan NaN bernilai false, jadi bar pertama = 0.
    plusDm[i] = u > d && u > 0 ? u : 0;
    minusDm[i] = d > u && d > 0 ? d : 0;
  }

  const alpha = 1 / period;
  const tr = ewm(trueRange(df), alpha);
  const plusSm = ewm(plusDm, alpha);
  const minusSm = ewm(minusDm, alpha);

  const dx = new Float64Array(n);
  for (let i = 0; i < n; i += 1) {
    const t = tr[i];
    // `.replace(0, np.nan)` di sisi Python: pembagian dengan nol jadi NaN.
    const pdi = t === 0 || Number.isNaN(t) ? NaN : (100 * plusSm[i]) / t;
    const mdi = t === 0 || Number.isNaN(t) ? NaN : (100 * minusSm[i]) / t;
    const sum = pdi + mdi;
    dx[i] = sum === 0 || Number.isNaN(sum) ? NaN : (100 * Math.abs(pdi - mdi)) / sum;
  }

  const smoothed = ewm(dx, alpha);
  const out = new Float64Array(n);
  for (let i = 0; i < n; i += 1) out[i] = Number.isNaN(smoothed[i]) ? 0 : smoothed[i];
  return out;
}

function pivot(values, left, right, isBetter) {
  const n = values.length;
  const picked = new Float64Array(n).fill(NaN);
  for (let i = 0; i < n; i += 1) {
    const v = values[i];
    if (Number.isNaN(v)) continue;
    let ok = true;
    for (let k = 1; k <= left && ok; k += 1) {
      const j = i - k;
      ok = j >= 0 && isBetter(v, values[j]);
    }
    for (let k = 1; k <= right && ok; k += 1) {
      const j = i + k;
      ok = j < n && isBetter(v, values[j]);
    }
    if (ok) picked[i] = v;
  }
  // Baru tersedia `right` bar setelah pivot terbentuk — ini yang mencegah lookahead.
  return ffill(shift(picked, right));
}

/** Harga swing high terkonfirmasi, di-forward-fill. */
export function swingHigh(df, left = 2, right = 2) {
  return pivot(df.high, left, right, (a, b) => a > b);
}

/** Harga swing low terkonfirmasi, di-forward-fill. */
export function swingLow(df, left = 2, right = 2) {
  return pivot(df.low, left, right, (a, b) => a < b);
}

/** Proporsi body terhadap total range candle (0..1). */
export function bodyRatio(df) {
  const n = df.high.length;
  const out = new Float64Array(n);
  for (let i = 0; i < n; i += 1) {
    const rng = df.high[i] - df.low[i];
    out[i] = rng === 0 || Number.isNaN(rng) ? 0 : Math.abs(df.close[i] - df.open[i]) / rng;
  }
  return out;
}

export function isBullishEngulfing(df) {
  const { open, close } = df;
  const prevOpen = shift(open, 1);
  const prevClose = shift(close, 1);
  return and(
    lt(prevClose, prevOpen),
    gt(close, open),
    gte(close, prevOpen),
    lte(open, prevClose),
  );
}

export function isBearishEngulfing(df) {
  const { open, close } = df;
  const prevOpen = shift(open, 1);
  const prevClose = shift(close, 1);
  return and(
    gt(prevClose, prevOpen),
    lt(close, open),
    lte(close, prevOpen),
    gte(open, prevClose),
  );
}

/** Lower wick minimal `wickMult` kali body, dan close di paruh atas candle. */
export function isBullishPin(df, wickMult = 2.0) {
  const n = df.high.length;
  const out = boolArray(n);
  for (let i = 0; i < n; i += 1) {
    const body = Math.abs(df.close[i] - df.open[i]);
    const lower = Math.min(df.open[i], df.close[i]) - df.low[i];
    const rng = df.high[i] - df.low[i];
    if (rng === 0 || Number.isNaN(rng)) continue; // rng 0 → NaN → perbandingan false
    out[i] = lower >= wickMult * body && (df.close[i] - df.low[i]) / rng > 0.5 ? 1 : 0;
  }
  return out;
}

export function isBearishPin(df, wickMult = 2.0) {
  const n = df.high.length;
  const out = boolArray(n);
  for (let i = 0; i < n; i += 1) {
    const body = Math.abs(df.close[i] - df.open[i]);
    const upper = df.high[i] - Math.max(df.open[i], df.close[i]);
    const rng = df.high[i] - df.low[i];
    if (rng === 0 || Number.isNaN(rng)) continue;
    out[i] = upper >= wickMult * body && (df.high[i] - df.close[i]) / rng > 0.5 ? 1 : 0;
  }
  return out;
}

/** Bias timeframe lebih tinggi (+1 / −1 / 0), di-resample lalu dipetakan balik ke M15.
 *
 * Bias sebuah periode HTF hanya berlaku setelah periode itu **tutup**, jadi tidak
 * ada informasi masa depan yang bocor ke bar M15. Padanan Python-nya
 * `resample(rule, label="left", closed="left").agg(…).dropna()` lalu `shift(1)`
 * dan `reindex(..., method="ffill")`.
 */
export function htfBias(df, periodMs, emaPeriod = 50) {
  const n = df.ts.length;
  // Bin di-anchor ke tengah malam UTC — sama seperti origin="start_day" pandas,
  // karena epoch juga jatuh tepat di tengah malam UTC.
  const binOf = new Int32Array(n);
  const binStarts = [];
  const closes = [];
  let currentKey = null;
  for (let i = 0; i < n; i += 1) {
    const key = Math.floor(df.ts[i] / periodMs);
    if (key !== currentKey) {
      currentKey = key;
      binStarts.push(key);
      closes.push(df.close[i]);
    } else {
      closes[closes.length - 1] = df.close[i];
    }
    // Bin kosong tidak pernah terbentuk (dropna di sisi Python), jadi indeksnya
    // rapat dan `shift(1)` berarti "bin berisi sebelumnya".
    binOf[i] = binStarts.length - 1;
  }

  const closeArr = Float64Array.from(closes);
  const emaArr = ema(closeArr, emaPeriod);
  const bias = new Int8Array(closeArr.length);
  for (let i = 0; i < closeArr.length; i += 1) {
    if (closeArr[i] > emaArr[i]) bias[i] = 1;
    else if (closeArr[i] < emaArr[i]) bias[i] = -1;
  }

  const out = new Int8Array(n);
  for (let i = 0; i < n; i += 1) {
    const b = binOf[i] - 1; // shift(1): pakai bias periode sebelumnya
    out[i] = b >= 0 ? bias[b] : 0;
  }
  return out;
}

export const HOUR_MS = 3600 * 1000;
