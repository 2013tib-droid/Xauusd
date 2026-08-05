"""Uji untuk briefing pra-entry (xauusd.brief, xauusd.macro, xauusd.brief_html)."""

from __future__ import annotations

import pandas as pd
import pytest

from xauusd import brief_html
from xauusd.brief import _blackout_status, build, drop_forming_bar
from xauusd.data import synthetic
from xauusd.engine import Backtest, Config, size_position
from xauusd.macro import assess, conflicts, parse_macro
from xauusd.strategies import Breakout


# --------------------------------------------------------------------- makro
def test_parse_macro_reads_symbol_price_and_change():
    r = parse_macro("DXY=99.30:-0.25")
    assert (r.symbol, r.last, r.change_pct) == ("DXY", 99.30, -0.25)
    assert r.inverse is True


def test_parse_macro_rejects_garbage():
    with pytest.raises(ValueError, match="Format makro tidak dikenal"):
        parse_macro("DXY 99.30")


def test_unknown_symbol_falls_back_to_generic_inverse():
    r = parse_macro("XYZ=10:5")
    assert r.kind == "generic" and r.inverse is True


def test_dollar_and_yield_use_different_thresholds():
    """Perubahan 0,5% itu besar untuk DXY tapi biasa saja untuk yield."""
    assert parse_macro("DXY=99:0.5").magnitude == 2
    assert parse_macro("US10Y=4:0.5").magnitude == 0


def test_rising_dollar_pressures_gold():
    assert parse_macro("DXY=99:0.5").gold_score < 0


def test_falling_yield_supports_gold():
    assert parse_macro("US10Y=4:-2.5").gold_score > 0


def test_flat_instrument_contributes_nothing():
    assert parse_macro("DXY=99:0.05").gold_score == 0


def test_opposing_instruments_cancel_out():
    bias = assess([parse_macro("DXY=99:0.5"), parse_macro("US10Y=4:-2.5")])
    assert bias.score == 0 and bias.side == 0


def test_weak_macro_is_not_treated_as_conflict():
    """Noise harian tidak boleh membatalkan setup yang sah."""
    weak = assess([parse_macro("DXY=99:-0.2")])  # skor +1
    assert conflicts(weak, setup_side=-1) is False


def test_strong_opposing_macro_is_a_conflict():
    strong = assess([parse_macro("DXY=99:-0.5"), parse_macro("US10Y=4:-2.5")])
    assert strong.score >= 2
    assert conflicts(strong, setup_side=-1) is True
    assert conflicts(strong, setup_side=1) is False


def test_no_setup_means_no_conflict():
    strong = assess([parse_macro("DXY=99:-0.5")])
    assert conflicts(strong, setup_side=0) is False


# ------------------------------------------------------------------ blackout
CALENDAR = {
    "calendar": [
        {"when_utc": "2026-03-05 13:30", "event": "US CPI"},
        {"when_utc": "2026-03-05 18:00", "event": "FOMC", "before_min": 30, "after_min": 60},
    ]
}


def test_blackout_active_inside_window():
    status = _blackout_status(CALENDAR, pd.Timestamp("2026-03-05 13:20", tz="UTC"))
    assert status["is_blackout"] is True
    assert status["active"][0]["event"] == "US CPI"


def test_blackout_clear_outside_window():
    status = _blackout_status(CALENDAR, pd.Timestamp("2026-03-05 12:00", tz="UTC"))
    assert status["is_blackout"] is False
    assert status["upcoming"][0]["event"] == "US CPI"


def test_custom_window_is_honoured():
    """FOMC pakai 30 menit sebelum, bukan 15 — jadi 17:40 sudah blackout."""
    status = _blackout_status(CALENDAR, pd.Timestamp("2026-03-05 17:40", tz="UTC"))
    assert status["is_blackout"] is True
    assert status["active"][0]["event"] == "FOMC"


def test_blackout_ends_after_window():
    status = _blackout_status(CALENDAR, pd.Timestamp("2026-03-05 13:50", tz="UTC"))
    assert status["is_blackout"] is False


def test_upcoming_events_are_sorted_by_proximity():
    status = _blackout_status(CALENDAR, pd.Timestamp("2026-03-05 10:00", tz="UTC"))
    assert [e["event"] for e in status["upcoming"]] == ["US CPI", "FOMC"]


# --------------------------------------------------------------- bar berjalan
def test_forming_bar_is_dropped():
    df = synthetic(bars=200)
    last = df.index[-1]
    trimmed = drop_forming_bar(df, now=last + pd.Timedelta(minutes=5))
    assert trimmed.index[-1] == df.index[-2]


def test_closed_bar_is_kept():
    df = synthetic(bars=200)
    last = df.index[-1]
    kept = drop_forming_bar(df, now=last + pd.Timedelta(minutes=16))
    assert kept.index[-1] == last


