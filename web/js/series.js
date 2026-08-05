/* Operasi deret yang meniru pandas — ini fondasi seluruh port.
 *
 * Setiap fungsi di sini punya padanan pandas yang persis, termasuk cara
 * memperlakukan NaN. Kalau ada yang diubah di sini, indikator dan strategi
 * akan menyimpang dari engine Python tanpa suara. Uji paritas
 * (tests/parity.mjs) ada untuk menangkap itu.
 */

export const NA = NaN;

export function isNA(v) {
  return Number.isNaN(v);
}

export function filled(n, value) {
  const out = new Float64Array(n);
  out.fill(value);
  return out;
}

export function boolArray(n, value = false) {
  return new Uint8Array(n).fill(value ? 1 : 0);
}

/** Exponentially weighted mean, padanan `Series.ewm(alpha=…, adjust=False).mean()`.
 *
 * Aturan NaN-nya ikut pandas (`ignore_na=False`): nilai NaN tidak menghasilkan
 * update, tapi jeda yang ditimbulkannya tetap dihitung sebagai peluruhan. Nilai
 * valid pertama menjadi benih, dan sebelum itu keluarannya NaN.
 */
export function ewm(x, alpha) {
  const n = x.length;
  const out = new Float64Array(n);
  let y = NaN;
  let gap = 0;
  for (let i = 0; i < n; i += 1) {
    const v = x[i];
    if (Number.isNaN(v)) {
      out[i] = y;
      gap += 1;
      continue;
    }
    if (Number.isNaN(y)) {
      y = v;
    } else {
      const w = (1 - alpha) ** (gap + 1);
      y = w * y + (1 - w) * v;
    }
    gap = 0;
    out[i] = y;
  }
  return out;
}

/** `Series.ewm(span=period, adjust=False).mean()` */
export function ewmSpan(x, period) {
  return ewm(x, 2 / (period + 1));
}

/** Geser ke depan sebanyak `k` bar (k negatif menggeser ke belakang). */
export function shift(x, k) {
  const n = x.length;
  const out = new Float64Array(n).fill(NaN);
  for (let i = 0; i < n; i += 1) {
    const j = i - k;
    if (j >= 0 && j < n) out[i] = x[j];
  }
  return out;
}

/** `Series.diff()` */
export function diff(x) {
  const n = x.length;
  const out = new Float64Array(n).fill(NaN);
  for (let i = 1; i < n; i += 1) out[i] = x[i] - x[i - 1];
  return out;
}

/** Isi maju nilai terakhir yang bukan NaN. */
export function ffill(x) {
  const n = x.length;
  const out = new Float64Array(n);
  let last = NaN;
  for (let i = 0; i < n; i += 1) {
    if (!Number.isNaN(x[i])) last = x[i];
    out[i] = last;
  }
  return out;
}

function rollingReduce(x, window, minPeriods, better) {
  const n = x.length;
  const need = minPeriods == null ? window : minPeriods;
  const out = new Float64Array(n).fill(NaN);
  for (let i = 0; i < n; i += 1) {
    const start = Math.max(0, i - window + 1);
    let best = NaN;
    let count = 0;
    for (let j = start; j <= i; j += 1) {
      const v = x[j];
      if (Number.isNaN(v)) continue;
      count += 1;
      if (Number.isNaN(best) || better(v, best)) best = v;
    }
    // pandas menghitung min_periods terhadap jumlah observasi valid di jendela,
    // bukan terhadap lebar jendelanya.
    if (count >= need && i + 1 >= need) out[i] = best;
  }
  return out;
}

/** `Series.rolling(window, min_periods).max()` */
export function rollingMax(x, window, minPeriods = null) {
  return rollingReduce(x, window, minPeriods, (v, best) => v > best);
}

/** `Series.rolling(window, min_periods).min()` */
export function rollingMin(x, window, minPeriods = null) {
  return rollingReduce(x, window, minPeriods, (v, best) => v < best);
}

/** Maksimum elemen-per-elemen yang melewati NaN — padanan `pd.concat(…).max(axis=1)`. */
export function maxOf(...arrays) {
  const n = arrays[0].length;
  const out = new Float64Array(n).fill(NaN);
  for (let i = 0; i < n; i += 1) {
    let best = NaN;
    for (const arr of arrays) {
      const v = arr[i];
      if (Number.isNaN(v)) continue;
      if (Number.isNaN(best) || v > best) best = v;
    }
    out[i] = best;
  }
  return out;
}

/** Minimum elemen-per-elemen yang melewati NaN. */
export function minOf(...arrays) {
  const n = arrays[0].length;
  const out = new Float64Array(n).fill(NaN);
  for (let i = 0; i < n; i += 1) {
    let best = NaN;
    for (const arr of arrays) {
      const v = arr[i];
      if (Number.isNaN(v)) continue;
      if (Number.isNaN(best) || v < best) best = v;
    }
    out[i] = best;
  }
  return out;
}

/** Ubah deret angka jadi mask boolean lewat sebuah predikat. */
export function mask(x, predicate) {
  const n = x.length;
  const out = new Uint8Array(n);
  for (let i = 0; i < n; i += 1) out[i] = predicate(x[i], i) ? 1 : 0;
  return out;
}

export function and(...masks) {
  const n = masks[0].length;
  const out = new Uint8Array(n).fill(1);
  for (let i = 0; i < n; i += 1) {
    for (const m of masks) {
      if (!m[i]) {
        out[i] = 0;
        break;
      }
    }
  }
  return out;
}

export function or(...masks) {
  const n = masks[0].length;
  const out = new Uint8Array(n);
  for (let i = 0; i < n; i += 1) {
    for (const m of masks) {
      if (m[i]) {
        out[i] = 1;
        break;
      }
    }
  }
  return out;
}

export function notNaN(x) {
  return mask(x, (v) => !Number.isNaN(v));
}

/** Bandingkan dua deret; perbandingan yang melibatkan NaN selalu false (seperti numpy). */
export function cmp(a, b, op) {
  const n = a.length;
  const out = new Uint8Array(n);
  const bIsArray = typeof b !== 'number';
  for (let i = 0; i < n; i += 1) {
    const x = a[i];
    const y = bIsArray ? b[i] : b;
    if (Number.isNaN(x) || Number.isNaN(y)) continue;
    out[i] = op(x, y) ? 1 : 0;
  }
  return out;
}

export const gt = (a, b) => cmp(a, b, (x, y) => x > y);
export const gte = (a, b) => cmp(a, b, (x, y) => x >= y);
export const lt = (a, b) => cmp(a, b, (x, y) => x < y);
export const lte = (a, b) => cmp(a, b, (x, y) => x <= y);

/** `mask.rolling(window, min_periods=1).max().astype(bool)` — "pernah true dalam N bar". */
export function anyWithin(m, window) {
  const n = m.length;
  const out = new Uint8Array(n);
  let lastTrue = -1;
  for (let i = 0; i < n; i += 1) {
    if (m[i]) lastTrue = i;
    out[i] = lastTrue >= 0 && i - lastTrue < window ? 1 : 0;
  }
  return out;
}
