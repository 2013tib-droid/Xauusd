"""CLI backtest.

Contoh:
    python -m xauusd.run --data data/XAUUSD_M15.csv --strategy all
    python -m xauusd.run --synthetic --strategy trend --equity 1000 --risk 1.0
    python -m xauusd.run --data data/XAUUSD_M15.csv --source-tz Etc/GMT-3 \
        --strategy smc --sessions asia,london --export hasil.csv
"""

from __future__ import annotations

import argparse
import sys

from . import metrics
from .data import load_csv, synthetic
from .engine import Backtest, Config
from .strategies import REGISTRY


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m xauusd.run",
        description="Backtest strategi XAUUSD M15 sesuai docs/TRADING_PLAN.md",
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--data", help="CSV M15 hasil export MT5 (lihat docs/DATA.md)")
    src.add_argument(
        "--synthetic",
        action="store_true",
        help="pakai data sintetis untuk menguji engine (BUKAN untuk mengambil keputusan trading)",
    )

    p.add_argument("--source-tz", default="UTC", help="zona waktu stempel di CSV, mis. Etc/GMT-3")
    p.add_argument("--bars", type=int, default=8000, help="jumlah bar sintetis")
    p.add_argument("--seed", type=int, default=7, help="seed data sintetis")

    p.add_argument(
        "--strategy",
        default="all",
        help="breakout | trend | smc | all (boleh dipisah koma)",
    )
    p.add_argument("--equity", type=float, default=1000.0)
    p.add_argument("--risk", type=float, default=1.0, help="persen risiko per trade")
    p.add_argument("--spread", type=float, default=0.25, help="spread dalam dollar")
    p.add_argument("--commission", type=float, default=7.0, help="komisi per lot round-turn")
    p.add_argument("--min-lot", type=float, default=0.01)
    p.add_argument(
        "--undersized",
        choices=["skip", "min"],
        default="skip",
        help="saat lot < min_lot: lewati trade, atau paksa pakai min_lot (risiko > target)",
    )
    p.add_argument("--sessions", default="asia,london,ny")
    p.add_argument("--no-partial", action="store_true", help="matikan partial close di +1R")
    p.add_argument("--no-trail", action="store_true", help="matikan trailing stop")
    p.add_argument("--export", help="tulis daftar trade ke CSV")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.synthetic:
        df = synthetic(bars=args.bars, seed=args.seed)
        print(
            "\n⚠️  DATA SINTETIS — hasil di bawah hanya membuktikan engine berjalan.\n"
            "    Tidak ada nilai prediktif. Ganti dengan data riil (docs/DATA.md)\n"
            "    sebelum mengambil keputusan trading apa pun."
        )
    else:
        df = load_csv(args.data, source_tz=args.source_tz)

    print(f"\nData: {len(df)} bar M15 | {df.index[0]} → {df.index[-1]} (UTC)")

    names = list(REGISTRY) if args.strategy == "all" else args.strategy.split(",")
    unknown = [n for n in names if n not in REGISTRY]
    if unknown:
        print(f"Strategi tidak dikenal: {unknown}. Pilihan: {list(REGISTRY)}", file=sys.stderr)
        return 2

    cfg = Config(
        initial_equity=args.equity,
        risk_pct=args.risk,
        spread=args.spread,
        commission_per_lot=args.commission,
        min_lot=args.min_lot,
        undersized_policy=args.undersized,
        sessions=tuple(s.strip() for s in args.sessions.split(",")),
        partial_at_r=None if args.no_partial else 1.0,
        trail_at_r=None if args.no_trail else 2.0,
    )

    all_trades = []
    for name in names:
        bt = Backtest(df, REGISTRY[name](), cfg).run()
        trades = bt.trades_frame()
        summary = metrics.summarise(trades, bt.equity_curve, cfg.initial_equity)
        print(metrics.format_report(f"Strategi: {name}", summary, trades))

        if bt.skipped_undersized:
            print(
                f"\n  ⚠️  {bt.skipped_undersized} setup dilewati karena lot hasil hitungan "
                f"< {cfg.min_lot} lot.\n"
                "      Modal terlalu kecil untuk stop loss selebar itu — lihat TRADING_PLAN §3.2."
            )
        if bt.partial_blocked:
            print(
                f"\n  ⚠️  {bt.partial_blocked} kali partial close di +1R tidak bisa dieksekusi: "
                f"posisi sudah di ukuran lot minimum.\n"
                "      Di 0.01 lot, 'tutup separuh' itu mustahil — yang tersisa hanya\n"
                "      geser SL ke break even. Lihat TRADING_PLAN §3.2."
            )
        if not trades.empty:
            trades = trades.assign(strategy=name)
            all_trades.append(trades)

    if args.export and all_trades:
        import pandas as pd

        pd.concat(all_trades).to_csv(args.export, index=False)
        print(f"\nDaftar trade ditulis ke {args.export}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
