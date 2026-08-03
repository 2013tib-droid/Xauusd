# Menyiapkan data XAUUSD M15

Backtester ini membaca CSV. Ia **tidak** mengunduh data sendiri — dan itu disengaja:
data gold yang gratis dari internet sering berbeda jauh dari feed broker tempat kamu
benar-benar trading (jam server beda, spread beda, bahkan harga beda beberapa dollar).
Backtest yang jujur harus memakai data dari broker yang akan kamu pakai.

## Cara 1 — Export dari MetaTrader 5 (paling disarankan)

1. Buka MT5 → menu **View → Symbols** (atau `Ctrl+U`).
2. Cari `XAUUSD` di daftar, pilih tab **Bars**.
3. Isi **Request**: periode `M15`, rentang tanggal sepanjang mungkin (minimal 2 tahun).
4. Klik **Request** → **Export Bars** → simpan sebagai CSV di folder `data/`.

Hasilnya berupa file tab-separated dengan kolom seperti ini:

```
<DATE>	<TIME>	<OPEN>	<HIGH>	<LOW>	<CLOSE>	<TICKVOL>	<VOL>	<SPREAD>
2026.01.02	00:00:00	4012.35	4014.80	4011.90	4013.55	842	0	21
```

Loader sudah mengenali format ini apa adanya — tidak perlu diedit.

### ⚠️ Zona waktu server: kesalahan paling mahal di sini

Kolom `<TIME>` memakai **jam server broker**, bukan UTC dan bukan WIB. Kebanyakan
broker forex memakai UTC+2 (musim dingin) / UTC+3 (musim panas).

Kalau kamu salah mengisi zona waktu, **seluruh filter sesi jadi ngawur** — engine akan
mengira sesi London padahal itu sesi Asia, dan hasil backtest-nya tidak berarti apa-apa.

Cara memastikan: di MT5 buka **Market Watch → Tick Chart**, bandingkan jam yang
tertera dengan jam WIB di HP-mu, lalu hitung selisihnya.

| Zona server | Isi `--source-tz` dengan |
|---|---|
| UTC+2 | `Etc/GMT-2` |
| UTC+3 (paling umum) | `Etc/GMT-3` |
| UTC / GMT | `UTC` |

> Perhatikan tandanya terbalik: `Etc/GMT-3` berarti **UTC+3**. Ini konvensi POSIX,
> bukan salah ketik.

Verifikasi cepat setelah export — sesi Asia harus terlihat paling sepi:

```bash
python3 -c "
from xauusd.data import load_csv, add_session
df = add_session(load_csv('data/XAUUSD_M15.csv', source_tz='Etc/GMT-3'))
print((df.high - df.low).groupby(df.session).mean().round(3))
"
```

Yang benar: `london` dan `ny` punya range rata-rata jelas lebih besar daripada `asia`.
Kalau `asia` yang paling besar, zona waktumu salah.

## Cara 2 — CSV dari sumber lain

Loader menerima pemisah koma/titik koma/tab dan mengenali nama kolom yang umum
(`Date`, `Time`, `Datetime`, `Gmt time`, `Open`, `High`, `Low`, `Close`, `Volume`).
Minimum yang dibutuhkan: satu kolom waktu + empat kolom OHLC.

Contoh yang valid:

```csv
Datetime,Open,High,Low,Close,Volume
2026-01-02 00:00:00,4012.35,4014.80,4011.90,4013.55,842
```

## Berapa banyak data yang dibutuhkan?

| Periode | Perkiraan bar M15 | Cukup untuk |
|---|---|---|
| 3 bulan | ~6.000 | uji jalan saja, sampel terlalu kecil untuk kesimpulan |
| 1 tahun | ~25.000 | evaluasi awal Strategi B (trend) |
| 2–3 tahun | ~50.000–75.000 | ambang 100+ trade untuk ketiga strategi |

Strategi A (breakout) dan C (SMC) sangat selektif — sekitar **1 setup per 1–2 minggu**.
Untuk mengumpulkan 100 trade dari keduanya, kamu butuh data **2–3 tahun**. Ini bukan
kelemahan backtester; memang setup berkualitas itu jarang.

Usahakan rentang datanya mencakup lebih dari satu regime pasar (tren naik, tren turun,
dan range). Strategi yang hanya diuji di satu regime akan mengejutkanmu saat regime-nya
berganti.

## Batasan yang harus kamu ketahui

Engine memakai bar M15, jadi ada hal-hal yang **tidak** bisa dimodelkan dengan jujur:

- **Urutan di dalam bar.** Kalau satu bar menyentuh SL dan TP sekaligus, engine
  menganggap SL yang kena. Ini pesimis, dan disengaja.
- **Slippage.** Tidak dimodelkan. Saat rilis berita, slippage gold bisa $1–5 —
  inilah salah satu alasan aturan blackout berita ada.
- **Spread mengambang.** Engine memakai spread tetap. Spread riil melebar tajam saat
  rollover dan saat rilis data. Untuk estimasi konservatif, pakai `--spread 0.40`.
- **Requote dan gap.** Gap akhir pekan muncul di data, tapi eksekusi di tengah gap
  tidak dimodelkan.

Artinya: **hasil live akan sedikit lebih buruk daripada backtest.** Kalau sebuah strategi
hanya menang tipis di backtest, di dunia nyata ia rugi.
