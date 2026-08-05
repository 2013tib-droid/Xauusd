# XAUUSD M15 — Trading Plan, Backtester & Briefing

Perangkat kerja untuk trading gold di timeframe 15 menit: sebuah **rulebook yang mengikat**,
sebuah **backtester** untuk membuktikan (atau menggugurkan) aturan-aturan itu sebelum uang
sungguhan dipertaruhkan, dan sebuah **briefing pra-entry** untuk memeriksa kondisi sekarang.

Tidak ada bot di sini. Tidak ada yang terhubung ke broker; eksekusi tetap di tanganmu.

Disusun untuk akun kecil (< $1.000), risiko 1% per trade, sesi Asia/London/NY.

## → [Buka versi web](https://2013tib-droid.github.io/Xauusd/)

> **Dua setelan yang harus dibuka manual sekali saja** — token Actions tidak punya
> izin mengubah keduanya sendiri:
>
> 1. Settings → Pages → **Source: GitHub Actions**.
> 2. Settings → Environments → `github-pages` → **Deployment branches**: pastikan
>    `main` ada di daftar. Daftar ini dibekukan saat Pages pertama dinyalakan dan
>    tidak ikut berubah ketika branch default diganti — kalau isinya masih nama
>    branch lama, job `deploy` gagal tanpa log sama sekali.
>
> Setelah itu setiap push ke `main` mendeploy situsnya otomatis.

Backtester yang sama, jalan sepenuhnya di browser: taruh CSV M15 dari MT5, pilih
zona waktu server broker, dan ketiga strategi langsung dijalankan — lengkap dengan
kurva equity, bedah performa per sesi, daftar trade, dan verdikt LOLOS/BELUM LOLOS.
Trading plan-nya juga bisa dibaca di sana.

**Datamu tidak diunggah ke mana pun.** Halaman itu tidak punya server; berkas CSV
dibaca dan dihitung di dalam browsermu sendiri.

Versi web dan CLI Python memakai satu perhitungan yang sama, dan itu dikunci oleh
uji paritas: 529 trade dari 9 kombinasi strategi × konfigurasi harus cocok
**field per field** antara kedua implementasi, atau CI menolak deploy.

## Isi

| Berkas | Isi |
|---|---|
| **[docs/TRADING_PLAN.md](docs/TRADING_PLAN.md)** | Rulebook lengkap: risk management, sesi, 3 strategi, kalender berita, aturan review. **Baca ini dulu.** |
| [docs/BRIEFING.md](docs/BRIEFING.md) | Briefing pra-entry: cara pakai, skor makro, format berkas berita |
| [docs/DATA.md](docs/DATA.md) | Cara export data M15 dari MT5, dan jebakan zona waktu server |
| [docs/MACRO_FED_WARSH.md](docs/MACRO_FED_WARSH.md) | Catatan latar era Fed Warsh — snapshot bertanggal, bukan patokan |
| `news/` | Brief makro mingguan hasil agen `gold-news` |
| [journal/template.csv](journal/template.csv) | Template jurnal trading |
| `xauusd/` | Backtester + briefing (Python, CLI) |
| `web/` | Backtester yang sama diport ke JavaScript, plus situsnya |
| `tests/` | 55 uji yang mengunci matematika sizing, asumsi eksekusi engine, dan aturan briefing |
| `web/tests/` | Uji paritas JavaScript ↔ Python |

## Mulai cepat

**Lewat Claude Code** (paling praktis) — buka sesi di folder repo ini, lalu ketik:

| Ketik | Yang terjadi |
|---|---|
| `/brief` | Claude tanya CSV + angka DXY/yield, carikan berita & kalender, lalu tampilkan halaman briefing |
| "backtest semua strategi" | Claude jalankan backtester dan bacakan verdikt LOLOS/BELUM LOLOS |
| "pakai agen gold-news untuk update berita gold minggu ini" | Riset makro mendalam, hasilnya ditulis ke `news/` |

Dua yang pertama untuk dipakai sebelum entry; yang ketiga riset mingguan, jalankan
terpisah. `/brief` sengaja tidak memanggil agen itu — briefing yang menunggu riset
makro selesai kehilangan gunanya, karena bar M15 berikutnya tidak menunggu.

Siapkan sebelum `/brief`: **CSV M15 terbaru** dari MT5 (`Tools → Quotes/Bars`, taruh di
`data/`), **zona waktu server broker** (mis. `Etc/GMT-3`), dan **angka DXY + US10Y +
US20Y** dari TradingView (harga terakhir dan perubahan harian %).

**Lewat terminal** — perintah lengkapnya ada di dua bagian di bawah.

## Dua alat, dua pertanyaan berbeda

| | Pertanyaan yang dijawab | Perintah |
|---|---|---|
| **Backtester** | "Strategi ini layak dipakai?" | `python3 -m xauusd.run` — atau [versi web](https://2013tib-droid.github.io/Xauusd/) |
| **Briefing** | "Sekarang ada setup yang sah?" | `python3 -m xauusd.now` |

Urutannya tidak boleh dibalik: sebuah strategi harus lolos backtest **dulu** sebelum
briefing-nya berarti apa-apa. Briefing yang menampilkan setup dari strategi yang belum
terbukti hanya membuat tebakan terlihat rapi.

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

### Menjalankan versi web secara lokal

```bash
bash web/build.sh
python3 -m http.server -d _site 8000   # lalu buka http://localhost:8000
```

Harus lewat HTTP, bukan `file://` — halamannya memakai modul ES dan `fetch()`
untuk memuat trading plan.

### Menjaga web dan CLI tetap sama

```bash
node web/tests/parity.mjs           # bandingkan hasil JS dengan hasil Python
python3 web/tests/make_fixture.py   # bangkitkan ulang fixture setelah engine Python berubah
```

Kalau kamu mengubah apa pun di `xauusd/`, jalankan `make_fixture.py` lalu commit
hasilnya. CI menolak fixture yang kedaluwarsa, karena tanpa itu web bisa diam-diam
bercerita beda tentang strategi yang sama.

## Briefing sebelum entry

```bash
python3 -m xauusd.now \
    --data data/XAUUSD_M15.csv --source-tz Etc/GMT-3 \
    --macro DXY=99.30:-0.25 --macro US10Y=4.12:1.8 --macro US20Y=4.61:1.4 \
    --news data/news.json --out briefing.html --open
```

Keluar satu halaman HTML: verdikt di atas (ada setup / tidak ada / blackout), lalu
bias H4-H1, level kunci, ukuran lot, konteks makro, dan judul berita terkini.

Angka DXY dan yield diisi manual dari TradingView — alasannya di
[docs/BRIEFING.md](docs/BRIEFING.md). Skrip ini tidak mengambil data sendiri dari internet.

Cara paling praktis: buka sesi Claude Code di repo ini dan ketik **`/brief`**. Skill-nya
akan menanyakan yang perlu, mencarikan berita dan kalender terkini, menjalankan perintah
di atas, lalu menampilkan halamannya.

Yang perlu dipegang: briefing memotret kondisi pada bar M15 yang **sudah close** —
bar yang sedang berjalan dibuang. Ia tidak meramal, dan tidak menggantikan checklist
di TRADING_PLAN §5.

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
