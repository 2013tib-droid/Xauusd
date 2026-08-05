"""Konteks makro: DXY, yield US, dan instrumen lain yang menggerakkan gold.

Modul ini sengaja **tidak** mengambil data sendiri dari internet. Angkanya kamu
isi manual dari TradingView saat menjalankan briefing — untuk keperluan
konfirmasi arah, yang dibutuhkan cuma "naik atau turun, seberapa kencang",
bukan harga presisi empat desimal.

Yang dikerjakan di sini: menerjemahkan pergerakan harian tiap instrumen menjadi
implikasi terhadap gold, lalu menjumlahkannya menjadi satu bias makro yang
bisa dibaca. Semua bobot dan ambangnya terbuka di kode ini — tidak ada kotak
hitam, dan kamu bisa membantahnya.
"""

from __future__ import annotations

from dataclasses import dataclass

# Ambang perubahan harian (persen) yang memisahkan "datar / sedang / kuat".
# Angkanya beda per jenis instrumen karena skala volatilitas hariannya beda:
# DXY bergerak 0,3% itu sudah besar, sedangkan yield 2% masih rutin.
THRESHOLDS = {
    "dollar": (0.15, 0.40),
    "yield": (0.80, 2.00),
    "generic": (0.30, 1.00),
}

# Instrumen yang dikenal, beserta arah hubungannya dengan gold.
# inverse=True berarti: instrumen naik → tekanan turun untuk gold.
KNOWN = {
    "DXY": ("dollar", True, "Indeks dollar"),
    "US10Y": ("yield", True, "Yield US 10 tahun"),
    "US20Y": ("yield", True, "Yield US 20 tahun"),
    "US02Y": ("yield", True, "Yield US 2 tahun"),
    "US30Y": ("yield", True, "Yield US 30 tahun"),
    "DE10Y": ("yield", True, "Yield Bund 10 tahun"),
    "SPX": ("generic", False, "S&P 500 (risk-on/off, hubungan longgar)"),
    "VIX": ("generic", False, "VIX (risk-off → gold sering menguat)"),
    "USDJPY": ("dollar", True, "USD/JPY"),
}

_LABELS = {2: "kuat", 1: "sedang", 0: "datar"}


@dataclass
class MacroReading:
    """Satu pembacaan instrumen makro pada saat briefing dibuat."""

    symbol: str
    last: float
    change_pct: float
    kind: str = "generic"
    inverse: bool = True
    label: str = ""

    @property
    def magnitude(self) -> int:
        """0 = datar, 1 = sedang, 2 = kuat."""
        soft, hard = THRESHOLDS.get(self.kind, THRESHOLDS["generic"])
        move = abs(self.change_pct)
        if move < soft:
            return 0
        return 1 if move < hard else 2

    @property
    def gold_score(self) -> int:
        """Kontribusi ke bias gold: negatif = menekan gold, positif = mendukung."""
        if self.magnitude == 0:
            return 0
        direction = 1 if self.change_pct > 0 else -1
        if self.inverse:
            direction = -direction
        return direction * self.magnitude

    @property
    def reading(self) -> str:
        if self.magnitude == 0:
            return f"{self.symbol} nyaris datar ({self.change_pct:+.2f}%) — tidak memberi arah"
        arah = "naik" if self.change_pct > 0 else "turun"
        efek = "mendukung gold" if self.gold_score > 0 else "menekan gold"
        return (
            f"{self.symbol} {arah} {_LABELS[self.magnitude]} ({self.change_pct:+.2f}%) "
            f"— {efek}"
        )


def parse_macro(spec: str) -> MacroReading:
    """Baca satu argumen CLI berbentuk `SIMBOL=harga:perubahan_persen`.

    Contoh: `DXY=99.30:-0.25`, `US10Y=4.12:1.8`
    """
    try:
        symbol, rest = spec.split("=", 1)
        last_s, change_s = rest.split(":", 1)
        symbol = symbol.strip().upper()
        last = float(last_s)
        change = float(change_s)
    except ValueError as exc:
        raise ValueError(
            f"Format makro tidak dikenal: {spec!r}. "
            "Pakai SIMBOL=harga:perubahan_persen, mis. DXY=99.30:-0.25"
        ) from exc

    kind, inverse, label = KNOWN.get(symbol, ("generic", True, symbol))
    return MacroReading(
        symbol=symbol, last=last, change_pct=change, kind=kind, inverse=inverse, label=label
    )


@dataclass
class MacroBias:
    score: int
    side: int  # +1 mendukung buy, -1 mendukung sell, 0 tidak memberi arah
    label: str
    readings: list[MacroReading]

    @property
    def strength(self) -> str:
        s = abs(self.score)
        if s == 0:
            return "netral"
        if s <= 2:
            return "lemah"
        return "kuat" if s >= 4 else "sedang"


def assess(readings: list[MacroReading]) -> MacroBias:
    """Gabungkan pembacaan instrumen menjadi satu bias makro untuk gold."""
    if not readings:
        return MacroBias(0, 0, "tidak ada data makro yang diisi", [])

    score = sum(r.gold_score for r in readings)
    side = 0 if score == 0 else (1 if score > 0 else -1)

    if side == 0:
        label = "makro tidak memberi arah — instrumen saling meniadakan atau datar"
    else:
        arah = "mendukung BUY" if side > 0 else "mendukung SELL"
        label = f"makro {arah}"

    bias = MacroBias(score=score, side=side, label=label, readings=readings)
    return bias


def conflicts(macro: MacroBias, setup_side: int) -> bool:
    """True kalau makro bergerak melawan arah setup, dan cukup kuat untuk dihiraukan.

    Bias makro yang lemah (|score| <= 1) tidak dihitung sebagai konflik — terlalu
    banyak noise harian yang akan membatalkan setup yang sebenarnya sah.
    """
    if setup_side == 0 or macro.side == 0:
        return False
    return macro.side != setup_side and abs(macro.score) >= 2
