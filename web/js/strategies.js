/* Tiga strategi dari TRADING_PLAN §5 — port 1:1 dari xauusd/strategies/.
 *
 * Sebuah strategi mengubah bar M15 (sudah punya `session`, `hourWib`, `atr`)
 * menjadi tabel sinyal sepanjang data yang sama:
 *
 *   side      : +1 buy, −1 sell, 0 tidak ada sinyal
 *   sl, tp    : harga stop loss dan take profit
 *   invLevel  : level yang, kalau ditembus balik oleh close, membatalkan setup
 *
 * Sinyal di baris ke-i berarti "setup terkonfirmasi saat bar ke-i close"; engine
 * mengeksekusinya di open bar ke-(i+1). Jadi sl/tp hanya boleh memakai informasi
 * sampai bar ke-i.
 */

import {
  adx,
  bodyRatio,
  ema,
  htfBias,
  isBearishEngulfing,
  isBearishPin,
  isBullishEngulfing,
  isBullishPin,
  swingHigh,
  swingLow,
} from './indicators.js';
import { anyWithin, rollingMax, rollingMin, shift } from './series.js';

const HOUR_MS = 3600 * 1000;
export const MIN_RR = 1.5; // TRADING_PLAN §0: di bawah ini, skip.

function emptySignals(n) {
  return {
    side: new Int8Array(n),
    sl: new Float64Array(n).fill(NaN),
    tp: new Float64Array(n).fill(NaN),
    invLevel: new Float64Array(n).fill(NaN),
  };
}

function clearSignal(sig, i) {
  sig.side[i] = 0;
  sig.sl[i] = NaN;
  sig.tp[i] = NaN;
  sig.invLevel[i] = NaN;
}

/** Buang sinyal yang risk-reward-nya di bawah ambang.
 *
 * Perbandingan sengaja ditulis persis seperti versi pandas: apa pun yang
 * melibatkan NaN bernilai false, artinya sinyal dengan angka hilang **tidak**
 * dibuang di sini. Menuliskannya terbalik (`!(x >= y)`) akan membuang sinyal
 * yang di Python lolos.
 */
function enforceRr(sig, refPrice, minRr = MIN_RR) {
  for (let i = 0; i < refPrice.length; i += 1) {
    if (!sig.side[i]) continue;
    const risk = Math.abs(refPrice[i] - sig.sl[i]);
    const reward = Math.abs(sig.tp[i] - refPrice[i]);
    const ratio = risk === 0 ? NaN : reward / risk;
    if (risk <= 0 || ratio < minRr) clearSignal(sig, i);
  }
  return sig;
}

/** Per hari (kunci hari apa pun): nilai kumulatif dari bar-bar SEBELUM bar ini. */
function dailyRunning(values, dayKeys, reducer) {
  const n = values.length;
  const out = new Float64Array(n).fill(NaN);
  let currentDay = null;
  let acc = NaN;
  for (let i = 0; i < n; i += 1) {
    if (dayKeys[i] !== currentDay) {
      currentDay = dayKeys[i];
      acc = NaN;
    } else {
      out[i] = acc;
    }
    const v = values[i];
    if (!Number.isNaN(v)) acc = Number.isNaN(acc) ? v : reducer(acc, v);
  }
  return out;
}

/* ------------------------------------------------------- A. Breakout / Momentum */

export class Breakout {
  static key = 'breakout';

  constructor({
    rangeBars = 8,
    // Kalibrasi: tinggi range 8-bar biasanya 2,0–3,3 × ATR (median ~2,6). Ambang
    // 2,0 menangkap kuartil paling sempit — itulah definisi operasional
    // "konsolidasi". Ambang 1,2 praktis tidak pernah terpenuhi.
    maxRangeAtr = 2.0,
    minBodyRatio = 0.6,
    minExpansionAtr = 1.2,
    slBufferAtr = 0.3,
    rr = 1.5,
    requireBias = true,
  } = {}) {
    Object.assign(this, {
      name: 'breakout',
      rangeBars,
      maxRangeAtr,
      minBodyRatio,
      minExpansionAtr,
      slBufferAtr,
      rr,
      requireBias,
    });
  }

