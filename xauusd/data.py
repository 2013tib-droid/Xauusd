"""Pemuatan dan penyiapan data XAUUSD M15.

Sumber data utama adalah CSV hasil export MetaTrader 5 (lihat docs/DATA.md).
Tersedia juga generator data sintetis untuk menguji engine tanpa data riil.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

WIB = "Asia/Jakarta"

# Batas sesi dalam jam WIB, sesuai docs/TRADING_PLAN.md §2.
SESSIONS = {
    "asia": (7, 12),
    "london": (14, 18),
    "ny": (19.5, 23),
}

_COLUMN_ALIASES = {
    "open": {"open", "o", "<open>"},
    "high": {"high", "h", "<high>"},
    "low": {"low", "l", "<low>"},
    "close": {"close", "c", "<close>", "adj close"},
    "volume": {"volume", "vol", "tickvol", "<tickvol>", "<vol>"},
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        key = str(col).strip().lower()
        for target, aliases in _COLUMN_ALIASES.items():
            if key == target or key in aliases:
                rename[col] = target
                break
    df = df.rename(columns=rename)

    missing = {"open", "high", "low", "close"} - set(df.columns)
    if missing:
        raise ValueError(
            f"Kolom OHLC tidak lengkap, yang hilang: {sorted(missing)}. "
            f"Kolom yang terbaca: {list(df.columns)}"
        )
    if "volume" not in df.columns:
        df["volume"] = np.nan
    return df[["open", "high", "low", "close", "volume"]]


def _build_index(raw: pd.DataFrame, df: pd.DataFrame) -> pd.DatetimeIndex:
    """Cari kolom waktu, gabungkan DATE+TIME kalau terpisah (format MT5)."""
    lower = {str(c).strip().lower(): c for c in raw.columns}

    date_col = next((lower[k] for k in ("date", "<date>", "tanggal") if k in lower), None)
    time_col = next((lower[k] for k in ("time", "<time>", "waktu") if k in lower), None)

    if date_col is not None and time_col is not None:
        stamp = raw[date_col].astype(str).str.strip() + " " + raw[time_col].astype(str).str.strip()
    elif date_col is not None:
        stamp = raw[date_col].astype(str)
    else:
        dt_col = next(
            (lower[k] for k in ("datetime", "timestamp", "gmt time", "local time") if k in lower),
            None,
        )
        if dt_col is None:
            # Fallback: index bawaan file (mis. CSV yang sudah punya index waktu).
            return pd.DatetimeIndex(pd.to_datetime(raw.index, errors="coerce", utc=True))
        stamp = raw[dt_col].astype(str)

    stamp = stamp.str.replace(".", "-", regex=False)
    return pd.DatetimeIndex(pd.to_datetime(stamp, errors="coerce", utc=True))


def load_csv(path: str | Path, source_tz: str = "UTC") -> pd.DataFrame:
    """Muat CSV OHLC M15 menjadi DataFrame ber-index UTC.

    Args:
        path: berkas CSV/TSV. Pemisah dideteksi otomatis (koma, titik koma, tab).
        source_tz: zona waktu stempel di berkas. Server MT5 umumnya UTC+2/+3 —
            cek di broker-mu dan isi mis. "Etc/GMT-3". Salah isi di sini akan
            menggeser seluruh filter sesi.
    """
    path = Path(path)
    raw = pd.read_csv(path, sep=None, engine="python", skipinitialspace=True)

    df = _normalise_columns(raw.copy())
    naive = _build_index(raw, df)

    if source_tz.upper() != "UTC":
        # Stempel dibaca sebagai UTC oleh _build_index; lepas label itu lalu
        # pasang zona waktu sumber yang sebenarnya.
        idx = naive.tz_localize(None).tz_localize(source_tz, ambiguous="NaT", nonexistent="NaT")
        df.index = idx.tz_convert("UTC")
    else:
        df.index = naive

    df = df[df.index.notna()]
    df = df[~df.index.duplicated(keep="first")].sort_index()

    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])

    if df.empty:
        raise ValueError(f"Tidak ada baris valid setelah parsing {path}")
    return df


def synthetic(
    bars: int = 8000,
    start: str = "2026-01-05 00:00",
    seed: int = 7,
    start_price: float = 4000.0,
) -> pd.DataFrame:
    """Bangkitkan data M15 sintetis yang menyerupai gold.

    Ini BUKAN pengganti data riil dan hasil backtest-nya tidak punya arti
    prediktif. Gunanya hanya untuk menguji bahwa engine, sizing, dan metrik
    berjalan benar. Karakter yang ditiru: volatilitas per sesi, tren yang
    berganti arah, dan volatility clustering.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start=start, periods=bars, freq="15min", tz="UTC")
    hour_wib = (idx.tz_convert(WIB).hour + idx.tz_convert(WIB).minute / 60).to_numpy()

    # Volatilitas per sesi: London/NY jauh lebih ramai daripada Asia dan malam.
    vol = np.full(bars, 0.35)
    vol[(hour_wib >= 7) & (hour_wib < 12)] = 0.55
    vol[(hour_wib >= 14) & (hour_wib < 18)] = 1.30
    vol[(hour_wib >= 19.5) & (hour_wib < 23)] = 1.45
    vol[idx.dayofweek >= 5] = 0.15

    # Rezim tren yang berganti tiap ~2 minggu, plus volatility clustering.
    regime = np.repeat(rng.normal(0, 0.035, bars // 1300 + 1), 1300)[:bars]
    cluster = np.abs(rng.normal(1.0, 0.35, bars))
    cluster = pd.Series(cluster).ewm(span=40).mean().to_numpy()

    steps = rng.normal(regime, vol * cluster)
    close = start_price + np.cumsum(steps)
    open_ = np.concatenate([[start_price], close[:-1]])

    wick = np.abs(rng.normal(0, vol * cluster * 0.7, bars))
    high = np.maximum(open_, close) + wick
    low = np.minimum(open_, close) - np.abs(rng.normal(0, vol * cluster * 0.7, bars))

    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.integers(50, 3000, bars),
        },
        index=idx,
    )


def add_session(df: pd.DataFrame, tz: str = WIB) -> pd.DataFrame:
    """Tambah kolom `session` dan `hour_wib` berdasarkan jam lokal WIB."""
    df = df.copy()
    local = df.index.tz_convert(tz)
    hours = local.hour + local.minute / 60
    df["hour_wib"] = hours

    session = pd.Series("off", index=df.index, dtype=object)
    for name, (start_h, end_h) in SESSIONS.items():
        session[(hours >= start_h) & (hours < end_h)] = name
    session[df.index.dayofweek >= 5] = "off"  # weekend
    df["session"] = session
    return df
