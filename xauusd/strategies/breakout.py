"""Strategi A — Breakout / Momentum (TRADING_PLAN §5.A).

Ide: konsolidasi sempit pecah dengan momentum saat London atau NY open.

Filter fakeout adalah inti strategi ini. Dalam regime range-bound, breakout
tanpa filter body dan filter ekspansi range akan menghancurkan akun — itulah
sebabnya keempat syarat konfirmasi di bawah tidak boleh dilonggarkan tanpa
backtest ulang.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..indicators import body_ratio, htf_bias
from .base import Strategy


class Breakout(Strategy):
    name = "breakout"

    def __init__(
        self,
        range_bars: int = 8,
        # Kalibrasi: tinggi range 8-bar biasanya 2,0–3,3 × ATR (median ~2,6).
        # Ambang 2,0 menangkap kira-kira kuartil paling sempit — itulah definisi
        # operasional "konsolidasi". Ambang 1,2 praktis tidak pernah terpenuhi.
        max_range_atr: float = 2.0,
        min_body_ratio: float = 0.60,
        min_expansion_atr: float = 1.2,
        sl_buffer_atr: float = 0.3,
        rr: float = 1.5,
        require_bias: bool = True,
    ):
        self.range_bars = range_bars
        self.max_range_atr = max_range_atr
        self.min_body_ratio = min_body_ratio
        self.min_expansion_atr = min_expansion_atr
        self.sl_buffer_atr = sl_buffer_atr
        self.rr = rr
        self.require_bias = require_bias

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        sig = self.empty_signals(df)
        atr_v = df["atr"]

        # Range konsolidasi dari N bar SEBELUM bar breakout.
        range_high = df["high"].rolling(self.range_bars).max().shift(1)
        range_low = df["low"].rolling(self.range_bars).min().shift(1)
        range_height = range_high - range_low

        tight = range_height < self.max_range_atr * atr_v
        expansion = (df["high"] - df["low"]) >= self.min_expansion_atr * atr_v
        strong_body = body_ratio(df) >= self.min_body_ratio

        # Jendela waktu: hanya sekitar London open dan NY open (§5.A).
        hour = df["hour_wib"]
        window = ((hour >= 14) & (hour < 15.5)) | ((hour >= 19.5) & (hour < 21))

        bias_h1 = htf_bias(df, "1h") if self.require_bias else pd.Series(0, index=df.index)

        base = tight & expansion & strong_body & window & atr_v.notna()

        long_ok = base & (df["close"] > range_high)
        short_ok = base & (df["close"] < range_low)
        if self.require_bias:
            long_ok &= bias_h1 >= 0
            short_ok &= bias_h1 <= 0

        # Jangan breakout tepat ke level kunci: butuh ruang ≥ 1,5 ATR ke high/low harian.
        day_high = df["high"].groupby(df.index.date).transform(
            lambda s: s.shift(1).cummax()
        )
        day_low = df["low"].groupby(df.index.date).transform(
            lambda s: s.shift(1).cummin()
        )
        room_up = (day_high - df["close"]).fillna(np.inf)
        room_down = (df["close"] - day_low).fillna(np.inf)
        long_ok &= (room_up >= 1.5 * atr_v) | (df["close"] > day_high.fillna(-np.inf))
        short_ok &= (room_down >= 1.5 * atr_v) | (df["close"] < day_low.fillna(np.inf))

        buffer = self.sl_buffer_atr * atr_v
        entry_ref = df["close"]

        sl_long = range_low - buffer
        sl_short = range_high + buffer

        sig.loc[long_ok, "side"] = 1
        sig.loc[long_ok, "sl"] = sl_long[long_ok]
        sig.loc[long_ok, "tp"] = (entry_ref + self.rr * (entry_ref - sl_long))[long_ok]
        # Balik masuk range = fakeout terkonfirmasi (§5.A "Invalidasi").
        sig.loc[long_ok, "inv_level"] = range_high[long_ok]

        sig.loc[short_ok, "side"] = -1
        sig.loc[short_ok, "sl"] = sl_short[short_ok]
        sig.loc[short_ok, "tp"] = (entry_ref - self.rr * (sl_short - entry_ref))[short_ok]
        sig.loc[short_ok, "inv_level"] = range_low[short_ok]

        return self.enforce_rr(sig, entry_ref)
