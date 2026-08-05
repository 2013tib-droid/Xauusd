"""Render objek Brief menjadi satu halaman HTML mandiri.

Halaman ini dibuat untuk dibaca cepat di HP sebelum entry: verdikt di atas,
alasannya di bawah. Tidak ada berkas eksternal — CSS ditanam di dalam, jadi
bisa dibuka offline atau dikirim ke diri sendiri lewat chat.
"""

from __future__ import annotations

from html import escape

from .brief import BIAS_LABEL, Brief

_CSS = """
:root {
  --bg: #f7f7f5; --card: #fff; --ink: #1a1a18; --muted: #6b6b66;
  --line: #e2e2dd; --buy: #0b7a4b; --sell: #b3261e; --warn: #a15c00;
  --warn-bg: #fdf3e2; --stop-bg: #fdeceb;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161614; --card: #1f1e1c; --ink: #ececE7; --muted: #9d9d96;
    --line: #33322e; --buy: #4ade80; --sell: #f87171; --warn: #fbbf24;
    --warn-bg: #2b2314; --stop-bg: #2d1a18;
  }
}
:root[data-theme="dark"] {
  --bg: #161614; --card: #1f1e1c; --ink: #ecece7; --muted: #9d9d96;
  --line: #33322e; --buy: #4ade80; --sell: #f87171; --warn: #fbbf24;
  --warn-bg: #2b2314; --stop-bg: #2d1a18;
}
:root[data-theme="light"] {
  --bg: #f7f7f5; --card: #fff; --ink: #1a1a18; --muted: #6b6b66;
  --line: #e2e2dd; --buy: #0b7a4b; --sell: #b3261e; --warn: #a15c00;
  --warn-bg: #fdf3e2; --stop-bg: #fdeceb;
}
body {
  margin: 0; padding: 20px 16px 56px; background: var(--bg); color: var(--ink);
  font: 15px/1.55 ui-sans-serif, -apple-system, "Segoe UI", system-ui, sans-serif;
}
.wrap { max-width: 780px; margin: 0 auto; }
h1 { font-size: 19px; margin: 0 0 2px; letter-spacing: -0.01em; }
h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .07em;
     color: var(--muted); margin: 28px 0 10px; font-weight: 600; }
.sub { color: var(--muted); font-size: 13px; margin-bottom: 20px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 12px;
        padding: 14px 16px; margin-bottom: 10px; }
.verdict { padding: 18px; border-radius: 12px; margin-bottom: 8px; }
.verdict .big { font-size: 21px; font-weight: 650; letter-spacing: -0.02em; }
.verdict .why { color: var(--muted); font-size: 13px; margin-top: 4px; }
.v-buy { background: var(--card); border: 2px solid var(--buy); }
.v-buy .big { color: var(--buy); }
.v-sell { background: var(--card); border: 2px solid var(--sell); }
.v-sell .big { color: var(--sell); }
.v-none { background: var(--card); border: 1px solid var(--line); }
.v-stop { background: var(--stop-bg); border: 2px solid var(--sell); }
.v-stop .big { color: var(--sell); }
.warn { background: var(--warn-bg); border-left: 3px solid var(--warn);
        border-radius: 6px; padding: 10px 12px; margin-bottom: 8px; font-size: 14px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(132px, 1fr)); gap: 10px; }
.stat .k { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
.stat .v { font-size: 17px; font-weight: 600; font-variant-numeric: tabular-nums; margin-top: 2px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
     color: var(--muted); font-weight: 600; padding: 6px 8px; border-bottom: 1px solid var(--line); }
td { padding: 7px 8px; border-bottom: 1px solid var(--line); font-variant-numeric: tabular-nums; }
tr:last-child td { border-bottom: 0; }
.scroll { overflow-x: auto; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px;
       font-weight: 600; }
.t-buy { background: var(--buy); color: var(--card); }
.t-sell { background: var(--sell); color: var(--card); }
.pos { color: var(--buy); } .neg { color: var(--sell); }
.note { font-size: 13px; color: var(--muted); margin-top: 8px; }
a { color: inherit; }
.foot { margin-top: 36px; padding-top: 14px; border-top: 1px solid var(--line);
        font-size: 12px; color: var(--muted); }
"""


def _fmt(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}"


