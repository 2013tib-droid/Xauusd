/* Pemuatan dan penyiapan data XAUUSD M15 di sisi browser.
 *
 * Port dari xauusd/data.py. Berkas CSV dibaca lokal oleh browser dan tidak
 * pernah dikirim ke mana pun — tidak ada server di aplikasi ini.
 */

const DAY_MS = 86400 * 1000;
const HOUR_MS = 3600 * 1000;

/** WIB = UTC+7 sepanjang tahun (tidak ada DST), jadi offsetnya boleh dipatok. */
export const WIB_OFFSET_MS = 7 * HOUR_MS;

/** Batas sesi dalam jam WIB, sesuai docs/TRADING_PLAN.md §2. */
export const SESSIONS = {
  asia: [7, 12],
  london: [14, 18],
  ny: [19.5, 23],
};

const COLUMN_ALIASES = {
  open: ['open', 'o', '<open>'],
  high: ['high', 'h', '<high>'],
  low: ['low', 'l', '<low>'],
  close: ['close', 'c', '<close>', 'adj close'],
  volume: ['volume', 'vol', 'tickvol', '<tickvol>', '<vol>'],
};

const DATE_KEYS = ['date', '<date>', 'tanggal'];
const TIME_KEYS = ['time', '<time>', 'waktu'];
const DATETIME_KEYS = ['datetime', 'timestamp', 'gmt time', 'local time'];

/** Nomor hari sejak epoch untuk zona WIB — dipakai sebagai kunci harian. */
export function wibDayIndex(ts) {
  return Math.floor((ts + WIB_OFFSET_MS) / DAY_MS);
}

/** Nomor hari sejak epoch dalam UTC (dipakai strategi breakout, ikut Python). */
export function utcDayIndex(ts) {
  return Math.floor(ts / DAY_MS);
}

/** Jam WIB sebagai pecahan (mis. 19.5 untuk 19:30). */
export function wibHour(ts) {
  const local = ts + WIB_OFFSET_MS;
  const within = ((local % DAY_MS) + DAY_MS) % DAY_MS;
  return within / HOUR_MS;
}

/** Hari dalam minggu untuk sebuah nomor hari epoch, Senin = 0. */
export function dayOfWeek(dayIndex) {
  return (((dayIndex + 3) % 7) + 7) % 7;
}

/** Kunci minggu ISO (tahun × 100 + minggu) dari nomor hari epoch. */
export function isoWeekKey(dayIndex) {
  const thursday = dayIndex - dayOfWeek(dayIndex) + 3;
  const d = new Date(thursday * DAY_MS);
  const year = d.getUTCFullYear();
  const jan1 = Math.floor(Date.UTC(year, 0, 1) / DAY_MS);
  return year * 100 + Math.floor((thursday - jan1) / 7) + 1;
}

function sniffDelimiter(headerLine) {
  const candidates = [',', ';', '\t', '|'];
  let best = ',';
  let bestCount = -1;
  for (const c of candidates) {
    const count = headerLine.split(c).length - 1;
    if (count > bestCount) {
      best = c;
      bestCount = count;
    }
  }
  return best;
}

function splitLine(line, delim) {
  // Cukup tangani tanda kutip sederhana; export MT5 tidak memakai koma di dalam sel.
  if (!line.includes('"')) return line.split(delim);
  const out = [];
  let cur = '';
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') quoted = !quoted;
    else if (ch === delim && !quoted) {
      out.push(cur);
      cur = '';
    } else cur += ch;
  }
  out.push(cur);
  return out;
}

