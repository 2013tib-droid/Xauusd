"""Kontrak dasar strategi.

Sebuah strategi mengubah DataFrame M15 (sudah ber-kolom `session`, `hour_wib`,
dan `atr`) menjadi tabel sinyal dengan index yang sama dan kolom:

    side       : +1 buy, -1 sell, 0 tidak ada sinyal
    sl         : harga stop loss
    tp         : harga take profit
    inv_level  : level yang, kalau ditembus balik oleh harga close, membatalkan
                 setup (opsional, isi NaN kalau tidak dipakai)

Sinyal pada baris ke-i berarti "setup terkonfirmasi saat bar ke-i close".
Engine akan mengeksekusinya di open bar ke-(i+1). Semua kolom sl/tp karenanya
hanya boleh memakai informasi sampai bar ke-i.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MIN_RR = 1.5  # TRADING_PLAN §0: di bawah ini, skip.


class Strategy:
    name = "base"

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError

    @staticmethod
    def empty_signals(df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "side": np.zeros(len(df), dtype=int),
                "sl": np.full(len(df), np.nan),
                "tp": np.full(len(df), np.nan),
                "inv_level": np.full(len(df), np.nan),
            },
            index=df.index,
        )

    @staticmethod
    def enforce_rr(sig: pd.DataFrame, ref_price: pd.Series, min_rr: float = MIN_RR) -> pd.DataFrame:
        """Buang sinyal yang risk-reward-nya di bawah ambang."""
        risk = (ref_price - sig["sl"]).abs()
        reward = (sig["tp"] - ref_price).abs()
        bad = (risk <= 0) | (reward / risk.replace(0, np.nan) < min_rr)
        sig.loc[bad.fillna(True), ["side", "sl", "tp", "inv_level"]] = [0, np.nan, np.nan, np.nan]
        return sig