def _verdict(brief: Brief) -> tuple[str, str, str]:
    """Kembalikan (kelas_css, judul, alasan)."""
    if brief.blackout["is_blackout"]:
        events = ", ".join(e["event"] for e in brief.blackout["active"])
        return "v-stop", "JANGAN ENTRY — BLACKOUT BERITA", f"Window {events} sedang aktif."

    if brief.session == "off":
        return "v-none", "TIDAK ADA SETUP — di luar sesi", "Di luar jam trading TRADING_PLAN §2."

    tradable = [s for s in brief.setups if s.tradable]
    if not brief.setups:
        return (
            "v-none",
            "TIDAK ADA SETUP",
            "Tidak ada strategi yang checklist-nya terpenuhi di bar terakhir. Menunggu.",
        )
    if not tradable:
        return (
            "v-none",
            "ADA SETUP, TAPI TIDAK TERJANGKAU",
            "Lot hasil hitungan di bawah minimum broker — TRADING_PLAN §3.2.",
        )

    first = tradable[0]
    others = f" (+{len(tradable) - 1} strategi lain)" if len(tradable) > 1 else ""
    cls = "v-buy" if first.side > 0 else "v-sell"
    return (
        cls,
        f"{first.side_label} — {first.strategy}{others}",
        f"Entry di open bar berikutnya · RR {first.rr:.2f} · {first.lot:.2f} lot",
    )


def _setup_card(setup, equity: float) -> str:
    tag = "t-buy" if setup.side > 0 else "t-sell"
    notes = "".join(f'<div class="note">{escape(n)}</div>' for n in setup.notes)
    risk_line = (
        f"{_fmt(setup.risk_usd)} USD ({setup.risk_usd / equity * 100:.2f}%)"
        if setup.lot > 0
        else "—"
    )
    return f"""
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
        <strong>{escape(setup.strategy)}</strong>
        <span class="tag {tag}">{setup.side_label}</span>
      </div>
      <div class="grid">
        <div class="stat"><div class="k">Entry (ref)</div><div class="v">{_fmt(setup.entry_ref)}</div></div>
        <div class="stat"><div class="k">Stop loss</div><div class="v">{_fmt(setup.sl)}</div></div>
        <div class="stat"><div class="k">Take profit</div><div class="v">{_fmt(setup.tp)}</div></div>
        <div class="stat"><div class="k">RR</div><div class="v">{setup.rr:.2f}</div></div>
        <div class="stat"><div class="k">Lot</div><div class="v">{setup.lot:.2f}</div></div>
        <div class="stat"><div class="k">Risiko</div><div class="v">{risk_line}</div></div>
      </div>
      {notes}
    </div>"""


def _levels_table(levels: dict) -> str:
    names = {
        "prev_day_high": "High kemarin",
        "prev_day_low": "Low kemarin",
        "asia_high": "High sesi Asia",
        "asia_low": "Low sesi Asia",
        "swing_high": "Swing high terakhir",
        "swing_low": "Swing low terakhir",
        "round_above": "Round number di atas",
        "round_below": "Round number di bawah",
    }
    rows = "".join(
        f"<tr><td>{names.get(k, k)}</td><td>{_fmt(v)}</td></tr>"
        for k, v in levels.items()
        if k in names
    )
    return f'<div class="card scroll"><table>{rows}</table></div>'


def _macro_table(brief: Brief) -> str:
    if not brief.macro.readings:
        return '<div class="card"><em>Tidak ada data makro yang diisi.</em></div>'

    rows = ""
    for r in brief.macro.readings:
        cls = "pos" if r.change_pct > 0 else "neg" if r.change_pct < 0 else ""
        if r.gold_score > 0:
            implikasi = '<span class="pos">mendukung</span>'
        elif r.gold_score < 0:
            implikasi = '<span class="neg">menekan</span>'
        else:
            implikasi = '<span style="color:var(--muted)">datar</span>'
        rows += (
            f"<tr><td><strong>{escape(r.symbol)}</strong></td>"
            f"<td>{_fmt(r.last, 2)}</td>"
            f'<td class="{cls}">{r.change_pct:+.2f}%</td>'
            f"<td>{implikasi}</td></tr>"
        )

    return f"""
    <div class="card scroll">
      <table>
        <tr><th>Simbol</th><th>Harga</th><th>Δ hari</th><th>Efek ke gold</th></tr>
        {rows}
      </table>
    </div>
    <div class="card"><strong>{escape(brief.macro.label)}</strong>
      <span style="color:var(--muted)"> — kekuatan {escape(brief.macro.strength)}
      (skor {brief.macro.score:+d})</span>
      <div class="note">Skor adalah jumlah kontribusi tiap instrumen: arah pergerakan
      dikali besarnya (datar 0, sedang 1, kuat 2), dibalik untuk instrumen yang
      korelasinya terbalik dengan gold. Ini konteks — bukan sinyal entry.</div>
    </div>"""


