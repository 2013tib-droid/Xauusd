"""Strategi C — Smart Money / Liquidity Sweep (TRADING_PLAN §5.C).

Urutan kejadian yang dicari:

    1. Liquidity pool jelas  : Asia high/low atau high/low hari sebelumnya
    2. Sweep                 : wick menembus pool, close balik ke sisi asal
    3. MSS                   : close menembus swing point terakhir, arah berlawanan sweep
    4. FVG                   : ada fair value gap di leg MSS
    5. Entry                 : masuk searah MSS

PENYEDERHANAAN YANG DISENGAJA — baca ini sebelum percaya hasilnya:
entry dilakukan di open bar setelah MSS terkonfirmasi, **bukan** menunggu
retrace ke FVG/order block seperti di rulebook. Alasannya, data M15 tidak
cukup untuk memodelkan pengisian limit order secara jujur; entry market
menghasilkan estimasi yang lebih pesimis (entry lebih jauh, SL lebih lebar).
Hasil live dengan entry limit di FVG bisa lebih baik — tapi jangan menganggap
selisihnya sebagai keuntungan sampai terbukti di forward test.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..indicators import swing_high, swing_low
from .base import Strategy


class SmartMoney(Strategy):
    name = "smc"

    def __init__(
        self,
        # MSS jarang muncul di bar yang sama dengan sweep; beri ruang ~1,5 jam.
        sweep_lookback: int = 6,
        sl_buffer_atr: float = 0.3,
        min_rr: float = 1.5,
        target_lookback: int = 20,
        require_fvg: bool = True,
    ):
        self.sweep_lookback = sweep_lookback
        self.sl_buffer_atr = sl_buffer_atr
        self.min_rr = min_rr
        self.target_lookback = target_lookback
        self.require_fvg = require_fvg

    @staticmethod
    def _liquidity_pools(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """Level likuiditas yang berlaku pada tiap bar: Asia high/low hari ini
        (setelah sesi Asia tutup) dan high/low hari sebelumnya."""
        date = pd.Index(df.index.tz_convert("Asia/Jakarta").date)
        asia = df["session"].eq("asia")

        asia_high = df["high"].where(asia).groupby(date).cummax().groupby(date).ffill()
        asia_low = df["low"].where(asia).groupby(date).cummin().groupby(date).ffill()

        daily_high = df["high"].groupby(date).max()
        daily_low = df["low"].groupby(date).min()
        prev_high = pd.Series(
            daily_high.shift(1).reindex(date).to_numpy(), index=df.index
        )
        prev_low = pd.Series(
            daily_low.shift(1).reindex(date).to_numpy(), index=df.index
        )

        # Pool atas = yang terdekat di atas; ambil yang tersedia.
        pool_high = pd.concat([asia_high, prev_high], axis=1).max(axis=1)
        pool_low = pd.concat([asia_low, prev_low], axis=1).min(axis=1)
        return pool_high, pool_low

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        sig = self.empty_signals(df)
        atr_v = df["atr"]
        n = self.sweep_lookback

        pool_high, pool_low = self._liquidity_pools(df)

        # 2. Sweep: wick menembus pool, close kembali ke sisi asal.
        swept_low = (df["low"] < pool_low) & (df["close"] > pool_low)
        swept_high = (df["high"] > pool_high) & (df["close"] < pool_high)
        # Sweep boleh terjadi di bar ini atau sampai N bar sebelumnya.
        recent_sweep_low = swept_low.rolling(n, min_periods=1).max().astype(bool)
        recent_sweep_high = swept_high.rolling(n, min_periods=1).max().astype(bool)

        # 3. MSS: close menembus swing point terkonfirmasi terakhir.
        sh = swing_high(df)
        sl_ = swing_low(df)
        mss_up = (df["close"] > sh) & (df["close"].shift(1) <= sh.shift(1))
        mss_down = (df["close"] < sl_) & (df["close"].shift(1) >= sl_.shift(1))

        # 4. FVG: celah tiga-bar yang belum terisi pada leg MSS.
        if self.require_fvg:
            fvg_up = df["low"] > df["high"].shift(2)
            fvg_down = df["high"] < df["low"].shift(2)
            has_fvg_up = fvg_up.rolling(n, min_periods=1).max().astype(bool)
            has_fvg_down = fvg_down.rolling(n, min_periods=1).max().astype(bool)
        else:
            has_fvg_up = has_fvg_down = pd.Series(True, index=df.index)

        long_ok = recent_sweep_low & mss_up & has_fvg_up & atr_v.notna()
        short_ok = recent_sweep_high & mss_down & has_fvg_down & atr_v.notna()

        buffer = self.sl_buffer_atr * atr_v
        entry_ref = df["close"]

        # SL di luar ujung wick sweep.
        sweep_low_price = df["low"].rolling(n, min_periods=1).min()
        sweep_high_price = df["high"].rolling(n, min_periods=1).max()
        sl_long = sweep_low_price - buffer
        sl_short = sweep_high_price + buffer

        # TP di pool likuiditas berlawanan berikutnya.
        target_up = pd.concat(
            [df["high"].rolling(self.target_lookback).max().shift(1), pool_high], axis=1
        ).max(axis=1)
        target_down = pd.concat(
            [df["low"].rolling(self.target_lookback).min().shift(1), pool_low], axis=1
        ).min(axis=1)

        sig.loc[long_ok, "side"] = 1
        sig.loc[long_ok, "sl"] = sl_long[long_ok]
        sig.loc[long_ok, "tp"] = target_up[long_ok]
        sig.loc[long_ok, "inv_level"] = sweep_low_price[long_ok]

        sig.loc[short_ok, "side"] = -1
        sig.loc[short_ok, "sl"] = sl_short[short_ok]
        sig.loc[short_ok, "tp"] = target_down[short_ok]
        sig.loc[short_ok, "inv_level"] = sweep_high_price[short_ok]

        # Target yang lebih dekat dari entry (pool sudah terlewati) tidak valid.
        bad = ((sig["side"] == 1) & (sig["tp"] <= entry_ref)) | (
            (sig["side"] == -1) & (sig["tp"] >= entry_ref)
        )
        sig.loc[bad, ["side", "sl", "tp", "inv_level"]] = [0, np.nan, np.nan, np.nan]

        return self.enforce_rr(sig, entry_ref, self.min_rr)