  generate(df) {
    const n = df.length;
    const sig = emptySignals(n);
    const atrV = df.atr;

    // Range konsolidasi dari N bar SEBELUM bar breakout.
    const rangeHigh = shift(rollingMax(df.high, this.rangeBars), 1);
    const rangeLow = shift(rollingMin(df.low, this.rangeBars), 1);

    const bias = this.requireBias ? htfBias(df, HOUR_MS) : new Int8Array(n);
    const body = bodyRatio(df);

    // Jangan breakout tepat ke level kunci: butuh ruang ≥ 1,5 ATR ke high/low harian.
    const dayHigh = dailyRunning(df.high, df.utcDay, Math.max);
    const dayLow = dailyRunning(df.low, df.utcDay, Math.min);

    for (let i = 0; i < n; i += 1) {
      const atrI = atrV[i];
      if (Number.isNaN(atrI)) continue;

      const rHigh = rangeHigh[i];
      const rLow = rangeLow[i];
      const tight = rHigh - rLow < this.maxRangeAtr * atrI;
      const expansion = df.high[i] - df.low[i] >= this.minExpansionAtr * atrI;
      const strongBody = body[i] >= this.minBodyRatio;

      // Jendela waktu: hanya sekitar London open dan NY open (§5.A).
      const h = df.hourWib[i];
      const inWindow = (h >= 14 && h < 15.5) || (h >= 19.5 && h < 21);

      if (!(tight && expansion && strongBody && inWindow)) continue;

      const close = df.close[i];
      const buffer = this.slBufferAtr * atrI;

      let long = close > rHigh;
      let short = close < rLow;
      if (this.requireBias) {
        long = long && bias[i] >= 0;
        short = short && bias[i] <= 0;
      }

      if (long) {
        const roomUp = Number.isNaN(dayHigh[i]) ? Infinity : dayHigh[i] - close;
        const beyond = Number.isNaN(dayHigh[i]) ? true : close > dayHigh[i];
        long = roomUp >= 1.5 * atrI || beyond;
      }
      if (short) {
        const roomDown = Number.isNaN(dayLow[i]) ? Infinity : close - dayLow[i];
        const beyond = Number.isNaN(dayLow[i]) ? true : close < dayLow[i];
        short = roomDown >= 1.5 * atrI || beyond;
      }

      if (long) {
        const sl = rLow - buffer;
        sig.side[i] = 1;
        sig.sl[i] = sl;
        sig.tp[i] = close + this.rr * (close - sl);
        // Balik masuk range = fakeout terkonfirmasi (§5.A "Invalidasi").
        sig.invLevel[i] = rHigh;
      } else if (short) {
        const sl = rHigh + buffer;
        sig.side[i] = -1;
        sig.sl[i] = sl;
        sig.tp[i] = close - this.rr * (sl - close);
        sig.invLevel[i] = rLow;
      }
    }

    return enforceRr(sig, df.close);
  }
}

/* ------------------------------------------- B. Trend Following via pullback EMA */

export class TrendPullback {
  static key = 'trend';

  constructor({
    fast = 20,
    slow = 50,
    minAdx = 20,
    slBufferAtr = 0.3,
    minRr = 1.5,
    sessions = ['london', 'ny'],
  } = {}) {
    Object.assign(this, { name: 'trend', fast, slow, minAdx, slBufferAtr, minRr, sessions });
    this.emaSlow = null;
  }

  generate(df) {
    const n = df.length;
    const sig = emptySignals(n);
    const atrV = df.atr;

    const emaFast = ema(df.close, this.fast);
    const emaSlow = ema(df.close, this.slow);
    this.emaSlow = emaSlow;

    const biasH4 = htfBias(df, 4 * HOUR_MS);
    const biasH1 = htfBias(df, HOUR_MS);
    const adxV = adx(df, 14);

    const bullPin = isBullishPin(df);
    const bearPin = isBearishPin(df);
    const bullEng = isBullishEngulfing(df);
    const bearEng = isBearishEngulfing(df);

    const prevLow = swingLow(df);
    const prevHigh = swingHigh(df);

    const sessionSet = new Set(this.sessions);

    for (let i = 0; i < n; i += 1) {
      const atrI = atrV[i];
      if (Number.isNaN(atrI)) continue;
      if (!(adxV[i] >= this.minAdx)) continue;
      if (!sessionSet.has(df.session[i])) continue;

      const zoneHi = Math.max(emaFast[i], emaSlow[i]);
      const zoneLo = Math.min(emaFast[i], emaSlow[i]);
      const close = df.close[i];

      // "Menyentuh zona" = wick masuk ke pita EMA, tapi close belum menembusnya.
      const touchedLong = df.low[i] <= zoneHi && close > zoneLo;
      const touchedShort = df.high[i] >= zoneLo && close < zoneHi;

      const longOk =
        biasH4[i] === 1 &&
        biasH1[i] === 1 &&
        emaFast[i] > emaSlow[i] &&
        touchedLong &&
        (bullPin[i] || bullEng[i]) &&
        df.low[i] > prevLow[i]; // struktur belum rusak

      const shortOk =
        biasH4[i] === -1 &&
        biasH1[i] === -1 &&
        emaFast[i] < emaSlow[i] &&
        touchedShort &&
        (bearPin[i] || bearEng[i]) &&
        df.high[i] < prevHigh[i];

      const buffer = this.slBufferAtr * atrI;

      if (longOk) {
        const sl = Math.min(
          Number.isNaN(prevLow[i]) ? Infinity : prevLow[i],
          df.low[i],
        ) - buffer;
        // TP: swing berlawanan terakhir, atau minimum RR — ambil yang lebih jauh.
        const rrTp = close + this.minRr * (close - sl);
        sig.side[i] = 1;
        sig.sl[i] = sl;
        sig.tp[i] = Number.isNaN(prevHigh[i]) ? rrTp : Math.max(prevHigh[i], rrTp);
      } else if (shortOk) {
        const sl = Math.max(
          Number.isNaN(prevHigh[i]) ? -Infinity : prevHigh[i],
          df.high[i],
        ) + buffer;
        const rrTp = close - this.minRr * (sl - close);
        sig.side[i] = -1;
        sig.sl[i] = sl;
        sig.tp[i] = Number.isNaN(prevLow[i]) ? rrTp : Math.min(prevLow[i], rrTp);
      }
    }

    return enforceRr(sig, df.close, this.minRr);
  }

