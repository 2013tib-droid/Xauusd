"""Indikator teknikal untuk XAUUSD M15.

Semua fungsi menerima dan mengembalikan pandas Series/DataFrame, dan tidak
melihat data masa depan (no lookahead) kecuali disebutkan eksplisit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    ranges = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (Wilder smoothing)."""
    return true_range(df).ewm(alpha=1 / period, adjust=False).mean()


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index — mengukur kekuatan tren, bukan arahnya."""
    up = df["high"].diff()
    down = -df["low"].diff()

    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)

    tr = true_range(df).ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(
        alpha=1 / period, adjust=False
    ).mean() / tr.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(
        alpha=1 / period, adjust=False
    ).mean() / tr.replace(0, np.nan)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean().fillna(0.0)


def swing_high(df: pd.DataFrame, left: int = 2, right: int = 2) -> pd.Series:
    """Harga swing high yang sudah terkonfirmasi, di-forward-fill.

    Sebuah bar adalah swing high jika high-nya tertinggi di antara `left` bar
    sebelumnya dan `right` bar sesudahnya. Nilainya baru tersedia `right` bar
    setelah pivot terbentuk — inilah yang mencegah lookahead.
    """
    highs = df["high"]
    is_pivot = pd.Series(True, index=df.index)
    for i in range(1, left + 1):
        is_pivot &= highs > highs.shift(i)
    for i in range(1, right + 1):
        is_pivot &= highs > highs.shift(-i)
    return highs.where(is_pivot).shift(right).ffill()


def swing_low(df: pd.DataFrame, left: int = 2, right: int = 2) -> pd.Series:
    """Harga swing low terkonfirmasi, di-forward-fill. Lihat `swing_high`."""
    lows = df["low"]
    is_pivot = pd.Series(True, index=df.index)
    for i in range(1, left + 1):
        is_pivot &= lows < lows.shift(i)
    for i in range(1, right + 1):
        is_pivot &= lows < lows.shift(-i)
    return lows.where(is_pivot).shift(right).ffill()


def body_ratio(df: pd.DataFrame) -> pd.Series:
    """Proporsi body terhadap total range candle (0..1). Filter doji/pin bar."""
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    return ((df["close"] - df["open"]).abs() / rng).fillna(0.0)


def is_bullish_engulfing(df: pd.DataFrame) -> pd.Series:
    prev_bear = df["close"].shift(1) < df["open"].shift(1)
    return (
        prev_bear
        & (df["close"] > df["open"])
        & (df["close"] >= df["open"].shift(1))
        & (df["open"] <= df["close"].shift(1))
    )


def is_bearish_engulfing(df: pd.DataFrame) -> pd.Series:
    prev_bull = df["close"].shift(1) > df["open"].shift(1)
    return (
        prev_bull
        & (df["close"] < df["open"])
        & (df["close"] <= df["open"].shift(1))
        & (df["open"] >= df["close"].shift(1))
    )


def is_bullish_pin(df: pd.DataFrame, wick_mult: float = 2.0) -> pd.Series:
    """Lower wick minimal `wick_mult` kali body, dan close di paruh atas."""
    body = (df["close"] - df["open"]).abs()
    lower = df[["open", "close"]].min(axis=1) - df["low"]
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    return (lower >= wick_mult * body) & ((df["close"] - df["low"]) / rng > 0.5)


def is_bearish_pin(df: pd.DataFrame, wick_mult: float = 2.0) -> pd.Series:
    body = (df["close"] - df["open"]).abs()
    upper = df["high"] - df[["open", "close"]].max(axis=1)
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    return (upper >= wick_mult * body) & ((df["high"] - df["close"]) / rng > 0.5)


def htf_bias(df: pd.DataFrame, rule: str, ema_period: int = 50) -> pd.Series:
    """Bias timeframe lebih tinggi (+1 bullish / -1 bearish / 0 netral),
    di-resample dari M15 lalu dipetakan balik ke tiap bar M15.

    Bias sebuah periode HTF hanya dipakai setelah periode itu **tutup**, jadi
    tidak ada informasi masa depan yang bocor ke bar M15.
    """
    htf = df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna()

    htf_ema = ema(htf["close"], ema_period)
    bias = pd.Series(0, index=htf.index, dtype=int)
    bias[htf["close"] > htf_ema] = 1
    bias[htf["close"] < htf_ema] = -1

    # Geser satu periode: bias baru berlaku untuk bar-bar SESUDAH periode ditutup.
    return bias.shift(1).reindex(df.index, method="ffill").fillna(0).astype(int)