def _news_block(news: dict, blackout: dict) -> str:
    out = ""

    upcoming = blackout.get("upcoming", [])
    if upcoming:
        rows = "".join(
            f"<tr><td>{escape(e['event'])}</td><td>{escape(e['when_wib'])}</td>"
            f"<td>{escape(e['window'])}</td></tr>"
            for e in upcoming
        )
        out += f"""
        <h2>Kalender — blackout berikutnya</h2>
        <div class="card scroll"><table>
          <tr><th>Event</th><th>Rilis</th><th>Window flat</th></tr>{rows}
        </table></div>"""

    headlines = news.get("headlines", [])
    if headlines:
        items = ""
        for h in headlines:
            title = escape(str(h.get("title", "")))
            source = escape(str(h.get("source", "")))
            when = escape(str(h.get("time", "")))
            url = str(h.get("url", ""))
            link = (
                f'<a href="{escape(url)}">{title}</a>'
                if url.startswith(("http://", "https://"))
                else title
            )
            items += (
                f'<div style="padding:8px 0;border-bottom:1px solid var(--line)">{link}'
                f'<div class="note" style="margin-top:2px">{source} · {when}</div></div>'
            )
        out += f"""
        <h2>Judul berita terkini</h2>
        <div class="card">{items}
          <div class="note">Judul ditampilkan apa adanya, tanpa kesimpulan bullish/bearish.
          Menyimpulkan arah dari berita adalah bagian yang paling sering salah — itu
          tetap tugasmu, bukan tugas alat ini.</div>
        </div>"""

    return out


def render(brief: Brief) -> str:
    cls, title, why = _verdict(brief)

    warnings = "".join(f'<div class="warn">{escape(w)}</div>' for w in brief.warnings)
    setups = "".join(_setup_card(s, brief.equity) for s in brief.setups)
    align = "searah" if brief.aligned else "berlawanan / netral"

    return f"""<title>Briefing XAUUSD M15 — {brief.bar_time_wib:%d %b %Y %H:%M} WIB</title>
<style>{_CSS}</style>
<div class="wrap">
  <h1>Briefing XAUUSD M15</h1>
  <div class="sub">
    Bar terakhir close {brief.bar_time_wib:%d %b %Y %H:%M} WIB
    · sesi <strong>{escape(brief.session)}</strong>
    · harga <strong>{_fmt(brief.price)}</strong>
  </div>

  <div class="verdict {cls}">
    <div class="big">{escape(title)}</div>
    <div class="why">{escape(why)}</div>
  </div>

  {warnings}

  <h2>Bias & indikator</h2>
  <div class="card">
    <div class="grid">
      <div class="stat"><div class="k">Bias H4</div><div class="v">{BIAS_LABEL[brief.bias_h4]}</div></div>
      <div class="stat"><div class="k">Bias H1</div><div class="v">{BIAS_LABEL[brief.bias_h1]}</div></div>
      <div class="stat"><div class="k">Keselarasan</div><div class="v">{align}</div></div>
      <div class="stat"><div class="k">ATR(14)</div><div class="v">{_fmt(brief.atr14)}</div></div>
      <div class="stat"><div class="k">ADX(14)</div><div class="v">{brief.adx14:.1f}</div></div>
      <div class="stat"><div class="k">EMA20 / 50</div><div class="v">{_fmt(brief.ema20)} / {_fmt(brief.ema50)}</div></div>
    </div>
  </div>

  <h2>Setup di bar terakhir</h2>
  {setups or '<div class="card"><em>Tidak ada strategi yang memberi sinyal.</em></div>'}

  <h2>Level kunci</h2>
  {_levels_table(brief.levels)}

  <h2>Konteks makro</h2>
  {_macro_table(brief)}

  {_news_block(brief.news, brief.blackout)}

  <div class="foot">
    Dibuat {brief.generated_at:%d %b %Y %H:%M} UTC · equity ${_fmt(brief.equity, 0)}
    · risiko {brief.risk_pct}%<br>
    Briefing ini memotret kondisi pada bar yang sudah close, bukan ramalan. Ia tidak
    menggantikan checklist di TRADING_PLAN §5 — kalau checklist gagal, setup tidak sah
    walaupun halaman ini menampilkannya.
  </div>
</div>"""