  /** Close M15 menembus EMA lambat = tren yang jadi alasan masuk sudah hilang. */
  invalidate(df, i, side) {
    if (!this.emaSlow) return false;
    const level = this.emaSlow[i];
    if (Number.isNaN(level)) return false;
    return side === 1 ? df.close[i] < level : df.close[i] > level;
  }
}

/* ------------------------------------------------- C. Smart Money / Liquidity Sweep */

export class SmartMoney {
  static key = 'smc';

  constructor({
    // MSS jarang muncul di bar yang sama dengan sweep; beri ruang ~1,5 jam.
    sweepLookback = 6,
    slBufferAtr = 0.3,
    minRr = 1.5,
    targetLookback = 20,
    requireFvg = true,
  } = {}) {
    Object.assign(this, {
      name: 'smc',
      sweepLookback,
      slBufferAtr,
      minRr,
      targetLookback,
      requireFvg,
    });
  }

  /** Level likuiditas yang berlaku di tiap bar: Asia high/low hari ini dan
   *  high/low hari sebelumnya (kunci hari memakai tanggal WIB, ikut Python). */
  liquidityPools(df) {
    const n = df.length;
    const asiaHigh = new Float64Array(n).fill(NaN);
    const asiaLow = new Float64Array(n).fill(NaN);

    let day = null;
    let runHigh = NaN;
    let runLow = NaN;
    for (let i = 0; i < n; i += 1) {
      if (df.wibDay[i] !== day) {
        day = df.wibDay[i];
        runHigh = NaN;
        runLow = NaN;
      }
      if (df.session[i] === 'asia') {
        runHigh = Number.isNaN(runHigh) ? df.high[i] : Math.max(runHigh, df.high[i]);
        runLow = Number.isNaN(runLow) ? df.low[i] : Math.min(runLow, df.low[i]);
      }
      // cummax lalu ffill di dalam hari: setelah Asia tutup nilainya bertahan.
      asiaHigh[i] = runHigh;
      asiaLow[i] = runLow;
    }

    // High/low hari sebelumnya — "sebelumnya" berarti hari berisi data sebelumnya,
    // jadi akhir pekan otomatis terlewati (padanan `daily.shift(1)`).
    const dayHigh = new Map();
    const dayLow = new Map();
    const dayOrder = [];
    for (let i = 0; i < n; i += 1) {
      const d = df.wibDay[i];
      if (!dayHigh.has(d)) {
        dayHigh.set(d, df.high[i]);
        dayLow.set(d, df.low[i]);
        dayOrder.push(d);
      } else {
        dayHigh.set(d, Math.max(dayHigh.get(d), df.high[i]));
        dayLow.set(d, Math.min(dayLow.get(d), df.low[i]));
      }
    }
    const prevOf = new Map();
    for (let k = 1; k < dayOrder.length; k += 1) prevOf.set(dayOrder[k], dayOrder[k - 1]);

    const poolHigh = new Float64Array(n).fill(NaN);
    const poolLow = new Float64Array(n).fill(NaN);
    for (let i = 0; i < n; i += 1) {
      const prev = prevOf.get(df.wibDay[i]);
      const ph = prev === undefined ? NaN : dayHigh.get(prev);
      const pl = prev === undefined ? NaN : dayLow.get(prev);
      poolHigh[i] = maxTwo(asiaHigh[i], ph);
      poolLow[i] = minTwo(asiaLow[i], pl);
    }
    return { poolHigh, poolLow };
  }

