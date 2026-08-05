"""Engine backtest bar-by-bar untuk XAUUSD M15.

Aturan eksekusi yang dipakai (sengaja konservatif — lebih baik hasil backtest
terlalu pesimis daripada terlalu optimis):

* Sinyal dihasilkan pada **close** sebuah bar, eksekusi pada **open bar berikutnya**.
* Kalau dalam satu bar harga menyentuh SL dan TP sekaligus, **SL yang dianggap kena**.
  Data M15 tidak memberi tahu mana yang lebih dulu.
* Spread dibebankan penuh satu kali saat entry.
* Komisi dibebankan per lot round-turn.
* Hanya satu posisi terbuka pada satu waktu (sesuai TRADING_PLAN §0).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .data import add_session
from .indicators import atr

# XAUUSD: 1,00 lot = 100 oz, jadi pergerakan $1,00 = $100 per lot.
CONTRACT_SIZE = 100.0


@dataclass
class Config:
    """Parameter akun dan manajemen risiko.

    Default-nya mencerminkan akun kecil (< $1.000) dengan risiko 1%, sesuai
    jawaban di sesi perencanaan. Perhatikan `min_lot`: lihat TRADING_PLAN §3.2
    soal kenapa akun $1.000 sering tidak bisa menegakkan risiko 1% yang sebenarnya.
    """

    initial_equity: float = 1000.0
    risk_pct: float = 1.0
    spread: float = 0.25          # dalam dollar; gold ritel biasanya $0.15–0.40
    commission_per_lot: float = 7.0  # round-turn per 1,00 lot
    min_lot: float = 0.01
    lot_step: float = 0.01
    max_lot: float = 100.0

    # Apa yang dilakukan saat lot hasil perhitungan < min_lot:
    #   "skip" — trade dilewati (jujur: setup ini memang tak terjangkau modalmu)
    #   "min"  — tetap masuk dengan min_lot, risiko riil jadi > risk_pct
    undersized_policy: str = "skip"

    # Manajemen posisi (TRADING_PLAN §3.4)
    partial_at_r: float | None = 1.0     # tutup sebagian di +1R
    partial_fraction: float = 0.5
    breakeven_at_r: float | None = 1.0   # geser SL ke BE di +1R
    trail_at_r: float | None = 2.0       # mulai trailing di +2R
    trail_atr_mult: float = 2.0
    time_stop_bars: int | None = 12      # 12 bar M15 = 3 jam

    # Rem risiko (TRADING_PLAN §3.3)
    daily_loss_limit_r: float | None = 2.0
    weekly_loss_limit_r: float | None = 4.0
    drawdown_derisk_pct: float = 10.0    # DD 10% → risiko dipotong setengah
    drawdown_derisk_factor: float = 0.5

    sessions: tuple[str, ...] = ("asia", "london", "ny")
    news_blackout: tuple[tuple[str, int, int], ...] = ()
    # ("2026-08-12 19:30", menit_sebelum, menit_sesudah) — stempel dalam UTC


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp | None = None
    side: int = 0
    strategy: str = ""
    session: str = ""
    entry: float = 0.0
    exit: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    risk_dist: float = 0.0
    lot: float = 0.0
    risk_usd: float = 0.0
    pnl: float = 0.0
    r: float = 0.0
    bars_held: int = 0
    exit_reason: str = ""
    equity_after: float = 0.0


@dataclass
class _Position:
    side: int
    entry: float
    sl: float
    tp: float
    risk_dist: float
    lot: float
    open_lot: float
    risk_usd: float
    entry_time: pd.Timestamp
    entry_index: int
    strategy: str
    session: str
    inv_level: float = float("nan")
    realised_pnl: float = 0.0
    partial_done: bool = False
    be_done: bool = False
    trailing: bool = False
    exits: list = field(default_factory=list)


def _round_lot(lot: float, step: float) -> float:
    return float(np.floor(lot / step + 1e-9) * step)


def size_position(
    equity: float,
    risk_dist: float,
    risk_pct: float = 1.0,
    min_lot: float = 0.01,
    lot_step: float = 0.01,
    max_lot: float = 100.0,
    undersized_policy: str = "skip",
) -> tuple[float, float]:
    """Kembalikan (lot, risiko_usd) untuk satu setup. Lot 0 = trade dilewati.

    Dipakai bersama oleh backtester dan briefing, supaya angka lot yang kamu
    lihat sebelum entry persis sama dengan yang dipakai saat menguji strategi.
    """
    if risk_dist <= 0:
        return 0.0, 0.0

    risk_usd = equity * risk_pct / 100.0
    lot = _round_lot(risk_usd / (risk_dist * CONTRACT_SIZE), lot_step)

    if lot < min_lot:
        if undersized_policy == "min":
            lot = min_lot
        else:
            return 0.0, 0.0

    lot = min(lot, max_lot)
    return lot, lot * risk_dist * CONTRACT_SIZE


def _blackout_mask(index: pd.DatetimeIndex, windows) -> pd.Series:
    mask = pd.Series(False, index=index)
    for stamp, before, after in windows:
        centre = pd.Timestamp(stamp, tz="UTC")
        mask |= (index >= centre - pd.Timedelta(minutes=before)) & (
            index <= centre + pd.Timedelta(minutes=after)
        )
    return mask


class Backtest:
    """Jalankan satu strategi terhadap satu set data M15."""

    def __init__(self, df: pd.DataFrame, strategy, config: Config | None = None):
        self.cfg = config or Config()
        self.strategy = strategy
        self.df = add_session(df)
        self.df["atr"] = atr(self.df, 14)
        self.signals = strategy.generate(self.df)
        self.trades: list[Trade] = []
        self.equity_curve: pd.Series | None = None
        self.skipped_undersized = 0
        self.partial_blocked = 0

    # ---------------------------------------------------------------- sizing
    def _size(self, equity: float, risk_dist: float) -> tuple[float, float]:
        """Kembalikan (lot, risiko_usd). Lot 0 berarti trade harus dilewati."""
        cfg = self.cfg
        return size_position(
            equity,
            risk_dist,
            risk_pct=cfg.risk_pct,
            min_lot=cfg.min_lot,
            lot_step=cfg.lot_step,
            max_lot=cfg.max_lot,
            undersized_policy=cfg.undersized_policy,
        )

    # ------------------------------------------------------------------ exit
    def _close(self, pos: _Position, price: float, lot: float, reason: str) -> float:
        pnl = pos.side * (price - pos.entry) * lot * CONTRACT_SIZE
        pnl -= self.cfg.commission_per_lot * lot
        pos.realised_pnl += pnl
        pos.open_lot = round(pos.open_lot - lot, 8)
        pos.exits.append((price, lot, reason))
        return pnl

    def _record(self, pos: _Position, exit_time, exit_price, bars, reason, equity) -> None:
        r = pos.realised_pnl / pos.risk_usd if pos.risk_usd else 0.0
        self.trades.append(
            Trade(
                entry_time=pos.entry_time,
                exit_time=exit_time,
                side=pos.side,
                strategy=pos.strategy,
                session=pos.session,
                entry=pos.entry,
                exit=exit_price,
                sl=pos.sl,
                tp=pos.tp,
                risk_dist=pos.risk_dist,
                lot=pos.lot,
                risk_usd=pos.risk_usd,
                pnl=pos.realised_pnl,
                r=r,
                bars_held=bars,
                exit_reason=reason,
                equity_after=equity,
            )
        )

    # ------------------------------------------------------------------- run
    def run(self) -> "Backtest":
        cfg = self.cfg
        df = self.df
        sig = self.signals
        n = len(df)

        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        opens = df["open"].to_numpy()
        closes = df["close"].to_numpy()
        atr_vals = df["atr"].to_numpy()
        sessions = df["session"].to_numpy()

        sides = sig["side"].to_numpy()
        sig_sl = sig["sl"].to_numpy()
        sig_tp = sig["tp"].to_numpy()
        sig_inv = (
            sig["inv_level"].to_numpy()
            if "inv_level" in sig.columns
            else np.full(n, np.nan)
        )

        blackout = _blackout_mask(df.index, cfg.news_blackout).to_numpy()
        wib_date = df.index.tz_convert("Asia/Jakarta").date
        iso_week = df.index.tz_convert("Asia/Jakarta").isocalendar()
        week_key = list(zip(iso_week.year, iso_week.week))

        equity = cfg.initial_equity
        peak_equity = equity
        equity_points = np.full(n, equity, dtype=float)

        daily_r: dict = {}
        weekly_r: dict = {}
        pos: _Position | None = None

        for i in range(1, n):
            bar_high, bar_low, bar_close = highs[i], lows[i], closes[i]

            # ---------------------------------------------------- kelola posisi
            if pos is not None:
                bars_held = i - pos.entry_index
                r_dist = pos.risk_dist
                exited = False

                # 1. Stop loss lebih dulu — asumsi konservatif.
                hit_sl = bar_low <= pos.sl if pos.side == 1 else bar_high >= pos.sl
                if hit_sl:
                    # Bedakan stop asli dari stop yang sudah digeser ke BE/trailing:
                    # keduanya "kena SL", tapi artinya sangat berbeda saat direview.
                    reason = "sl" if not (pos.be_done or pos.trailing) else (
                        "trail_stop" if pos.trailing else "be_stop"
                    )
                    equity += self._close(pos, pos.sl, pos.open_lot, reason)
                    exited, exit_price = True, pos.sl

                # 2. Take profit.
                if not exited:
                    hit_tp = bar_high >= pos.tp if pos.side == 1 else bar_low <= pos.tp
                    if hit_tp:
                        equity += self._close(pos, pos.tp, pos.open_lot, "tp")
                        exited, exit_price, reason = True, pos.tp, "tp"

                # 3. Partial + break even di +1R.
                if not exited and cfg.partial_at_r and not pos.partial_done:
                    level = pos.entry + pos.side * cfg.partial_at_r * r_dist
                    reached = bar_high >= level if pos.side == 1 else bar_low <= level
                    if reached:
                        part = _round_lot(pos.open_lot * cfg.partial_fraction, cfg.lot_step)
                        if part >= cfg.min_lot and part < pos.open_lot:
                            equity += self._close(pos, level, part, "partial")
                        else:
                            # Posisi sudah sekecil min_lot — separuhnya tidak ada.
                            self.partial_blocked += 1
                        pos.partial_done = True
                        if cfg.breakeven_at_r is not None:
                            pos.sl = pos.entry + pos.side * self.cfg.spread
                            pos.be_done = True

                # 4. Trailing stop mulai +2R.
                if not exited and cfg.trail_at_r:
                    level = pos.entry + pos.side * cfg.trail_at_r * r_dist
                    reached = bar_high >= level if pos.side == 1 else bar_low <= level
                    if reached:
                        pos.trailing = True
                    if pos.trailing and not np.isnan(atr_vals[i]):
                        gap = cfg.trail_atr_mult * atr_vals[i]
                        trail = (
                            bar_close - gap if pos.side == 1 else bar_close + gap
                        )
                        pos.sl = max(pos.sl, trail) if pos.side == 1 else min(pos.sl, trail)

                # 5a. Invalidasi level statis: harga kembali menembus level yang
                #     jadi dasar setup (mis. balik masuk range pada breakout).
                if not exited and not np.isnan(pos.inv_level):
                    broken = (
                        bar_close < pos.inv_level
                        if pos.side == 1
                        else bar_close > pos.inv_level
                    )
                    if broken:
                        equity += self._close(pos, bar_close, pos.open_lot, "invalidated")
                        exited, exit_price, reason = True, bar_close, "invalidated"

                # 5b. Invalidasi dinamis yang didefinisikan strategi.
                if not exited and hasattr(self.strategy, "invalidate"):
                    if self.strategy.invalidate(df, i, pos.side):
                        equity += self._close(pos, bar_close, pos.open_lot, "invalidated")
                        exited, exit_price, reason = True, bar_close, "invalidated"

                # 6. Time stop.
                if not exited and cfg.time_stop_bars and bars_held >= cfg.time_stop_bars:
                    equity += self._close(pos, bar_close, pos.open_lot, "time_stop")
                    exited, exit_price, reason = True, bar_close, "time_stop"

                if exited:
                    self._record(pos, df.index[i], exit_price, bars_held, reason, equity)
                    trade_r = pos.realised_pnl / pos.risk_usd if pos.risk_usd else 0.0
                    day, wk = wib_date[i], week_key[i]
                    daily_r[day] = daily_r.get(day, 0.0) + trade_r
                    weekly_r[wk] = weekly_r.get(wk, 0.0) + trade_r
                    peak_equity = max(peak_equity, equity)
                    pos = None

            equity_points[i] = equity

            # ------------------------------------------------------ entry baru
            if pos is not None or equity <= 0:
                continue

            side = sides[i - 1]
            if side == 0 or np.isnan(sig_sl[i - 1]):
                continue
            if sessions[i] not in cfg.sessions or blackout[i]:
                continue

            day, wk = wib_date[i], week_key[i]
            if cfg.daily_loss_limit_r and daily_r.get(day, 0.0) <= -cfg.daily_loss_limit_r:
                continue
            if cfg.weekly_loss_limit_r and weekly_r.get(wk, 0.0) <= -cfg.weekly_loss_limit_r:
                continue

            entry = opens[i] + (cfg.spread if side == 1 else 0.0)
            sl, tp = sig_sl[i - 1], sig_tp[i - 1]

            # Sinyal yang harganya sudah lewat saat bar dibuka: batal.
            if (side == 1 and (entry <= sl or entry >= tp)) or (
                side == -1 and (entry >= sl or entry <= tp)
            ):
                continue

            risk_dist = abs(entry - sl)
            if risk_dist <= 0:
                continue

            # De-risk saat drawdown dalam (TRADING_PLAN §3.3).
            effective_equity = equity
            if peak_equity > 0 and equity < peak_equity * (1 - cfg.drawdown_derisk_pct / 100):
                effective_equity = equity * cfg.drawdown_derisk_factor

            lot, risk_usd = self._size(effective_equity, risk_dist)
            if lot <= 0:
                self.skipped_undersized += 1
                continue

            pos = _Position(
                side=int(side),
                entry=entry,
                sl=float(sl),
                tp=float(tp),
                risk_dist=risk_dist,
                lot=lot,
                open_lot=lot,
                risk_usd=risk_usd,
                entry_time=df.index[i],
                entry_index=i,
                strategy=getattr(self.strategy, "name", "unknown"),
                session=str(sessions[i]),
                inv_level=float(sig_inv[i - 1]),
            )

        # Posisi yang masih terbuka di akhir data ditutup di harga terakhir.
        if pos is not None:
            equity += self._close(pos, closes[-1], pos.open_lot, "end_of_data")
            self._record(
                pos, df.index[-1], closes[-1], n - 1 - pos.entry_index, "end_of_data", equity
            )
            equity_points[-1] = equity

        self.equity_curve = pd.Series(equity_points, index=df.index, name="equity")
        return self

    def trades_frame(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame(
                columns=[f.name for f in Trade.__dataclass_fields__.values()]
            )
        return pd.DataFrame([t.__dict__ for t in self.trades])
