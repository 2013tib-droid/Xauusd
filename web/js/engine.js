/* Engine backtest bar-by-bar — port 1:1 dari xauusd/engine.py.
 *
 * Aturan eksekusi yang dipakai (sengaja konservatif — lebih baik hasil backtest
 * terlalu pesimis daripada terlalu optimis):
 *
 *   • Sinyal dihasilkan pada close sebuah bar, eksekusi pada open bar berikutnya.
 *   • Kalau dalam satu bar harga menyentuh SL dan TP sekaligus, SL yang dianggap
 *     kena. Data M15 tidak memberi tahu mana yang lebih dulu.
 *   • Spread dibebankan penuh satu kali saat entry.
 *   • Komisi dibebankan per lot round-turn.
 *   • Hanya satu posisi terbuka pada satu waktu (TRADING_PLAN §0).
 */

import { addSession } from './data.js';
import { atr } from './indicators.js';

/** XAUUSD: 1,00 lot = 100 oz, jadi pergerakan $1,00 = $100 per lot. */
export const CONTRACT_SIZE = 100.0;

const MINUTE_MS = 60 * 1000;

/** Parameter akun dan manajemen risiko. Default-nya akun kecil (< $1.000),
 *  risiko 1% — lihat TRADING_PLAN §3.2 soal kenapa akun segitu sering tidak
 *  bisa menegakkan risiko 1% yang sebenarnya. */
export const DEFAULT_CONFIG = {
  initialEquity: 1000.0,
  riskPct: 1.0,
  spread: 0.25, // dalam dollar; gold ritel biasanya $0.15–0.40
  commissionPerLot: 7.0, // round-turn per 1,00 lot
  minLot: 0.01,
  lotStep: 0.01,
  maxLot: 100.0,

  // Saat lot hasil perhitungan < minLot:
  //   "skip" — trade dilewati (jujur: setup ini memang tak terjangkau modalmu)
  //   "min"  — tetap masuk dengan minLot, risiko riil jadi > riskPct
  undersizedPolicy: 'skip',

  // Manajemen posisi (TRADING_PLAN §3.4)
  partialAtR: 1.0,
  partialFraction: 0.5,
  breakevenAtR: 1.0,
  trailAtR: 2.0,
  trailAtrMult: 2.0,
  timeStopBars: 12, // 12 bar M15 = 3 jam

  // Rem risiko (TRADING_PLAN §3.3)
  dailyLossLimitR: 2.0,
  weeklyLossLimitR: 4.0,
  drawdownDeriskPct: 10.0,
  drawdownDeriskFactor: 0.5,

  sessions: ['asia', 'london', 'ny'],
  // { stamp: milidetik UTC, before: menit, after: menit }
  newsBlackout: [],
};

function roundLot(lot, step) {
  return Math.floor(lot / step + 1e-9) * step;
}

function blackoutMask(ts, windows) {
  const out = new Uint8Array(ts.length);
  if (!windows || !windows.length) return out;
  for (let i = 0; i < ts.length; i += 1) {
    for (const w of windows) {
      if (ts[i] >= w.stamp - w.before * MINUTE_MS && ts[i] <= w.stamp + w.after * MINUTE_MS) {
        out[i] = 1;
        break;
      }
    }
  }
  return out;
}

