"""Strategi B — Trend Following via pullback ke EMA (TRADING_PLAN §5.B).

Ide: ikut arah H4/H1, masuk saat harga pullback ke zona EMA20–EMA50 M15 dan
menunjukkan penolakan, bukan mengejar saat harga sudah lari jauh.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..indicators import (
    adx,
    ema,
    htf_bias,
    is_bearish_engulfing,
    is_bearish_pin,
    is_bullish_engulfing,
    is_bullish_pin,
    swing_high,
    swing_low,
)
from .base import Strategy


class TrendPullback(Strategy):
    name = "trend"

    def __init__(
        self,
        fast: int = 20,
        slow: int = 50,
        min_adx: float = 20.0,
        sl_buffer_atr: float = 0.3,
        min_rr: float = 1.5,
        sessions: tuple[str, ...] = ("london", "ny"),
    ):
        self.fast = fast
        self.slow = slow
        self.min_adx = min_adx
        self.sl_buffer_atr = sl_buffer_atr
        self.min_rr = min_rr
        self.sessions = sessions
        self._ema_slow: pd.Series | None = None

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        sig = self.empty_signals(df)
        atr_v = df["atr"]

        ema_fast = ema(df["close"], self.fast)
        ema_slow = ema(df["close"], self.slow)
        self._ema_slow = ema_slow

        bias_h4 = htf_bias(df, "4h")
        bias_h1 = htf_bias(df, "1h")
        aligned_long = (bias_h4 == 1) & (bias_h1 == 1)
        aligned_short = (bias_h4 == -1) & (bias_h1 == -1)

        trending = adx(df, 14) >= self.min_adx
        in_session = df["session"].isin(self.sessions)

        zone_hi = pd.concat([ema_fast, ema_slow], axis=1).max(axis=1)
        zone_lo = pd.concat([ema_fast, ema_slow], axis=1).min(axis=1)
        # "Menyentuh zona" = wick masuk ke pita EMA, tapi close belum menembusnya.
        touched_long = (df["low"] <= zone_hi) & (df["close"] > zone_lo)
        touched_short = (df["high"] >= zone_lo) & (df["close"] < zone_hi)

        rejection_long = is_bullish_pin(df) | is_bullish_engulfing(df)
        rejection_short = is_bearish_pin(df) | is_bearish_engulfing(df)

        prev_low = swing_low(df)
        prev_high = swing_high(df)

        base = trending & in_session & atr_v.notna()

        long_ok = (
            base
            & aligned_long
            & (ema_fast > ema_slow)
            & touched_long
            & rejection_long
            & (df["low"] > prev_low)  # struktur belum rusak
        )
        short_ok = (
            base
            & aligned_short
            & (ema_fast < ema_slow)
            & touched_short
            & rejection_short
            & (df["high"] < prev_high)
        )

        buffer = self.sl_buffer_atr * atr_v
        entry_ref = df["close"]

        sl_long = pd.concat([prev_low, df["low"]], axis=1).min(axis=1) - buffer
        sl_short = pd.concat([prev_high, df["high"]], axis=1).max(axis=1) + buffer

        # TP: swing berlawanan terakhir, atau minimum RR — ambil yang lebih jauh.
        tp_long = pd.concat(
            [prev_high, entry_ref + self.min_rr * (entry_ref - sl_long)], axis=1
        ).max(axis=1)
        tp_short = pd.concat(
            [prev_low, entry_ref - self.min_rr * (sl_short - entry_ref)], axis=1
        ).min(axis=1)

        sig.loc[long_ok, "side"] = 1
        sig.loc[long_ok, "sl"] = sl_long[long_ok]
        sig.loc[long_ok, "tp"] = tp_long[long_ok]

        sig.loc[short_ok, "side"] = -1
        sig.loc[short_ok, "sl"] = sl_short[short_ok]
        sig.loc[short_ok, "tp"] = tp_short[short_ok]

        return self.enforce_rr(sig, entry_ref, self.min_rr)

    def invalidate(self, df: pd.DataFrame, i: int, side: int) -> bool:
        """Close M15 menembus EMA lambat = tren yang jadi alasan masuk sudah hilang."""
        if self._ema_slow is None:
            return False
        level = self._ema_slow.iat[i]
        if np.isnan(level):
            return False
        close = df["close"].iat[i]
        return close < level if side == 1 else close > level
