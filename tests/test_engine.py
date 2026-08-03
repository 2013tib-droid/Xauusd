"""Uji perilaku engine dengan data yang dibuat manual, supaya hasilnya
bisa dihitung tangan. Jalankan: python -m pytest tests/ -q
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from xauusd.data import add_session, synthetic
from xauusd.engine import CONTRACT_SIZE, Backtest, Config
from xauusd.indicators import htf_bias
from xauusd.strategies import REGISTRY
from xauusd.strategies.base import Strategy


def bars(prices, start="2026-03-02 07:00", freq="15min"):
    """Bangun DataFrame M15 dari daftar (open, high, low, close)."""
    idx = pd.date_range(start, periods=len(prices), freq=freq, tz="UTC")
    arr = np.array(prices, dtype=float)
    return pd.DataFrame(
        {"open": arr[:, 0], "high": arr[:, 1], "low": arr[:, 2], "close": arr[:, 3], "volume": 1},
        index=idx,
    )


class FixedSignal(Strategy):
    """Beri satu sinyal pada bar `at`, dengan SL/TP yang ditentukan penguji."""

    name = "fixed"

    def __init__(self, at, side, sl, tp):
        self.at, self.side, self.sl, self.tp = at, side, sl, tp

    def generate(self, df):
        sig = self.empty_signals(df)
        sig.iloc[self.at] = [self.side, self.sl, self.tp, np.nan]
        return sig


BASE_CFG = dict(
    # Equity sengaja dibuat besar di uji eksekusi supaya batas lot minimum tidak
    # ikut campur; batas itu diuji terpisah di test_undersized_trade_is_skipped.
    initial_equity=50_000.0,
    spread=0.0,
    commission_per_lot=0.0,
    partial_at_r=None,
    breakeven_at_r=None,
    trail_at_r=None,
    time_stop_bars=None,
    sessions=("asia", "london", "ny"),
)


# --------------------------------------------------------------- position sizing
def test_lot_size_matches_manual_calculation():
    """Equity $1.000, risk 1% = $10. SL $5 → 10 / (5 × 100) = 0.02 lot."""
    bt = Backtest(bars([(4000, 4001, 3999, 4000)] * 5), FixedSignal(0, 0, np.nan, np.nan),
                  Config(initial_equity=1000, risk_pct=1.0))
    lot, risk_usd = bt._size(1000.0, 5.0)
    assert lot == pytest.approx(0.02)
    assert risk_usd == pytest.approx(10.0)


def test_undersized_trade_is_skipped_by_default():
    """SL $15 pada akun $1.000 butuh 0.0067 lot — di bawah min lot 0.01.

    Ini kasus nyata dari TRADING_PLAN §3.2: bukan bug, tapi batas modal.
    """
    cfg = Config(initial_equity=1000, risk_pct=1.0, undersized_policy="skip")
    bt = Backtest(bars([(4000, 4001, 3999, 4000)] * 5), FixedSignal(0, 0, np.nan, np.nan), cfg)
    assert bt._size(1000.0, 15.0) == (0.0, 0.0)

    forced = Config(initial_equity=1000, risk_pct=1.0, undersized_policy="min")
    bt2 = Backtest(bars([(4000, 4001, 3999, 4000)] * 5), FixedSignal(0, 0, np.nan, np.nan), forced)
    lot, risk_usd = bt2._size(1000.0, 15.0)
    assert lot == pytest.approx(0.01)
    assert risk_usd == pytest.approx(15.0)  # risiko riil 1,5%, bukan 1%


# -------------------------------------------------------------------- eksekusi
def test_entry_happens_on_next_bar_open():
    df = bars([
        (4000, 4002, 3998, 4001),   # bar 0: sinyal
        (4010, 4012, 4008, 4011),   # bar 1: entry di open = 4010
        (4011, 4013, 4009, 4012),
        (4012, 4030, 4011, 4029),   # TP kena
    ])
    bt = Backtest(df, FixedSignal(0, 1, 4000.0, 4020.0), Config(**BASE_CFG)).run()
    trade = bt.trades[0]
    assert trade.entry == pytest.approx(4010.0)
    assert trade.entry_time == df.index[1]


def test_stop_wins_when_bar_touches_both_sl_and_tp():
    """Asumsi konservatif: data M15 tidak memberi tahu mana yang duluan."""
    df = bars([
        (4000, 4002, 3998, 4001),
        (4000, 4001, 3999, 4000),   # entry 4000
        (4000, 4025, 3990, 4010),   # bar ini menyentuh TP 4020 DAN SL 3995
    ])
    bt = Backtest(df, FixedSignal(0, 1, 3995.0, 4020.0), Config(**BASE_CFG)).run()
    assert bt.trades[0].exit_reason == "sl"
    assert bt.trades[0].r == pytest.approx(-1.0, abs=0.01)


def test_full_stop_loss_costs_exactly_one_r():
    df = bars([
        (4000, 4002, 3998, 4001),
        (4000, 4001, 3999, 4000),
        (4000, 4001, 3990, 3992),   # SL 3995 kena
    ])
    cfg = Config(**BASE_CFG)
    bt = Backtest(df, FixedSignal(0, 1, 3995.0, 4030.0), cfg).run()
    trade = bt.trades[0]
    assert trade.r == pytest.approx(-1.0, abs=1e-6)
    assert trade.pnl == pytest.approx(-trade.risk_usd)
    assert bt.equity_curve.iloc[-1] == pytest.approx(
        cfg.initial_equity - trade.risk_usd
    )


def test_short_trade_pnl_sign_is_correct():
    df = bars([
        (4000, 4002, 3998, 4001),
        (4000, 4001, 3999, 4000),   # entry short 4000
        (4000, 4001, 3970, 3975),   # TP 3980 kena
    ])
    bt = Backtest(df, FixedSignal(0, -1, 4010.0, 3980.0), Config(**BASE_CFG)).run()
    trade = bt.trades[0]
    assert trade.side == -1
    assert trade.pnl > 0
    assert trade.r == pytest.approx(2.0, abs=0.01)


def test_spread_and_commission_reduce_pnl():
    df = bars([
        (4000, 4002, 3998, 4001),
        (4000, 4001, 3999, 4000),
        (4000, 4030, 3999, 4029),
    ])
    clean = Config(**BASE_CFG)
    costly = Config(**{**BASE_CFG, "spread": 0.50, "commission_per_lot": 7.0})

    a = Backtest(df, FixedSignal(0, 1, 3990.0, 4020.0), clean).run().trades[0]
    b = Backtest(df, FixedSignal(0, 1, 3990.0, 4020.0), costly).run().trades[0]
    assert b.entry > a.entry          # buy diisi di ask
    assert b.pnl < a.pnl              # biaya menggerus hasil


def test_break_even_stop_is_labelled_separately():
    """Setelah partial di +1R, SL pindah ke BE. Kalau kena, itu bukan '-1R'."""
    df = bars([
        (4000, 4002, 3998, 4001),
        (4000, 4001, 3999, 4000),    # entry 4000, SL 3990, risiko $10/oz
        (4000, 4011, 3999, 4010),    # +1R → partial + SL ke BE
        (4010, 4011, 3995, 3996),    # kembali ke BE 4000 → kena
    ])
    cfg = Config(**{**BASE_CFG, "partial_at_r": 1.0, "breakeven_at_r": 1.0})
    bt = Backtest(df, FixedSignal(0, 1, 3990.0, 4050.0), cfg).run()
    trade = bt.trades[0]
    assert trade.exit_reason == "be_stop"
    assert trade.r > 0     # separuh posisi sudah dikunci untung di +1R


def test_partial_close_impossible_at_minimum_lot():
    """Realitas akun kecil: 0.01 lot tidak bisa ditutup separuh.

    Aturan "tutup 50% di +1R" hanya bisa dijalankan mulai 0.02 lot. Di bawah
    itu, satu-satunya yang tersisa adalah geser SL ke break even — jadi hasil
    terbaik yang mungkin dari sebuah trade yang berbalik adalah 0R, bukan +0,5R.
    """
    df = bars([
        (4000, 4002, 3998, 4001),
        (4000, 4001, 3999, 4000),
        (4000, 4011, 3999, 4010),   # +1R
        (4010, 4011, 3995, 3996),   # balik ke BE
    ])
    cfg = Config(**{**BASE_CFG, "initial_equity": 1000.0, "risk_pct": 1.0,
                    "partial_at_r": 1.0, "breakeven_at_r": 1.0,
                    "undersized_policy": "min"})
    trade = Backtest(df, FixedSignal(0, 1, 3990.0, 4050.0), cfg).run().trades[0]
    assert trade.lot == pytest.approx(0.01)
    assert trade.exit_reason == "be_stop"
    assert trade.r == pytest.approx(0.0)   # tidak ada profit yang bisa dikunci


def test_time_stop_closes_stagnant_position():
    flat = [(4000, 4001, 3999, 4000)] * 20
    df = bars([(4000, 4002, 3998, 4001)] + flat)
    cfg = Config(**{**BASE_CFG, "time_stop_bars": 4})
    bt = Backtest(df, FixedSignal(0, 1, 3980.0, 4060.0), cfg).run()
    assert bt.trades[0].exit_reason == "time_stop"
    assert bt.trades[0].bars_held == 4


def test_static_invalidation_level_closes_trade():
    class Inv(FixedSignal):
        def generate(self, df):
            sig = super().generate(df)
            sig.iloc[self.at, sig.columns.get_loc("inv_level")] = 3999.0
            return sig

    df = bars([
        (4000, 4002, 3998, 4001),
        (4000, 4001, 3999, 4000),
        (4000, 4001, 3997, 3998),   # close 3998 < inv_level 3999 → batal
    ])
    bt = Backtest(df, Inv(0, 1, 3980.0, 4040.0), Config(**BASE_CFG)).run()
    assert bt.trades[0].exit_reason == "invalidated"


# ----------------------------------------------------------------- filter risiko
def test_signals_outside_allowed_sessions_are_ignored():
    # 02:00 UTC = 09:00 WIB = sesi Asia.
    df = bars([(4000, 4002, 3998, 4001)] * 6, start="2026-03-02 02:00")
    cfg = Config(**{**BASE_CFG, "sessions": ("london", "ny")})
    bt = Backtest(df, FixedSignal(0, 1, 3990.0, 4030.0), cfg).run()
    assert bt.trades == []


def test_news_blackout_blocks_entry():
    df = bars([(4000, 4002, 3998, 4001)] * 6, start="2026-03-02 07:00")
    cfg = Config(**{**BASE_CFG, "news_blackout": (("2026-03-02 07:15", 15, 15),)})
    bt = Backtest(df, FixedSignal(0, 1, 3990.0, 4030.0), cfg).run()
    assert bt.trades == []


def test_only_one_position_open_at_a_time():
    class Always(Strategy):
        name = "always"

        def generate(self, df):
            sig = self.empty_signals(df)
            sig["side"] = 1
            sig["sl"] = df["close"] - 10
            sig["tp"] = df["close"] + 30
            return sig

    df = add_session(synthetic(600, seed=3))
    bt = Backtest(df, Always(), Config(**{**BASE_CFG, "undersized_policy": "min"})).run()
    frame = bt.trades_frame()
    if len(frame) > 1:
        # exit trade ke-n tidak boleh mendahului entry trade ke-(n+1)
        assert (frame["exit_time"].values[:-1] <= frame["entry_time"].values[1:]).all()


# ------------------------------------------------------------------- lookahead
def test_htf_bias_does_not_leak_future_information():
    """Mengubah bar-bar terakhir tidak boleh mengubah bias di bar-bar awal."""
    df = synthetic(2000, seed=11)
    original = htf_bias(df, "4h")

    tampered = df.copy()
    ohlc = ["open", "high", "low", "close"]
    tampered.loc[tampered.index[1500:], ohlc] *= 1.15  # ubah drastis masa depan
    after = htf_bias(tampered, "4h")

    assert (original.iloc[:1400] == after.iloc[:1400]).all()


@pytest.mark.parametrize("name", list(REGISTRY))
def test_strategy_signals_are_structurally_valid(name):
    df = add_session(synthetic(3000, seed=5))
    from xauusd.indicators import atr as _atr

    df["atr"] = _atr(df, 14)
    sig = REGISTRY[name]().generate(df)

    assert list(sig.index) == list(df.index)
    assert set(sig["side"].unique()) <= {-1, 0, 1}

    live = sig[sig["side"] != 0]
    if live.empty:
        return
    assert live[["sl", "tp"]].notna().all().all()

    longs = live[live["side"] == 1]
    shorts = live[live["side"] == -1]
    close = df["close"]
    assert (longs["sl"] < close.loc[longs.index]).all()
    assert (longs["tp"] > close.loc[longs.index]).all()
    assert (shorts["sl"] > close.loc[shorts.index]).all()
    assert (shorts["tp"] < close.loc[shorts.index]).all()

    # RR minimum 1,5 (TRADING_PLAN §0)
    risk = (close.loc[live.index] - live["sl"]).abs()
    reward = (live["tp"] - close.loc[live.index]).abs()
    assert (reward / risk >= 1.5 - 1e-9).all()


def test_contract_size_convention():
    """1,00 lot = 100 oz, jadi gerakan $1 = $100. Kalau ini salah, semua salah."""
    assert CONTRACT_SIZE == 100.0
    assert 0.01 * CONTRACT_SIZE * 5.0 == pytest.approx(5.0)  # 0.01 lot, gerak $5 = $5
