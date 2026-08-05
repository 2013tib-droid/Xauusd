"""Bangkitkan fixture paritas: satu CSV M15 + hasil backtest versi Python.

Berkas yang dihasilkan dipakai `parity.mjs` untuk membuktikan port JavaScript
menghasilkan angka yang sama dengan engine Python — sampai ke tiap trade, bukan
cuma ringkasannya.

    python3 web/tests/make_fixture.py

Jalankan ulang setiap kali engine, strategi, atau indikator Python berubah.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from xauusd import metrics  # noqa: E402
from xauusd.data import load_csv, synthetic  # noqa: E402
from xauusd.engine import Backtest, Config  # noqa: E402
from xauusd.strategies import REGISTRY  # noqa: E402

HERE = Path(__file__).resolve().parent
# Di-gzip: 30.000 bar jadi ~250 KB alih-alih ~2 MB, dan pandas maupun Node
# sama-sama bisa membacanya langsung.
CSV_PATH = HERE / "fixture.csv.gz"
EXPECTED_PATH = HERE / "expected.json"

BARS = 30000  # ~10 bulan data M15
SEED = 7

# Tiga konfigurasi, dipilih supaya jalur kode yang berbeda ikut kena:
# undersized="min" membuat hampir semua setup jadi trade (manajemen posisi
# teruji), dan modal besar tanpa trailing menguji cabang partial + TP penuh.
CONFIGS = {
    "default": {},
    "min_lot_no_partial": {
        "undersized_policy": "min",
        "partial_at_r": None,
        "risk_pct": 0.5,
        "spread": 0.4,
    },
    "big_account_no_trail": {
        "initial_equity": 50000.0,
        "risk_pct": 2.0,
        "trail_at_r": None,
        "commission_per_lot": 0.0,
        "sessions": ("london", "ny"),
        "time_stop_bars": 24,
    },
}

TRADE_FIELDS = [
    "side",
    "entry",
    "exit",
    "sl",
    "tp",
    "risk_dist",
    "lot",
    "risk_usd",
    "pnl",
    "r",
    "bars_held",
    "exit_reason",
    "session",
]


def main() -> int:
    df = synthetic(bars=BARS, seed=SEED)
    out = df.reset_index().rename(columns={"index": "ts"})
    out["DATE"] = out["ts"].dt.strftime("%Y.%m.%d")
    out["TIME"] = out["ts"].dt.strftime("%H:%M")
    out = out[["DATE", "TIME", "open", "high", "low", "close", "volume"]]
    out.columns = ["DATE", "TIME", "OPEN", "HIGH", "LOW", "CLOSE", "TICKVOL"]
    # Dua desimal, seperti kuotasi gold sungguhan. Efek sampingnya disengaja:
    # harga jadi sering seri persis, jadi cabang "range candle = 0" ikut teruji.
    #
    # mtime=0 membuat keluarannya byte-identik tiap kali dibangkitkan. Tanpa itu,
    # header gzip menyimpan waktu pembuatan dan berkas ini akan tampak berubah di
    # setiap run — cek "fixture masih mutakhir" di CI jadi selalu merah.
    out.to_csv(
        CSV_PATH,
        index=False,
        float_format="%.2f",
        compression={"method": "gzip", "mtime": 0},
    )

    # Baca ulang dari CSV supaya sisi Python dan JS mulai dari angka yang persis
    # sama (float_format memotong presisi — kalau tidak dibaca ulang, selisihnya
    # akan muncul sebagai "beda hasil" yang menyesatkan).
    df = load_csv(CSV_PATH, source_tz="UTC")

    expected = {"bars": int(len(df)), "cases": {}}
    for cfg_name, overrides in CONFIGS.items():
        cfg = Config(**overrides)
        for strat_name, strat_cls in REGISTRY.items():
            bt = Backtest(df, strat_cls(), cfg).run()
            trades = bt.trades_frame()
            summary = metrics.summarise(trades, bt.equity_curve, cfg.initial_equity)
            expected["cases"][f"{cfg_name}/{strat_name}"] = {
                "summary": summary,
                "skipped_undersized": bt.skipped_undersized,
                "partial_blocked": bt.partial_blocked,
                "trades": (
                    []
                    if trades.empty
                    else [
                        {
                            "entry_time": t["entry_time"].isoformat(),
                            "exit_time": t["exit_time"].isoformat(),
                            **{f: t[f] for f in TRADE_FIELDS},
                        }
                        for _, t in trades.iterrows()
                    ]
                ),
            }

    # Kompak, bukan indent: berkas ini dibangkitkan mesin dan tidak dibaca manusia.
    EXPECTED_PATH.write_text(
        json.dumps(expected, separators=(",", ":"), default=str) + "\n"
    )

    total = sum(len(c["trades"]) for c in expected["cases"].values())
    print(f"fixture.csv  : {len(df)} bar M15")
    print(f"expected.json: {len(expected['cases'])} kasus, {total} trade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