/** Parse stempel waktu tanpa zona menjadi milidetik "seolah UTC". */
export function parseNaiveStamp(raw) {
  const text = String(raw).trim().replace(/\./g, '-');
  const m = text.match(
    /^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?/,
  );
  if (m) {
    return Date.UTC(
      Number(m[1]),
      Number(m[2]) - 1,
      Number(m[3]),
      Number(m[4] ?? 0),
      Number(m[5] ?? 0),
      Number(m[6] ?? 0),
    );
  }
  // Format hari-dulu (mis. 04-08-2026 15:30), yang dipakai sebagian broker.
  const dmy = text.match(/^(\d{1,2})-(\d{1,2})-(\d{4})(?:[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?/);
  if (dmy) {
    return Date.UTC(
      Number(dmy[3]),
      Number(dmy[2]) - 1,
      Number(dmy[1]),
      Number(dmy[4] ?? 0),
      Number(dmy[5] ?? 0),
      Number(dmy[6] ?? 0),
    );
  }
  const fallback = Date.parse(text.endsWith('Z') ? text : `${text}Z`);
  return Number.isNaN(fallback) ? NaN : fallback;
}

function toNumber(raw) {
  if (raw == null) return NaN;
  const text = String(raw).trim();
  if (!text) return NaN;
  const v = Number(text);
  return Number.isNaN(v) ? NaN : v;
}

/** Muat CSV OHLC M15 menjadi bar ber-stempel UTC.
 *
 * @param {string} text isi berkas
 * @param {number} sourceOffsetHours offset zona waktu stempel di berkas
 *   (server MT5 umumnya UTC+2 atau UTC+3 — salah isi menggeser seluruh filter sesi)
 */
export function parseCsv(text, sourceOffsetHours = 0) {
  const lines = text.split(/\r?\n/).filter((l) => l.trim() !== '');
  if (lines.length < 2) throw new Error('Berkas kosong atau hanya berisi header.');

  const delim = sniffDelimiter(lines[0]);
  const header = splitLine(lines[0], delim).map((h) => h.trim().toLowerCase().replace(/^"|"$/g, ''));

  const colIndex = {};
  for (const [target, aliases] of Object.entries(COLUMN_ALIASES)) {
    const idx = header.findIndex((h) => h === target || aliases.includes(h));
    if (idx >= 0) colIndex[target] = idx;
  }

  const missing = ['open', 'high', 'low', 'close'].filter((c) => !(c in colIndex));
  if (missing.length) {
    throw new Error(
      `Kolom OHLC tidak lengkap, yang hilang: ${missing.join(', ')}. ` +
        `Kolom yang terbaca: ${header.join(', ')}`,
    );
  }

  const dateIdx = header.findIndex((h) => DATE_KEYS.includes(h));
  const timeIdx = header.findIndex((h) => TIME_KEYS.includes(h));
  const dtIdx = header.findIndex((h) => DATETIME_KEYS.includes(h));
  if (dateIdx < 0 && dtIdx < 0) {
    throw new Error(
      `Kolom waktu tidak ditemukan. Butuh salah satu dari: date, datetime, timestamp, ` +
        `atau pasangan date + time. Kolom yang terbaca: ${header.join(', ')}`,
    );
  }

  const rows = [];
  for (let i = 1; i < lines.length; i += 1) {
    const cells = splitLine(lines[i], delim);
    if (cells.length < 2) continue;

    let stamp;
    if (dateIdx >= 0 && timeIdx >= 0) stamp = `${cells[dateIdx]?.trim()} ${cells[timeIdx]?.trim()}`;
    else if (dateIdx >= 0) stamp = cells[dateIdx];
    else stamp = cells[dtIdx];

    const naive = parseNaiveStamp(stamp);
    if (Number.isNaN(naive)) continue;

    const o = toNumber(cells[colIndex.open]);
    const h = toNumber(cells[colIndex.high]);
    const l = toNumber(cells[colIndex.low]);
    const c = toNumber(cells[colIndex.close]);
    if ([o, h, l, c].some(Number.isNaN)) continue;

    rows.push({
      ts: naive - sourceOffsetHours * HOUR_MS,
      open: o,
      high: h,
      low: l,
      close: c,
      volume: 'volume' in colIndex ? toNumber(cells[colIndex.volume]) : NaN,
    });
  }

  if (!rows.length) throw new Error('Tidak ada baris valid setelah parsing.');

  rows.sort((a, b) => a.ts - b.ts);
  const deduped = [];
  for (const row of rows) {
    // `~index.duplicated(keep="first")`: stempel kembar, yang pertama menang.
    if (deduped.length && deduped[deduped.length - 1].ts === row.ts) continue;
    deduped.push(row);
  }

  return framesFromRows(deduped);
}

function framesFromRows(rows) {
  const n = rows.length;
  const df = {
    ts: new Float64Array(n),
    open: new Float64Array(n),
    high: new Float64Array(n),
    low: new Float64Array(n),
    close: new Float64Array(n),
    volume: new Float64Array(n),
    length: n,
  };
  for (let i = 0; i < n; i += 1) {
    df.ts[i] = rows[i].ts;
    df.open[i] = rows[i].open;
    df.high[i] = rows[i].high;
    df.low[i] = rows[i].low;
    df.close[i] = rows[i].close;
    df.volume[i] = rows[i].volume;
  }
  return df;
}

/** Tambah kolom `session` dan `hourWib`, plus kunci hari/minggu yang dipakai engine.
 *
 * Catatan yang mudah terlewat: penandaan akhir pekan memakai hari **UTC**, sama
 * seperti `df.index.dayofweek` di Python — bukan hari WIB.
 */
export function addSession(df) {
  const n = df.length;
  const hourWib = new Float64Array(n);
  const session = new Array(n);
  const wibDay = new Int32Array(n);
  const utcDay = new Int32Array(n);
  const weekKey = new Int32Array(n);

  for (let i = 0; i < n; i += 1) {
    const ts = df.ts[i];
    const h = wibHour(ts);
    hourWib[i] = h;
    wibDay[i] = wibDayIndex(ts);
    utcDay[i] = utcDayIndex(ts);
    weekKey[i] = isoWeekKey(wibDay[i]);

    let name = 'off';
    for (const [key, [start, end]] of Object.entries(SESSIONS)) {
      if (h >= start && h < end) name = key;
    }
    if (dayOfWeek(utcDay[i]) >= 5) name = 'off';
    session[i] = name;
  }

  return { ...df, hourWib, session, wibDay, utcDay, weekKey };
}

/** PRNG deterministik (mulberry32) supaya data sintetis bisa diulang persis. */
function mulberry32(seed) {
  let a = seed >>> 0;
  return function next() {
    a += 0x6d2b79f5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function gaussian(rand) {
  // Box–Muller
  let u = 0;
  let v = 0;
  while (u === 0) u = rand();
  while (v === 0) v = rand();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

/** Data M15 sintetis yang menyerupai gold.
 *
 * BUKAN pengganti data riil: hasil backtest-nya tidak punya nilai prediktif.
 * Gunanya hanya membuktikan engine, sizing, dan metrik berjalan. Angkanya tidak
 * identik dengan `data.synthetic()` versi Python karena generator acaknya beda —
 * karakternya yang ditiru, bukan nilainya.
 */
export function synthetic({ bars = 8000, seed = 7, startPrice = 4000, start = '2026-01-05T00:00:00Z' } = {}) {
  const rand = mulberry32(seed);
  const startMs = Date.parse(start);
  const rows = [];

  const vol = new Float64Array(bars);
  const ts = new Float64Array(bars);
  for (let i = 0; i < bars; i += 1) {
    ts[i] = startMs + i * 15 * 60 * 1000;
    const h = wibHour(ts[i]);
    let v = 0.35;
    if (h >= 7 && h < 12) v = 0.55;
    else if (h >= 14 && h < 18) v = 1.3;
    else if (h >= 19.5 && h < 23) v = 1.45;
    if (dayOfWeek(utcDayIndex(ts[i])) >= 5) v = 0.15;
    vol[i] = v;
  }

  // Rezim tren berganti tiap ~2 minggu, plus volatility clustering.
  const regime = new Float64Array(bars);
  for (let block = 0; block * 1300 < bars; block += 1) {
    const value = gaussian(rand) * 0.035;
    for (let i = block * 1300; i < Math.min(bars, (block + 1) * 1300); i += 1) regime[i] = value;
  }

  const cluster = new Float64Array(bars);
  const clusterAlpha = 2 / (40 + 1);
  let clusterState = NaN;
  for (let i = 0; i < bars; i += 1) {
    const raw = Math.abs(1 + gaussian(rand) * 0.35);
    clusterState = Number.isNaN(clusterState)
      ? raw
      : clusterState + clusterAlpha * (raw - clusterState);
    cluster[i] = clusterState;
  }

  let close = startPrice;
  for (let i = 0; i < bars; i += 1) {
    const open = close;
    close = open + regime[i] + gaussian(rand) * vol[i] * cluster[i];
    const upperWick = Math.abs(gaussian(rand) * vol[i] * cluster[i] * 0.7);
    const lowerWick = Math.abs(gaussian(rand) * vol[i] * cluster[i] * 0.7);
    rows.push({
      ts: ts[i],
      open,
      high: Math.max(open, close) + upperWick,
      low: Math.min(open, close) - lowerWick,
      close,
      volume: Math.floor(50 + rand() * 2950),
    });
  }

  return framesFromRows(rows);
}

export function formatUtc(ts) {
  return new Date(ts).toISOString().slice(0, 16).replace('T', ' ');
}