  generate(df) {
    const n = df.length;
    const sig = emptySignals(n);
    const atrV = df.atr;
    const win = this.sweepLookback;

    const { poolHigh, poolLow } = this.liquidityPools(df);

    // 2. Sweep: wick menembus pool, close kembali ke sisi asal.
    const sweptLow = new Uint8Array(n);
    const sweptHigh = new Uint8Array(n);
    for (let i = 0; i < n; i += 1) {
      sweptLow[i] = df.low[i] < poolLow[i] && df.close[i] > poolLow[i] ? 1 : 0;
      sweptHigh[i] = df.high[i] > poolHigh[i] && df.close[i] < poolHigh[i] ? 1 : 0;
    }
    const recentSweepLow = anyWithin(sweptLow, win);
    const recentSweepHigh = anyWithin(sweptHigh, win);

    // 3. MSS: close menembus swing point terkonfirmasi terakhir.
    const sh = swingHigh(df);
    const slw = swingLow(df);
    const prevClose = shift(df.close, 1);
    const prevSh = shift(sh, 1);
    const prevSlw = shift(slw, 1);

    // 4. FVG: celah tiga-bar yang belum terisi pada leg MSS.
    let hasFvgUp;
    let hasFvgDown;
    if (this.requireFvg) {
      const fvgUp = new Uint8Array(n);
      const fvgDown = new Uint8Array(n);
      for (let i = 2; i < n; i += 1) {
        fvgUp[i] = df.low[i] > df.high[i - 2] ? 1 : 0;
        fvgDown[i] = df.high[i] < df.low[i - 2] ? 1 : 0;
      }
      hasFvgUp = anyWithin(fvgUp, win);
      hasFvgDown = anyWithin(fvgDown, win);
    } else {
      hasFvgUp = new Uint8Array(n).fill(1);
      hasFvgDown = new Uint8Array(n).fill(1);
    }

    // SL di luar ujung wick sweep.
    const sweepLowPrice = rollingMin(df.low, win, 1);
    const sweepHighPrice = rollingMax(df.high, win, 1);

    // TP di pool likuiditas berlawanan berikutnya.
    const swingTargetUp = shift(rollingMax(df.high, this.targetLookback), 1);
    const swingTargetDown = shift(rollingMin(df.low, this.targetLookback), 1);

    for (let i = 0; i < n; i += 1) {
      const atrI = atrV[i];
      if (Number.isNaN(atrI)) continue;

      const close = df.close[i];
      const mssUp = close > sh[i] && prevClose[i] <= prevSh[i];
      const mssDown = close < slw[i] && prevClose[i] >= prevSlw[i];

      const longOk = recentSweepLow[i] && mssUp && hasFvgUp[i];
      const shortOk = recentSweepHigh[i] && mssDown && hasFvgDown[i];
      if (!longOk && !shortOk) continue;

      const buffer = this.slBufferAtr * atrI;

      if (longOk) {
        const tp = maxTwo(swingTargetUp[i], poolHigh[i]);
        sig.side[i] = 1;
        sig.sl[i] = sweepLowPrice[i] - buffer;
        sig.tp[i] = tp;
        sig.invLevel[i] = sweepLowPrice[i];
      } else {
        const tp = minTwo(swingTargetDown[i], poolLow[i]);
        sig.side[i] = -1;
        sig.sl[i] = sweepHighPrice[i] + buffer;
        sig.tp[i] = tp;
        sig.invLevel[i] = sweepHighPrice[i];
      }

      // Target yang lebih dekat dari entry (pool sudah terlewati) tidak valid.
      const tp = sig.tp[i];
      if ((sig.side[i] === 1 && tp <= close) || (sig.side[i] === -1 && tp >= close)) {
        clearSignal(sig, i);
      }
    }

    return enforceRr(sig, df.close, this.minRr);
  }
}

function maxTwo(a, b) {
  if (Number.isNaN(a)) return b;
  if (Number.isNaN(b)) return a;
  return Math.max(a, b);
}

function minTwo(a, b) {
  if (Number.isNaN(a)) return b;
  if (Number.isNaN(b)) return a;
  return Math.min(a, b);
}

export const REGISTRY = {
  breakout: Breakout,
  trend: TrendPullback,
  smc: SmartMoney,
};

export const STRATEGY_LABELS = {
  breakout: 'Breakout / Momentum',
  trend: 'Trend Following',
  smc: 'Smart Money / Liquidity',
};