# ------------------------------------------------------------------- sizing
@pytest.mark.parametrize("equity,risk_dist", [(1000, 5.0), (1000, 15.0), (5000, 3.7), (250, 20.0)])
def test_briefing_sizing_matches_backtester(equity, risk_dist):
    """Lot yang kamu lihat sebelum entry harus sama dengan yang diuji backtester."""
    cfg = Config(initial_equity=equity)
    bt = Backtest(synthetic(bars=300), Breakout(), cfg)
    assert bt._size(equity, risk_dist) == size_position(
        equity,
        risk_dist,
        risk_pct=cfg.risk_pct,
        min_lot=cfg.min_lot,
        undersized_policy=cfg.undersized_policy,
    )


def test_undersized_setup_is_flagged_not_hidden():
    """Setup yang tak terjangkau tetap ditampilkan, tapi ditandai tidak tradable."""
    lot, _ = size_position(1000, 15.0, risk_pct=1.0)
    assert lot == 0.0


# -------------------------------------------------------------------- build
def _brief_at(stamp: str, **kwargs):
    df = synthetic(bars=3000, seed=11).loc[:stamp]
    now = pd.Timestamp(stamp, tz="UTC") + pd.Timedelta(minutes=16)
    return build(df, now=now, **kwargs)


def test_build_reports_signal_on_last_closed_bar():
    b = _brief_at("2026-01-09 13:00")
    assert [s.strategy for s in b.setups] == ["breakout"]
    setup = b.setups[0]
    assert setup.side == -1
    assert setup.rr >= 1.5  # TRADING_PLAN §0: di bawah ini setup dibuang
    assert setup.sl > setup.entry_ref > setup.tp  # SELL: SL di atas, TP di bawah


def test_build_without_signal_returns_no_setup():
    assert _brief_at("2026-01-09 09:00").setups == []


def test_offsession_bar_raises_warning():
    b = _brief_at("2026-01-10 03:00")  # Sabtu
    assert any("luar jam sesi" in w for w in b.warnings)


def test_stale_data_raises_warning():
    df = synthetic(bars=500, seed=11)
    b = build(df, now=df.index[-1] + pd.Timedelta(hours=6))
    assert any("berumur" in w for w in b.warnings)


def test_macro_conflict_surfaces_as_warning():
    b = _brief_at(
        "2026-01-09 13:00",
        macro_readings=[parse_macro("DXY=99:-0.5"), parse_macro("US10Y=4:-2.5")],
    )
    assert any("Konteks melawan" in w for w in b.warnings)


def test_aligned_macro_produces_no_conflict_warning():
    b = _brief_at(
        "2026-01-09 13:00",
        macro_readings=[parse_macro("DXY=99:0.5"), parse_macro("US10Y=4:2.5")],
    )
    assert not any("Konteks melawan" in w for w in b.warnings)


def test_blackout_warning_wins_attention():
    b = _brief_at(
        "2026-01-09 13:00",
        news={"calendar": [{"when_utc": "2026-01-09 13:20", "event": "US CPI"}]},
    )
    assert any("BLACKOUT BERITA aktif" in w for w in b.warnings)


def test_key_levels_are_present():
    b = _brief_at("2026-01-09 13:00")
    assert {"swing_high", "swing_low", "round_above", "round_below"} <= set(b.levels)
    assert b.levels["round_below"] <= b.price <= b.levels["round_above"]


def test_brief_serialises_to_json():
    import json

    payload = json.loads(_brief_at("2026-01-09 13:00").to_json())
    assert payload["setups"][0]["strategy"] == "breakout"
    assert payload["bias"]["h4"] in (-1, 0, 1)


# --------------------------------------------------------------------- HTML
def test_html_renders_verdict_and_numbers():
    html = brief_html.render(_brief_at("2026-01-09 13:00"))
    assert "SELL — breakout" in html
    assert "Briefing XAUUSD M15" in html
    assert "<title>" in html


def test_html_says_no_setup_when_there_is_none():
    html = brief_html.render(_brief_at("2026-01-09 09:00"))
    assert "TIDAK ADA SETUP" in html


def test_headline_html_is_escaped():
    """Judul berita datang dari luar — tidak boleh bisa menyuntikkan markup."""
    b = _brief_at(
        "2026-01-09 13:00",
        news={"headlines": [{"title": "<script>alert(1)</script>", "source": "x"}]},
    )
    html = brief_html.render(b)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_headline_url_must_be_http():
    """URL non-http (mis. javascript:) tidak boleh jadi tautan."""
    b = _brief_at(
        "2026-01-09 13:00",
        news={"headlines": [{"title": "klik", "url": "javascript:alert(1)"}]},
    )
    html = brief_html.render(b)
    assert "javascript:alert(1)" not in html
