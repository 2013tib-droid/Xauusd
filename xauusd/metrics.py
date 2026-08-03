"""Metrik evaluasi backtest.

Urutan pentingnya metrik mengikuti TRADING_PLAN §8: expectancy dan profit
factor lebih dulu, win rate belakangan. Win rate tinggi tanpa expectancy
positif tidak berarti apa-apa.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Ambang kelulusan backtest, TRADING_PLAN §8.
PASS_PROFIT_FACTOR = 1.3
PASS_MAX_DD_PCT = 15.0
PASS_EXPECTANCY_R = 0.15
MIN_SAMPLE = 100      # di bawah ini, angka apa pun hanyalah kebisingan
IDEAL_SAMPLE = 200

# 4 bar M15 per jam × 24 jam × 252 hari perdagangan.
BARS_PER_YEAR = 4 * 24 * 252


def max_drawdown(equity: pd.Series) -> tuple[float, float]:
    """Kembalikan (drawdown_absolut_usd, drawdown_persen)."""
    if equity is None or equity.empty:
        return 0.0, 0.0
    peak = equity.cummax()
    dd = equity - peak
    pct = (dd / peak.replace(0, np.nan)) * 100
    return float(-dd.min()), float(-pct.min()) if pct.notna().any() else 0.0


def summarise(trades: pd.DataFrame, equity: pd.Series, initial_equity: float) -> dict:
    if trades.empty:
        return {
            "trades": 0,
            "note": "tidak ada trade — periksa filter sesi, ukuran lot minimum, atau parameter strategi",
        }

    r = trades["r"]
    pnl = trades["pnl"]
    wins, losses = r[r > 0], r[r <= 0]

    gross_win = pnl[pnl > 0].sum()
    gross_loss = -pnl[pnl <= 0].sum()
    profit_factor = float(gross_win / gross_loss) if gross_loss > 0 else float("inf")

    dd_usd, dd_pct = max_drawdown(equity)
    final_equity = float(equity.iloc[-1]) if equity is not None and len(equity) else initial_equity

    # Sharpe kasar dari return per bar, disetahunkan.
    rets = equity.pct_change().dropna() if equity is not None else pd.Series(dtype=float)
    sharpe = (
        float(rets.mean() / rets.std() * np.sqrt(BARS_PER_YEAR))
        if len(rets) > 1 and rets.std() > 0
        else 0.0
    )

    # Rentetan kalah terpanjang.
    streak = worst_streak = 0
    for value in r:
        streak = streak + 1 if value <= 0 else 0
        worst_streak = max(worst_streak, streak)

    return {
        "trades": int(len(trades)),
        "win_rate_pct": round(float((r > 0).mean() * 100), 2),
        "profit_factor": round(profit_factor, 3),
        "expectancy_r": round(float(r.mean()), 4),
        "total_r": round(float(r.sum()), 2),
        "avg_win_r": round(float(wins.mean()), 3) if len(wins) else 0.0,
        "avg_loss_r": round(float(losses.mean()), 3) if len(losses) else 0.0,
        "best_trade_r": round(float(r.max()), 2),
        "worst_trade_r": round(float(r.min()), 2),
        "max_losing_streak": int(worst_streak),
        "net_pnl_usd": round(float(pnl.sum()), 2),
        "return_pct": round((final_equity / initial_equity - 1) * 100, 2),
        "final_equity": round(final_equity, 2),
        "max_drawdown_usd": round(dd_usd, 2),
        "max_drawdown_pct": round(dd_pct, 2),
        "sharpe": round(sharpe, 2),
        "avg_bars_held": round(float(trades["bars_held"].mean()), 1),
    }


def passes(summary: dict) -> tuple[bool, list[str]]:
    """Cek kriteria kelulusan TRADING_PLAN §8. Kembalikan (lolos, alasan_gagal)."""
    if summary.get("trades", 0) == 0:
        return False, ["tidak ada trade"]

    reasons = []
    if summary["trades"] < MIN_SAMPLE:
        reasons.append(
            f"sampel terlalu kecil: {summary['trades']} trade (minimum mutlak {MIN_SAMPLE})"
        )
    elif summary["trades"] < IDEAL_SAMPLE:
        reasons.append(
            f"sampel terbatas: {summary['trades']} trade — perpanjang periode data "
            f"sampai ≥ {IDEAL_SAMPLE} sebelum menaruh uang riil"
        )
    if summary["profit_factor"] < PASS_PROFIT_FACTOR:
        reasons.append(f"profit factor {summary['profit_factor']} < {PASS_PROFIT_FACTOR}")
    if summary["max_drawdown_pct"] > PASS_MAX_DD_PCT:
        reasons.append(f"max drawdown {summary['max_drawdown_pct']}% > {PASS_MAX_DD_PCT}%")
    if summary["expectancy_r"] < PASS_EXPECTANCY_R:
        reasons.append(f"expectancy {summary['expectancy_r']}R < {PASS_EXPECTANCY_R}R")
    return (not reasons), reasons


def breakdown(trades: pd.DataFrame, by: str) -> pd.DataFrame:
    """Bedah performa per sesi, per alasan exit, atau per bulan."""
    if trades.empty:
        return pd.DataFrame()

    frame = trades.copy()
    if by == "month":
        frame["month"] = pd.to_datetime(frame["entry_time"]).dt.to_period("M").astype(str)
        by = "month"

    grouped = frame.groupby(by).agg(
        trades=("r", "size"),
        win_rate_pct=("r", lambda s: round(float((s > 0).mean() * 100), 1)),
        expectancy_r=("r", lambda s: round(float(s.mean()), 3)),
        total_r=("r", lambda s: round(float(s.sum()), 2)),
        net_usd=("pnl", lambda s: round(float(s.sum()), 2)),
    )
    return grouped.sort_values("total_r", ascending=False)


def format_report(name: str, summary: dict, trades: pd.DataFrame) -> str:
    lines = [f"\n{'=' * 62}", f"  {name}", "=" * 62]

    if summary.get("trades", 0) == 0:
        lines.append(f"  {summary.get('note', 'tidak ada trade')}")
        return "\n".join(lines)

    order = [
        ("Jumlah trade", "trades", ""),
        ("Win rate", "win_rate_pct", "%"),
        ("Profit factor", "profit_factor", ""),
        ("Expectancy", "expectancy_r", "R"),
        ("Total R", "total_r", "R"),
        ("Rata-rata menang", "avg_win_r", "R"),
        ("Rata-rata kalah", "avg_loss_r", "R"),
        ("Kalah beruntun terpanjang", "max_losing_streak", " trade"),
        ("Net P/L", "net_pnl_usd", " USD"),
        ("Return", "return_pct", "%"),
        ("Equity akhir", "final_equity", " USD"),
        ("Max drawdown", "max_drawdown_pct", "%"),
        ("Sharpe (kasar)", "sharpe", ""),
        ("Rata-rata durasi", "avg_bars_held", " bar M15"),
    ]
    for label, key, unit in order:
        lines.append(f"  {label:.<32} {summary[key]}{unit}")

    ok, reasons = passes(summary)
    lines.append("-" * 62)
    if ok:
        lines.append("  VERDIKT: LOLOS kriteria backtest (TRADING_PLAN §8)")
        lines.append("  Lanjut ke forward test demo 30 trade sebelum uang riil.")
    else:
        lines.append("  VERDIKT: BELUM LOLOS — jangan dipakai live")
        for reason in reasons:
            lines.append(f"    - {reason}")

    for label, key in (("Per sesi", "session"), ("Per alasan exit", "exit_reason")):
        table = breakdown(trades, key)
        if not table.empty:
            lines.append(f"\n  {label}:")
            lines.append("    " + table.to_string().replace("\n", "\n    "))

    return "\n".join(lines)
