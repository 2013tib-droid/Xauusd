"""Briefing pra-entry: kondisi XAUUSD M15 saat ini, bukan backtest.

Bedanya dengan `xauusd.run`: modul itu menguji strategi terhadap masa lalu,
modul ini memotret **keadaan sekarang** dan menjawab satu pertanyaan —
"menurut rulebook, ada setup yang sah atau tidak?"

Yang perlu dipegang saat membacanya:

* Sinyal dievaluasi pada **bar M15 terakhir yang sudah close**. Bar yang sedang
  berjalan sengaja dibuang, karena harga belum final dan sinyalnya bisa hilang
  sebelum candle-nya tutup.
* Kalau ada sinyal, entry-nya di **open bar berikutnya** — sama persis dengan
  asumsi backtester. Angka lot yang keluar juga dari fungsi sizing yang sama.
* Blok makro dan berita adalah **konteks**, bukan sinyal. Keduanya tidak pernah
  membuat setup yang gagal checklist jadi sah.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .data import WIB, add_session
from .engine import size_position
from .indicators import adx, atr, ema, htf_bias, swing_high, swing_low
from .macro import MacroBias, MacroReading, assess, conflicts
from .strategies import REGISTRY

ROUND_STEP = 50.0  # TRADING_PLAN §4: round number yang diperhatikan gold


@dataclass
class Setup:
    strategy: str
    side: int
    entry_ref: float
    sl: float
    tp: float
    rr: float
    risk_dist: float
    lot: float
    risk_usd: float
    tradable: bool
    notes: list[str] = field(default_factory=list)

    @property
    def side_label(self) -> str:
        return "BUY" if self.side > 0 else "SELL"


@dataclass
class Brief:
    generated_at: pd.Timestamp
    bar_time: pd.Timestamp
    bar_time_wib: pd.Timestamp
    price: float
    session: str
    bias_h4: int
    bias_h1: int
    aligned: bool
    ema20: float
    ema50: float
    atr14: float
    adx14: float
    levels: dict
    setups: list[Setup]
    macro: MacroBias
    news: dict
    blackout: dict
    warnings: list[str]
    equity: float
    risk_pct: float

    def to_json(self) -> str:
        def encode(obj):
            if isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            if isinstance(obj, (np.integer, np.floating)):
                return obj.item()
            return str(obj)

        payload = {
            "generated_at": self.generated_at,
            "bar_time_utc": self.bar_time,
            "bar_time_wib": self.bar_time_wib,
            "price": self.price,
            "session": self.session,
            "bias": {"h4": self.bias_h4, "h1": self.bias_h1, "aligned": self.aligned},
            "indicators": {
                "ema20": self.ema20,
                "ema50": self.ema50,
                "atr14": self.atr14,
                "adx14": self.adx14,
            },
            "levels": self.levels,
            "setups": [asdict(s) for s in self.setups],
            "macro": {
                "score": self.macro.score,
                "side": self.macro.side,
                "label": self.macro.label,
                "strength": self.macro.strength,
                "readings": [asdict(r) for r in self.macro.readings],
            },
            "news": self.news,
            "blackout": self.blackout,
            "warnings": self.warnings,
            "account": {"equity": self.equity, "risk_pct": self.risk_pct},
        }
        return json.dumps(payload, indent=2, default=encode, ensure_ascii=False)


BIAS_LABEL = {1: "bullish", -1: "bearish", 0: "netral"}


def _key_levels(df: pd.DataFrame, price: float) -> dict:
    """Level yang wajib diisi di jurnal sebelum lihat setup (TRADING_PLAN §4)."""
    local = df.index.tz_convert(WIB)
    days = pd.Index(local.date)
    today = days[-1]

    levels: dict = {}

    prev_days = days[days < today]
    if len(prev_days):
        yesterday = prev_days[-1]
        mask = days == yesterday
        levels["prev_day_high"] = float(df["high"][mask].max())
        levels["prev_day_low"] = float(df["low"][mask].min())

    today_mask = days == today
    asia = today_mask & (df["session"] == "asia").to_numpy()
    if asia.any():
        levels["asia_high"] = float(df["high"][asia].max())
        levels["asia_low"] = float(df["low"][asia].min())

    levels["swing_high"] = float(swing_high(df).iat[-1])
    levels["swing_low"] = float(swing_low(df).iat[-1])
    levels["round_above"] = float(np.ceil(price / ROUND_STEP) * ROUND_STEP)
    levels["round_below"] = float(np.floor(price / ROUND_STEP) * ROUND_STEP)

    return {k: v for k, v in levels.items() if not (isinstance(v, float) and np.isnan(v))}


def _blackout_status(news: dict, now: pd.Timestamp) -> dict:
    """Cek apakah `now` jatuh di dalam window blackout salah satu event kalender.

    Window default §7: 15 menit sebelum sampai 15 menit sesudah. Tiap event boleh
    menimpanya lewat field `before_min` / `after_min` (FOMC: 30/60).
    """
    active, upcoming = [], []

    for event in news.get("calendar", []):
        stamp = event.get("when_utc")
        if not stamp:
            continue
        when = pd.Timestamp(stamp)
        when = when.tz_localize("UTC") if when.tzinfo is None else when.tz_convert("UTC")

        before = int(event.get("before_min", 15))
        after = int(event.get("after_min", 15))
        start, end = when - pd.Timedelta(minutes=before), when + pd.Timedelta(minutes=after)

        entry = {
            "event": event.get("event", "?"),
            "impact": event.get("impact", "high"),
            "when_utc": when.isoformat(),
            "when_wib": when.tz_convert(WIB).strftime("%Y-%m-%d %H:%M WIB"),
            "window": f"{start.tz_convert(WIB):%H:%M}–{end.tz_convert(WIB):%H:%M} WIB",
            "minutes_away": round((when - now).total_seconds() / 60),
        }

        if start <= now <= end:
            active.append(entry)
        elif now < start:
            upcoming.append(entry)

    upcoming.sort(key=lambda e: e["minutes_away"])
    return {"active": active, "upcoming": upcoming[:5], "is_blackout": bool(active)}


def _evaluate(
    df: pd.DataFrame,
    names: list[str],
    equity: float,
    risk_pct: float,
    min_lot: float,
    undersized: str,
) -> list[Setup]:
    """Jalankan tiap strategi dan ambil sinyal pada bar terakhir yang sudah close."""
    setups: list[Setup] = []
    last = df.index[-1]

    for name in names:
        sig = REGISTRY[name]().generate(df)
        row = sig.loc[last]
        side = int(row["side"])
        if side == 0:
            continue

        entry_ref = float(df["close"].iat[-1])
        sl, tp = float(row["sl"]), float(row["tp"])
        risk_dist = abs(entry_ref - sl)
        reward = abs(tp - entry_ref)
        rr = reward / risk_dist if risk_dist > 0 else 0.0

        lot, risk_usd = size_position(
            equity,
            risk_dist,
            risk_pct=risk_pct,
            min_lot=min_lot,
            undersized_policy=undersized,
        )

        notes = []
        if lot == 0:
            notes.append(
                f"Lot hasil hitungan < {min_lot}. Dengan equity ${equity:,.0f} dan SL "
                f"${risk_dist:.2f}, risiko {risk_pct}% tidak terjangkau — TRADING_PLAN §3.2."
            )
        elif lot == min_lot:
            actual = lot * risk_dist * 100.0
            notes.append(
                f"Di lot minimum: partial close di +1R tidak bisa dieksekusi, "
                f"risiko riil ${actual:.2f} ({actual / equity * 100:.2f}% equity)."
            )

        setups.append(
            Setup(
                strategy=name,
                side=side,
                entry_ref=entry_ref,
                sl=sl,
                tp=tp,
                rr=rr,
                risk_dist=risk_dist,
                lot=lot,
                risk_usd=risk_usd,
                tradable=lot > 0,
                notes=notes,
            )
        )

    return setups


def build(
    df: pd.DataFrame,
    macro_readings: list[MacroReading] | None = None,
    news: dict | None = None,
    equity: float = 1000.0,
    risk_pct: float = 1.0,
    min_lot: float = 0.01,
    undersized: str = "skip",
    strategies: list[str] | None = None,
    now: pd.Timestamp | None = None,
) -> Brief:
    """Susun briefing dari data M15 mentah.

    `df` harus ber-index UTC dan berisi bar yang **sudah close** — pemanggil
    bertanggung jawab membuang bar yang masih berjalan (lihat `drop_forming_bar`).
    """
    news = news or {}
    macro_readings = macro_readings or []
    names = strategies or list(REGISTRY)
    now = now or pd.Timestamp.utcnow().tz_localize("UTC")

    df = add_session(df)
    df["atr"] = atr(df, 14)

    last = df.index[-1]
    price = float(df["close"].iat[-1])

    bias_h4 = int(htf_bias(df, "4h").iat[-1])
    bias_h1 = int(htf_bias(df, "1h").iat[-1])
    aligned = bias_h4 == bias_h1 != 0

    setups = _evaluate(df, names, equity, risk_pct, min_lot, undersized)
    macro = assess(macro_readings)
    blackout = _blackout_status(news, now)

    warnings: list[str] = []

    if blackout["is_blackout"]:
        events = ", ".join(e["event"] for e in blackout["active"])
        warnings.append(
            f"BLACKOUT BERITA aktif ({events}). TRADING_PLAN §7: flat — tidak ada "
            "entry baru, tidak ada posisi terbuka."
        )
    elif blackout["upcoming"] and blackout["upcoming"][0]["minutes_away"] <= 60:
        nxt = blackout["upcoming"][0]
        warnings.append(
            f"{nxt['event']} tinggal {nxt['minutes_away']} menit lagi "
            f"({nxt['when_wib']}). Blackout mulai {nxt['window'].split('–')[0]}."
        )

    session = str(df["session"].iat[-1])
    if session == "off":
        warnings.append(
            "Di luar jam sesi (TRADING_PLAN §2). Setup apa pun di luar sesi tidak sah."
        )

    if not aligned and bias_h4 != 0 and bias_h1 != 0:
        warnings.append(
            f"H4 {BIAS_LABEL[bias_h4]} vs H1 {BIAS_LABEL[bias_h1]} — berlawanan. "
            "TRADING_PLAN §4: hanya Strategi C (smc) yang boleh dipakai, dan hanya di level kunci."
        )

    for setup in setups:
        if conflicts(macro, setup.side):
            warnings.append(
                f"Setup {setup.strategy} {setup.side_label}, tapi {macro.label.lower()} "
                f"({macro.strength}). Konteks melawan — bukan pembatal otomatis, "
                "tapi alasan untuk menuntut checklist yang bersih."
            )

    stale_min = (now - last).total_seconds() / 60
    if stale_min > 45:
        warnings.append(
            f"Data terakhir berumur {stale_min:.0f} menit. Export ulang dari MT5 "
            "sebelum memakai briefing ini untuk keputusan."
        )

    return Brief(
        generated_at=now,
        bar_time=last,
        bar_time_wib=last.tz_convert(WIB),
        price=price,
        session=session,
        bias_h4=bias_h4,
        bias_h1=bias_h1,
        aligned=aligned,
        ema20=float(ema(df["close"], 20).iat[-1]),
        ema50=float(ema(df["close"], 50).iat[-1]),
        atr14=float(df["atr"].iat[-1]),
        adx14=float(adx(df, 14).iat[-1]),
        levels=_key_levels(df, price),
        setups=setups,
        macro=macro,
        news=news,
        blackout=blackout,
        warnings=warnings,
        equity=equity,
        risk_pct=risk_pct,
    )


def drop_forming_bar(df: pd.DataFrame, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Buang bar M15 terakhir kalau periodenya belum selesai.

    Export MT5 hampir selalu menyertakan candle yang sedang berjalan. Sinyal dari
    bar setengah jadi tidak bisa dipercaya: harga close-nya masih berubah.
    """
    if df.empty:
        return df
    now = now or pd.Timestamp.utcnow().tz_localize("UTC")
    if df.index[-1] + pd.Timedelta(minutes=15) > now:
        return df.iloc[:-1]
    return df


def load_news(path: str | Path | None) -> dict:
    """Muat berkas berita/kalender JSON. Lihat docs/BRIEFING.md untuk formatnya."""
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Berkas berita harus berupa objek JSON dengan kunci 'calendar'/'headlines'")
    return data
