# XAUUSD M15 — Trading Plan & Backtester

Perangkat kerja untuk trading gold di timeframe 15 menit: sebuah **rulebook yang mengikat**
dan sebuah **backtester** untuk membuktikan (atau menggugurkan) aturan-aturan itu sebelum
uang sungguhan dipertaruhkan.

Disusun untuk akun kecil (< $1.000), risiko 1% per trade, sesi Asia/London/NY.

## Isi

| Berkas | Isi |
|---|---|
| **[docs/TRADING_PLAN.md](docs/TRADING_PLAN.md)** | Rulebook lengkap: risk management, sesi, 3 strategi, kalender berita, aturan review. **Baca ini dulu.** |
| [docs/MACRO_FED_WARSH.md](docs/MACRO_FED_WARSH.md) | Konteks makro era Fed Warsh: forward guidance dipangkas, real yield naik, dan kenapa disiplin blackout berita jadi mengikat |
| [docs/DATA.md](docs/DATA.md) | Cara export data M15 dari MT5, dan jebakan zona waktu server |
| [journal/template.csv](journal/template.csv) | Template jurnal trading |
| `xauusd/` | Backtester |
| `tests/` | 19 uji yang mengunci matematika sizing dan asumsi eksekusi engine |

## Mulai

```bash
pip install -r requirements.txt

# 1. Cek engine berjalan (data sintetis — TIDAK punya nilai prediktif)
python3 -m xauusd.run --synthetic --strategy all

# 2. Backtest sungguhan dengan data brokermu (lihat docs/DATA.md)
python3 -m xauusd.run --data data/XAUUSD_M15.csv --source-tz Etc/GMT-3 --strategy all

# 3. Satu strategi, sesi tertentu, hasil diekspor
python3 -m xauusd.run --data data/XAUUSD_M15.csv --source-tz Etc/GMT-3 \
    --strategy smc --sessions asia,london --export hasil_smc.csv

python3 -m pytest tests/ -q
```

Opsi lain: `--equity`, `--risk`, `--spread`, `--commission`, `--min-lot`,
`--undersized {skip,min}`, `--no-partial`, `--no-trail`. Lihat `--help`.

## Tiga strategi

| Kode | Nama | Sesi | Ide inti |
|---|---|---|---|
| `breakout` | Breakout / Momentum | London & NY open | Konsolidasi sempit pecah dengan ekspansi range dan body kuat |
| `trend` | Trend Following | London, NY | H4+H1 searah, masuk di pullback ke pita EMA20–50 dengan candle rejeksi |
| `smc` | Smart Money / Liquidity | semua sesi | Sweep likuiditas → market structure shift → FVG |

Setiap strategi diberi SL struktural, TP dengan RR minimum 1,5, dan aturan invalidasi
sendiri. Detail lengkapnya di TRADING_PLAN §5.

## Cara engine ini menghitung (asumsi yang membuatnya konservatif)

- Sinyal dikonfirmasi di **close** bar, dieksekusi di **open bar berikutnya**.
  Tidak ada entry di tengah candle.
- Kalau satu bar menyentuh **SL dan TP sekaligus, SL yang dianggap kena.**
  Data M15 tidak memberi tahu mana yang lebih dulu.
- Spread dibebankan penuh saat entry; komisi per lot round-turn.
- Satu posisi pada satu waktu, sesuai rulebook.
- Manajemen posisi: partial 50% di +1R, SL ke break even, trailing 2×ATR mulai +2R,
  time stop 12 bar.
- Rem risiko aktif: batas rugi harian −2R, mingguan −4R, dan risiko dipotong setengah
  saat drawdown > 10%.
- Bias H4/H1 di-resample dengan pergeseran satu periode, jadi **tidak ada lookahead**
  (dikunci oleh `test_htf_bias_does_not_leak_future_information`).

Hasil live akan **sedikit lebih buruk** dari backtest: slippage, spread mengambang,
dan requote tidak dimodelkan. Baca "Batasan" di [docs/DATA.md](docs/DATA.md).

## Dua kenyataan yang akan kamu temui di output

Backtester akan memperingatkanmu soal ini, dan keduanya berasal dari batas lot minimum
0.01 — bukan dari kesalahan strategi:

1. **Sebagian setup dilewati** karena lot hasil perhitungan lebih kecil dari 0.01.
   Dengan akun $1.000, stop loss $15 (yang normal untuk gold M15) menuntut 0.0067 lot.
2. **Partial close di +1R sering tidak bisa dieksekusi**, karena separuh dari 0.01 lot
   tidak ada. Konsekuensinya, hasil terbaik dari trade yang berbalik adalah 0R, bukan +0,5R.

Keduanya dibahas tuntas — beserta jalan keluarnya — di **TRADING_PLAN §3.2 dan §3.3**.

## Urutan sebelum uang sungguhan

Jangan lompati satu pun (TRADING_PLAN §8):

1. **Backtest** — profit factor ≥ 1,3 · max drawdown ≤ 15% · expectancy ≥ 0,15R · ≥ 100 trade
2. **Forward test demo** — 30 trade, kepatuhan checklist ≥ 90%
3. **Live risiko 0,25%** — 30 trade
4. Baru naik ke risiko penuh

Backtester mencetak verdikt LOLOS/BELUM LOLOS untuk kriteria tahap 1 secara otomatis.

---

Perangkat ini tidak menjamin profit. Ia hanya memastikan kamu tahu **kapan sebuah
strategi tidak layak dipakai** — dan itu justru bagian yang paling menyelamatkan akun.
