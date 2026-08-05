/* Metrik evaluasi backtest — port 1:1 dari xauusd/metrics.py.
 *
 * Urutan pentingnya metrik mengikuti TRADING_PLAN §8: expectancy dan profit
 * factor lebih dulu, win rate belakangan. Win rate tinggi tanpa expectancy
 * positif tidak berarti apa-apa.
 */

/** Ambang kelulusan backtest, TRADING_PLAN §8. */
export const PASS_PROFIT_FACTOR = 1.3;
export const PASS_MAX_DD_PCT = 15.0;
export const PASS_EXPECTANCY_R = 0.15;
export const MIN_SAMPLE = 100; // di bawah ini, angka apa pun hanyalah kebisingan
export const IDEAL_SAMPLE = 200;

/** 4 bar M15 per jam × 24 jam × 252 hari perdagangan. */
export const BARS_PER_YEAR = 4 * 24 * 252;

function round(value, digits) {
  if (!Number.isFinite(value)) return value;
  const f = 10 ** digits;
  return Math.round((value + Number.EPSILON * Math.abs(value)) * f) / f;
}

/** Kembalikan { usd, pct } drawdown maksimum. */
export function maxDrawdown(equity) {
  if (!equity || !equity.length) return { usd: 0, pct: 0 };
  let peak = -Infinity;
  let worstUsd = 0;
  let worstPct = 0;
  let sawPct = false;
  for (let i = 0; i < equity.length; i += 1) {
    peak = Math.max(peak, equity[i]);
    const dd = equity[i] - peak;
    if (dd < worstUsd) worstUsd = dd;
    if (peak !== 0) {
      sawPct = true;
      const pct = (dd / peak) * 100;
      if (pct < worstPct) worstPct = pct;
    }
  }
  return { usd: -worstUsd, pct: sawPct ? -worstPct : 0 };
}

export function summarise(trades, equity, initialEquity) {
  if (!trades.length) {
    return {
      trades: 0,
      note: 'tidak ada trade — periksa filter sesi, ukuran lot minimum, atau parameter strategi',
    };
  }

  const rs = trades.map((t) => t.r);
  const pnls = trades.map((t) => t.pnl);
  const wins = rs.filter((v) => v > 0);
  const losses = rs.filter((v) => v <= 0);

  const grossWin = pnls.filter((v) => v > 0).reduce((a, b) => a + b, 0);
  const grossLoss = -pnls.filter((v) => v <= 0).reduce((a, b) => a + b, 0);
  const profitFactor = grossLoss > 0 ? grossWin / grossLoss : Infinity;

  const dd = maxDrawdown(equity);
  const finalEquity = equity && equity.length ? equity[equity.length - 1] : initialEquity;

  // Sharpe kasar dari return per bar, disetahunkan.
  const rets = [];
  for (let i = 1; i < equity.length; i += 1) {
    const prev = equity[i - 1];
    if (prev === 0) continue;
    rets.push(equity[i] / prev - 1);
  }
  let sharpe = 0;
  if (rets.length > 1) {
    const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
    // ddof=1, sama seperti Series.std() di pandas.
    const variance = rets.reduce((a, b) => a + (b - mean) ** 2, 0) / (rets.length - 1);
    const std = Math.sqrt(variance);
    if (std > 0) sharpe = (mean / std) * Math.sqrt(BARS_PER_YEAR);
  }

  // Rentetan kalah terpanjang.
  let streak = 0;
  let worstStreak = 0;
  for (const v of rs) {
    streak = v <= 0 ? streak + 1 : 0;
    worstStreak = Math.max(worstStreak, streak);
  }

  const mean = (arr) => arr.reduce((a, b) => a + b, 0) / arr.length;
  const sum = (arr) => arr.reduce((a, b) => a + b, 0);

  return {
    trades: trades.length,
    win_rate_pct: round((wins.length / rs.length) * 100, 2),
    profit_factor: round(profitFactor, 3),
    expectancy_r: round(mean(rs), 4),
    total_r: round(sum(rs), 2),
    avg_win_r: wins.length ? round(mean(wins), 3) : 0,
    avg_loss_r: losses.length ? round(mean(losses), 3) : 0,
    best_trade_r: round(Math.max(...rs), 2),
    worst_trade_r: round(Math.min(...rs), 2),
    max_losing_streak: worstStreak,
    net_pnl_usd: round(sum(pnls), 2),
    return_pct: round((finalEquity / initialEquity - 1) * 100, 2),
    final_equity: round(finalEquity, 2),
    max_drawdown_usd: round(dd.usd, 2),
    max_drawdown_pct: round(dd.pct, 2),
    sharpe: round(sharpe, 2),
    avg_bars_held: round(mean(trades.map((t) => t.barsHeld)), 1),
  };
}

/** Cek kriteria kelulusan TRADING_PLAN §8. */
export function passes(summary) {
  if (!summary.trades) return { ok: false, reasons: ['tidak ada trade'] };

  const reasons = [];
  if (summary.trades < MIN_SAMPLE) {
    reasons.push(`sampel terlalu kecil: ${summary.trades} trade (minimum mutlak ${MIN_SAMPLE})`);
  } else if (summary.trades < IDEAL_SAMPLE) {
    reasons.push(
      `sampel terbatas: ${summary.trades} trade — perpanjang periode data ` +
        `sampai ≥ ${IDEAL_SAMPLE} sebelum menaruh uang riil`,
    );
  }
  if (summary.profit_factor < PASS_PROFIT_FACTOR) {
    reasons.push(`profit factor ${summary.profit_factor} < ${PASS_PROFIT_FACTOR}`);
  }
  if (summary.max_drawdown_pct > PASS_MAX_DD_PCT) {
    reasons.push(`max drawdown ${summary.max_drawdown_pct}% > ${PASS_MAX_DD_PCT}%`);
  }
  if (summary.expectancy_r < PASS_EXPECTANCY_R) {
    reasons.push(`expectancy ${summary.expectancy_r}R < ${PASS_EXPECTANCY_R}R`);
  }
  return { ok: reasons.length === 0, reasons };
}

/** Bedah performa per sesi, per alasan exit, atau per bulan. */
export function breakdown(trades, by) {
  if (!trades.length) return [];

  const groups = new Map();
  for (const t of trades) {
    let key;
    if (by === 'month') key = new Date(t.entryTime).toISOString().slice(0, 7);
    else if (by === 'session') key = t.session;
    else if (by === 'exit_reason') key = t.exitReason;
    else key = t.strategy;

    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(t);
  }

  const rows = [];
  for (const [key, items] of groups) {
    const rs = items.map((t) => t.r);
    rows.push({
      key,
      trades: items.length,
      win_rate_pct: round((rs.filter((v) => v > 0).length / rs.length) * 100, 1),
      expectancy_r: round(rs.reduce((a, b) => a + b, 0) / rs.length, 3),
      total_r: round(rs.reduce((a, b) => a + b, 0), 2),
      net_usd: round(items.reduce((a, t) => a + t.pnl, 0), 2),
    });
  }
  rows.sort((a, b) => b.total_r - a.total_r);
  return rows;
}
