"""CLI briefing: kondisi XAUUSD sekarang, bukan backtest.

Contoh:
    python -m xauusd.now --data data/XAUUSD_M15.csv --source-tz Etc/GMT-3 \\
        --macro DXY=99.30:-0.25 --macro US10Y=4.12:1.8 --macro US20Y=4.61:1.4 \\
        --news data/news.json --out briefing.html

Bagian makro diisi manual dari TradingView — lihat docs/BRIEFING.md.
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

import pandas as pd

from . import brief_html
from .brief import build, drop_forming_bar, load_news
from .data import load_csv
from .macro import parse_macro
from .strategies import REGISTRY


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m xauusd.now",
        description="Briefing pra-entry XAUUSD M15 sesuai docs/TRADING_PLAN.md",
    )
    p.add_argument("--data", required=True, help="CSV M15 terbaru dari MT5 (lihat docs/DATA.md)")
    p.add_argument("--source-tz", default="UTC", help="zona waktu stempel CSV, mis. Etc/GMT-3")
    p.add_argument(
        "--macro",
        action="append",
        default=[],
        metavar="SIMBOL=harga:persen",
        help="boleh diulang, mis. --macro DXY=99.30:-0.25 --macro US10Y=4.12:1.8",
    )
    p.add_argument("--news", help="berkas JSON kalender + judul berita (docs/BRIEFING.md)")
    p.add_argument("--strategy", default="all", help="breakout | trend | smc | all (pisah koma)")
    p.add_argument("--equity", type=float, default=1000.0)
    p.add_argument("--risk", type=float, default=1.0, help="persen risiko per trade")
    p.add_argument("--min-lot", type=float, default=0.01)
    p.add_argument("--undersized", choices=["skip", "min"], default="skip")
    p.add_argument("--out", default="briefing.html", help="berkas HTML yang ditulis")
    p.add_argument("--json", help="tulis juga briefing mentah sebagai JSON")
    p.add_argument("--open", action="store_true", help="buka hasilnya di browser")
    p.add_argument(
        "--keep-forming-bar",
        action="store_true",
        help="jangan buang bar M15 yang belum close (tidak disarankan)",
    )
    p.add_argument("--now", help="override waktu sekarang (ISO, UTC) — untuk pengujian")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    now = (
        pd.Timestamp(args.now, tz="UTC")
        if args.now
        else pd.Timestamp.utcnow().tz_localize("UTC")
    )

    names = list(REGISTRY) if args.strategy == "all" else args.strategy.split(",")
    unknown = [n for n in names if n not in REGISTRY]
    if unknown:
        print(f"Strategi tidak dikenal: {unknown}. Pilihan: {list(REGISTRY)}", file=sys.stderr)
        return 2

    df = load_csv(args.data, source_tz=args.source_tz)
    if not args.keep_forming_bar:
        before = len(df)
        df = drop_forming_bar(df, now=now)
        if len(df) < before:
            print("Bar M15 terakhir belum close — dibuang dari analisis.")

    if df.empty:
        print("Tidak ada bar yang sudah close di berkas ini.", file=sys.stderr)
        return 1

    try:
        readings = [parse_macro(spec) for spec in args.macro]
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    brief = build(
        df,
        macro_readings=readings,
        news=load_news(args.news),
        equity=args.equity,
        risk_pct=args.risk,
        min_lot=args.min_lot,
        undersized=args.undersized,
        strategies=names,
        now=now,
    )

    out = Path(args.out)
    out.write_text(brief_html.render(brief), encoding="utf-8")

    # Ringkasan singkat di terminal, supaya tidak perlu buka HTML kalau jawabannya "tidak ada".
    print(f"\nBar terakhir: {brief.bar_time_wib:%d %b %Y %H:%M} WIB | sesi {brief.session} "
          f"| harga {brief.price:,.2f}")
    if brief.setups:
        for s in brief.setups:
            status = "" if s.tradable else "  [lot < minimum — tidak terjangkau]"
            print(
                f"  {s.side_label:4} {s.strategy:9} entry {s.entry_ref:,.2f} "
                f"SL {s.sl:,.2f} TP {s.tp:,.2f} RR {s.rr:.2f} {s.lot:.2f} lot{status}"
            )
    else:
        print("  Tidak ada setup di bar terakhir.")

    for w in brief.warnings:
        print(f"  ⚠️  {w}")

    print(f"\nBriefing ditulis ke {out.resolve()}")

    if args.json:
        Path(args.json).write_text(brief.to_json(), encoding="utf-8")
        print(f"JSON ditulis ke {args.json}")

    if args.open:
        webbrowser.open(out.resolve().as_uri())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