/** Jalankan satu strategi terhadap satu set data M15. */
export function runBacktest(rawDf, strategy, userConfig = {}) {
  const cfg = { ...DEFAULT_CONFIG, ...userConfig };
  const df = addSession(rawDf);
  df.atr = atr(df, 14);

  const sig = strategy.generate(df);
  const n = df.length;

  const { high: highs, low: lows, open: opens, close: closes, ts } = df;
  const atrVals = df.atr;
  const sessions = df.session;
  const blackout = blackoutMask(ts, cfg.newsBlackout);
  const sessionSet = new Set(cfg.sessions);

  const trades = [];
  const equityPoints = new Float64Array(n).fill(cfg.initialEquity);
  let skippedUndersized = 0;
  let partialBlocked = 0;

  const dailyR = new Map();
  const weeklyR = new Map();

  let equity = cfg.initialEquity;
  let peakEquity = equity;
  let pos = null;

  // Menutup sebagian/seluruh posisi: kembalikan P/L bersih setelah komisi.
  function closePart(price, lot) {
    let pnl = pos.side * (price - pos.entry) * lot * CONTRACT_SIZE;
    pnl -= cfg.commissionPerLot * lot;
    pos.realisedPnl += pnl;
    pos.openLot = Number((pos.openLot - lot).toFixed(8));
    return pnl;
  }

  function record(exitTs, exitPrice, bars, reason, equityAfter) {
    const r = pos.riskUsd ? pos.realisedPnl / pos.riskUsd : 0;
    trades.push({
      entryTime: pos.entryTime,
      exitTime: exitTs,
      side: pos.side,
      strategy: pos.strategy,
      session: pos.session,
      entry: pos.entry,
      exit: exitPrice,
      sl: pos.sl,
      tp: pos.tp,
      riskDist: pos.riskDist,
      lot: pos.lot,
      riskUsd: pos.riskUsd,
      pnl: pos.realisedPnl,
      r,
      barsHeld: bars,
      exitReason: reason,
      equityAfter,
    });
  }

  function size(effectiveEquity, riskDist) {
    const riskUsd = (effectiveEquity * cfg.riskPct) / 100;
    if (riskDist <= 0) return [0, 0];

    let lot = roundLot(riskUsd / (riskDist * CONTRACT_SIZE), cfg.lotStep);
    if (lot < cfg.minLot) {
      if (cfg.undersizedPolicy === 'min') lot = cfg.minLot;
      else return [0, 0];
    }
    lot = Math.min(lot, cfg.maxLot);
    return [lot, lot * riskDist * CONTRACT_SIZE];
  }

  for (let i = 1; i < n; i += 1) {
    const barHigh = highs[i];
    const barLow = lows[i];
    const barClose = closes[i];

    /* ------------------------------------------------------- kelola posisi */
    if (pos !== null) {
      const barsHeld = i - pos.entryIndex;
      const rDist = pos.riskDist;
      let exited = false;
      let exitPrice = NaN;
      let reason = '';

      // 1. Stop loss lebih dulu — asumsi konservatif.
      const hitSl = pos.side === 1 ? barLow <= pos.sl : barHigh >= pos.sl;
      if (hitSl) {
        // Bedakan stop asli dari stop yang sudah digeser ke BE/trailing: keduanya
        // "kena SL", tapi artinya sangat berbeda saat direview.
        reason = !(pos.beDone || pos.trailing) ? 'sl' : pos.trailing ? 'trail_stop' : 'be_stop';
        equity += closePart(pos.sl, pos.openLot);
        exited = true;
        exitPrice = pos.sl;
      }

      // 2. Take profit.
      if (!exited) {
        const hitTp = pos.side === 1 ? barHigh >= pos.tp : barLow <= pos.tp;
        if (hitTp) {
          equity += closePart(pos.tp, pos.openLot);
          exited = true;
          exitPrice = pos.tp;
          reason = 'tp';
        }
      }

      // 3. Partial + break even di +1R.
      if (!exited && cfg.partialAtR && !pos.partialDone) {
        const level = pos.entry + pos.side * cfg.partialAtR * rDist;
        const reached = pos.side === 1 ? barHigh >= level : barLow <= level;
        if (reached) {
          const part = roundLot(pos.openLot * cfg.partialFraction, cfg.lotStep);
          if (part >= cfg.minLot && part < pos.openLot) {
            equity += closePart(level, part);
          } else {
            // Posisi sudah sekecil minLot — separuhnya tidak ada.
            partialBlocked += 1;
          }
          pos.partialDone = true;
          if (cfg.breakevenAtR !== null && cfg.breakevenAtR !== undefined) {
            pos.sl = pos.entry + pos.side * cfg.spread;
            pos.beDone = true;
          }
        }
      }

      // 4. Trailing stop mulai +2R.
      if (!exited && cfg.trailAtR) {
        const level = pos.entry + pos.side * cfg.trailAtR * rDist;
        const reached = pos.side === 1 ? barHigh >= level : barLow <= level;
        if (reached) pos.trailing = true;
        if (pos.trailing && !Number.isNaN(atrVals[i])) {
          const gap = cfg.trailAtrMult * atrVals[i];
          const trail = pos.side === 1 ? barClose - gap : barClose + gap;
          pos.sl = pos.side === 1 ? Math.max(pos.sl, trail) : Math.min(pos.sl, trail);
        }
      }

      // 5a. Invalidasi level statis: harga kembali menembus level yang jadi dasar
      //     setup (mis. balik masuk range pada breakout).
      if (!exited && !Number.isNaN(pos.invLevel)) {
        const broken = pos.side === 1 ? barClose < pos.invLevel : barClose > pos.invLevel;
        if (broken) {
          equity += closePart(barClose, pos.openLot);
          exited = true;
          exitPrice = barClose;
          reason = 'invalidated';
        }
      }

      // 5b. Invalidasi dinamis yang didefinisikan strategi.
      if (!exited && typeof strategy.invalidate === 'function') {
        if (strategy.invalidate(df, i, pos.side)) {
          equity += closePart(barClose, pos.openLot);
          exited = true;
          exitPrice = barClose;
          reason = 'invalidated';
        }
      }

      // 6. Time stop.
      if (!exited && cfg.timeStopBars && barsHeld >= cfg.timeStopBars) {
        equity += closePart(barClose, pos.openLot);
        exited = true;
        exitPrice = barClose;
        reason = 'time_stop';
      }

      if (exited) {
        record(ts[i], exitPrice, barsHeld, reason, equity);
        const tradeR = pos.riskUsd ? pos.realisedPnl / pos.riskUsd : 0;
        const day = df.wibDay[i];
        const week = df.weekKey[i];
        dailyR.set(day, (dailyR.get(day) ?? 0) + tradeR);
        weeklyR.set(week, (weeklyR.get(week) ?? 0) + tradeR);
        peakEquity = Math.max(peakEquity, equity);
        pos = null;
      }
    }

    equityPoints[i] = equity;

    /* --------------------------------------------------------- entry baru */
    if (pos !== null || equity <= 0) continue;

    const side = sig.side[i - 1];
    if (side === 0 || Number.isNaN(sig.sl[i - 1])) continue;
    if (!sessionSet.has(sessions[i]) || blackout[i]) continue;

    const day = df.wibDay[i];
    const week = df.weekKey[i];
    if (cfg.dailyLossLimitR && (dailyR.get(day) ?? 0) <= -cfg.dailyLossLimitR) continue;
    if (cfg.weeklyLossLimitR && (weeklyR.get(week) ?? 0) <= -cfg.weeklyLossLimitR) continue;

    const entry = opens[i] + (side === 1 ? cfg.spread : 0);
    const sl = sig.sl[i - 1];
    const tp = sig.tp[i - 1];

    // Sinyal yang harganya sudah lewat saat bar dibuka: batal.
    if ((side === 1 && (entry <= sl || entry >= tp)) || (side === -1 && (entry >= sl || entry <= tp))) {
      continue;
    }

    const riskDist = Math.abs(entry - sl);
    if (riskDist <= 0) continue;

    // De-risk saat drawdown dalam (TRADING_PLAN §3.3).
    let effectiveEquity = equity;
    if (peakEquity > 0 && equity < peakEquity * (1 - cfg.drawdownDeriskPct / 100)) {
      effectiveEquity = equity * cfg.drawdownDeriskFactor;
    }

    const [lot, riskUsd] = size(effectiveEquity, riskDist);
    if (lot <= 0) {
      skippedUndersized += 1;
      continue;
    }

    pos = {
      side,
      entry,
      sl,
      tp,
      riskDist,
      lot,
      openLot: lot,
      riskUsd,
      entryTime: ts[i],
      entryIndex: i,
      strategy: strategy.name ?? 'unknown',
      session: sessions[i],
      invLevel: sig.invLevel[i - 1],
      realisedPnl: 0,
      partialDone: false,
      beDone: false,
      trailing: false,
    };
  }

  // Posisi yang masih terbuka di akhir data ditutup di harga terakhir.
  if (pos !== null) {
    equity += closePart(closes[n - 1], pos.openLot);
    record(ts[n - 1], closes[n - 1], n - 1 - pos.entryIndex, 'end_of_data', equity);
    equityPoints[n - 1] = equity;
  }

  return {
    trades,
    equity: equityPoints,
    ts,
    skippedUndersized,
    partialBlocked,
    config: cfg,
  };
}
