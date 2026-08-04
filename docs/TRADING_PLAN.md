# Trading Plan XAUUSD — Timeframe M15

> Dokumen ini adalah **aturan yang mengikat**, bukan saran. Kalau sebuah setup tidak
> memenuhi seluruh checklist di bawah, setup itu tidak ada. Tidak ada "kayaknya".
>
> Versi 1.0 — disusun 3 Agustus 2026.

---

## 0. Ringkasan satu halaman

| Item | Ketetapan |
|---|---|
| Instrumen | XAUUSD saja |
| Timeframe entry | M15 |
| Timeframe bias | H4 (arah) → H1 (struktur) → M15 (eksekusi) |
| Modal | < $1.000 |
| Risiko per trade | **1% dari equity** (lihat §3 untuk batasan lot minimum) |
| Max loss harian | **2 kali stop loss (−2R)** → berhenti trading hari itu |
| Max loss mingguan | **−4R** → berhenti sampai Senin berikutnya |
| Max posisi bersamaan | **1** |
| Target RR minimum | **1 : 1,5** (di bawah itu, skip) |
| Strategi aktif | A. Breakout/Momentum · B. Trend Following · C. Smart Money (SMC) |
| Sesi | Asia, London, New York (lihat §2) |
| Blackout berita | 15 menit sebelum s/d 15 menit sesudah rilis high-impact |

---

## 1. Konteks pasar saat plan ini dibuat

Ini bukan hiasan — konteks menentukan strategi mana yang aku prioritaskan.

- Gold ~**$4.070**, turun ~28% dari rekor Januari 2026 ($5.598), tapi masih +21% YoY.
- **6 minggu konsolidasi menyempit** di area low tahunan. Range sempit = fakeout sering.
- Fed *hold* di 3,50–3,75% — tapi dengan **3 dissent** (Hammack, Kashkari, Logan)
  yang minta naik 25 bps. Keputusan berikutnya benar-benar terbuka.
- Ketua Fed Warsh memangkas forward guidance secara **sengaja** → **pasar hiper-reaktif
  terhadap data**. Yield nominal dan riil naik tajam; emas kena beban jangka pendek dan
  reaksinya kini padat di menit-menit pertama tiap rilis.
  Detail lengkap: **[MACRO_FED_WARSH.md](MACRO_FED_WARSH.md)**.
- Bank sentral masih akumulasi; ETF outflow berat. Dua gaya ini saling mengunci → range.

**Implikasi operasional:**
1. Dalam regime range-bound seperti ini, **Strategi A (breakout) punya rasio fakeout tertinggi.**
   Karena itu breakout wajib pakai filter konfirmasi (§5.A) — tanpa itu, jangan dipakai.
2. Volatilitas event-driven tinggi → **disiplin blackout berita (§7) bukan opsional.**
3. Pidato Ketua Fed diperlakukan **setara rilis data**, bukan event kelas bawah — tanpa
   guidance, tiap kalimatnya adalah informasi baru.
4. Begitu range 6 minggu ini pecah dengan volume, prioritas bergeser ke Strategi B (trend following).

Regime ini harus **direview ulang tiap awal bulan.** Plan yang tidak di-review adalah plan basi.

---

## 2. Sesi & jam trading (WIB, UTC+7)

| Sesi | Jam WIB | Karakter gold | Strategi yang boleh dipakai |
|---|---|---|---|
| **Asia** | 07:00–12:00 | Range sempit, likuiditas tipis, sering choppy | C (SMC, sweep Asia low/high). **A dan B dilarang.** |
| **London** | 14:00–18:00 | Volatilitas naik tajam, tren bersih, breakout Asia-range sering jalan | A, B, C |
| **NY / overlap** | 19:30–23:00 | Likuiditas terbesar, semua data US rilis di sini | A, B, C — tapi patuh blackout berita |

**Zona terlarang:**
- 12:00–14:00 WIB (lunch lull London pre-open) — spread lebar, arah palsu.
- 23:00–07:00 WIB — likuiditas kering, spread melebar 2–3×, gap rollover.
- Jumat setelah 21:00 WIB — jangan buka posisi baru, risiko gap weekend.
- Senin sebelum 12:00 WIB — tunggu gap terisi/terkonfirmasi.

Kamu memantau ketiga sesi. Itu ~11 jam sehari — **tidak realistis dilakukan tiap hari.**
Aturannya: pilih **maksimal 2 sesi per hari**, tetapkan di jurnal sebelum hari dimulai.
Trading karena "kebetulan lagi buka HP" adalah cara paling umum akun kecil habis.

---

## 3. Risk management — bagian paling penting

### 3.1 Rumus lot

Untuk XAUUSD: **1,00 lot = 100 oz**, jadi pergerakan $1,00 = $100 per lot.

```
Lot = Risiko_USD / (SL_dalam_dollar × 100)
```

Contoh: equity $1.000, risk 1% = $10. SL $5,00 (500 points).
`Lot = 10 / (5 × 100) = 0.02 lot` ✓

### 3.2 Peringatan keras soal modal kecil

ATR M15 gold di harga ~$4.000 biasanya **$8–14**. Stop loss wajar (1,5 × ATR) = **$12–21**.

| SL ($) | Lot untuk risk $10 | Bisa dieksekusi? (min 0.01 lot) | Risiko riil di 0.01 lot |
|---|---|---|---|
| $5 | 0.02 | ✅ | $5 (0,5%) |
| $10 | 0.01 | ✅ pas di batas | $10 (1,0%) |
| $15 | 0.0067 | ❌ **di bawah min lot** | $15 = **1,5%** |
| $20 | 0.005 | ❌ | $20 = **2,0%** |

**Kesimpulan jujur: dengan akun $1.000 dan min lot 0.01, kamu TIDAK BISA menjaga
risiko 1% pada stop loss yang wajar untuk gold M15.** Setiap trade akan otomatis
berisiko 1,5–2%. Ini masalah matematis, bukan masalah disiplin.

Tiga jalan keluar yang sah — pilih satu:

1. **Cent account** (1 lot = 100 cent-oz). Ini yang paling aku sarankan untuk modal
   di bawah $1.000. Granularitas risiko jadi 100× lebih halus, aturan 1% bisa ditegakkan.
2. **Broker dengan micro lot 0.001.** Beberapa broker ECN menyediakan. Cek dulu.
3. **Naikkan modal ke ~$2.000** sebelum pakai risk 1% dengan SL $15–20.

Yang **tidak** boleh: memaksa SL sempit ($3–5) supaya lot-nya "muat". SL sempit di gold
M15 = kena noise, bukan kena analisis salah. Itu cara tercepat kehabisan akun.

### 3.3 Konsekuensi kedua dari min lot: partial close jadi mustahil

Kalau posisimu 0.01 lot, **"tutup 50% di +1R" tidak bisa dieksekusi** — separuh dari
0.01 lot adalah 0.005, dan lot itu tidak ada. Ini bukan soal disiplin, ini soal
broker tidak menerima order sekecil itu.

Akibatnya, di 0.01 lot skenario terbaik untuk trade yang berbalik setelah +1R adalah
**0R (break even), bukan +0,5R.** Seluruh keunggulan dari partial profit hilang.
Aturan §3.5 tentang partial baru benar-benar berlaku mulai **0.02 lot ke atas**.

Ini alasan tambahan kenapa cent account adalah pilihan yang tepat untuk modalmu:
di cent account, 0.02+ lot mudah dicapai, jadi manajemen posisi bertingkat bisa
benar-benar dijalankan — bukan cuma jadi teori di dokumen ini.

Backtester akan memberi peringatan eksplisit setiap kali hal ini terjadi.

### 3.4 Aturan yang tidak bisa ditawar

- **Tidak ada trade tanpa stop loss.** Titik.
- **Tidak ada averaging down.** Tidak ada martingale. Tidak ada "hedging" untuk
  menyelamatkan posisi rugi.
- **Tidak ada memindahkan SL menjauh dari harga.** Selamanya. SL hanya boleh bergerak
  ke arah profit.
- Setelah **2 loss beruntun** → istirahat minimal 1 jam, review kedua trade di jurnal.
- Setelah **−2R dalam sehari** → tutup platform. Hari itu selesai.
- Setelah **−4R dalam seminggu** → berhenti sampai Senin. Wajib review mingguan.
- Setelah **drawdown −10% dari equity puncak** → turunkan risiko jadi 0,5% sampai
  equity kembali ke puncak lama.

### 3.5 Manajemen posisi (berlaku untuk semua strategi)

| Kondisi | Aksi |
|---|---|
| Harga capai **+1R** | Tutup 50% posisi, geser SL sisanya ke **break even + spread** |
| Harga capai **+2R** | Trailing SL pakai **2 × ATR(14) M15**, atau di bawah swing low M15 terakhir (untuk buy) |
| Harga capai **+3R** | Tutup sisanya, kecuali ada tren H1 jelas → lanjut trailing |
| 12 candle M15 (3 jam) tanpa gerak ke arah TP | **Time stop** — tutup manual apa pun P/L-nya |
| Menjelang blackout berita (§7) | Tutup posisi atau amankan ke break even |

---

## 4. Filter bias — wajib sebelum lihat setup apa pun

Setiap sesi trading dimulai dengan mengisi tiga baris ini di jurnal:

1. **H4:** harga di atas/di bawah EMA 50? Struktur HH-HL (bullish) atau LH-LL (bearish)?
2. **H1:** searah H4 atau sedang pullback? Di mana swing high/low terakhir?
3. **Level kunci hari ini:** high/low kemarin, high/low sesi Asia, round number terdekat
   ($4.050, $4.100, dst), dan level dari kalender (§7).

**Aturan bias:** Kalau H4 dan H1 berlawanan arah → **hanya Strategi C yang boleh dipakai,
dan hanya di level kunci.** Strategi A dan B butuh keselarasan H4+H1.

---

## 5. Tiga strategi

Semua entry di **candle M15 close**, bukan di tengah candle. Eksekusi di open candle berikutnya.

### A. Breakout / Momentum

**Kapan:** London open (14:00–15:30 WIB) dan NY open (19:30–21:00 WIB).
**Ide:** range Asia atau konsolidasi M15 pecah dengan momentum.

Checklist entry (semua harus ✅):
- [ ] Ada range jelas minimal **8 candle M15** (2 jam) dengan tinggi range < **2,0 × ATR(14)**
      — angka ini dikalibrasi dari data: tinggi range 8-bar normalnya 2,0–3,3 × ATR
      (median ~2,6), jadi ambang 2,0 berarti "seperempat paling sempit". Ambang yang
      lebih ketat (mis. 1,2 × ATR) praktis tidak pernah terpenuhi.
- [ ] Candle breakout **close di luar range**, bukan hanya wick
- [ ] Body candle breakout ≥ **60% dari total range candle** (bukan doji/pin)
- [ ] Range candle breakout ≥ **1,2 × ATR(14)** — ini filter fakeout utama
- [ ] Arah breakout **searah bias H1** (§4)
- [ ] Bukan di dalam window blackout berita
- [ ] Jarak ke level kunci terdekat (§4.3) minimal 1,5 × ATR — jangan breakout tepat ke resistance

**SL:** sisi berlawanan dari range, + buffer 0,3 × ATR.
**TP:** 1,5 × jarak SL, lalu ikuti §3.5.
**Invalidasi:** kalau harga balik masuk range dan close di dalam range → **tutup manual**,
jangan tunggu SL. Ini fakeout yang terkonfirmasi.

> ⚠️ Dalam regime range-bound sekarang (§1), strategi ini paling sering gagal.
> Backtest dulu (§8). Kalau profit factor < 1,2, **matikan strategi ini** sampai regime berubah.

### B. Trend Following (pullback EMA)

**Kapan:** London dan NY, saat H4 dan H1 searah.
**Ide:** ikut arah, masuk di pullback, bukan di puncak momentum.

Checklist entry (semua harus ✅):
- [ ] H4 dan H1 searah (§4)
- [ ] M15: EMA 20 di atas EMA 50 (untuk buy) / di bawah (untuk sell)
- [ ] Harga pullback menyentuh zona **EMA 20–EMA 50**
- [ ] Ada **candle rejeksi** di zona itu (pin bar / engulfing searah tren)
- [ ] ADX(14) M15 ≥ **20** — memastikan ada tren, bukan sideways
- [ ] Pullback **tidak melewati** swing low/high terakhir (struktur masih utuh)
- [ ] Bukan di window blackout berita

**SL:** di bawah swing low terakhir (buy) + buffer 0,3 × ATR.
**TP:** swing high sebelumnya, atau minimum 1,5R — ambil yang lebih jauh, selama RR ≥ 1,5.
**Invalidasi:** close M15 di bawah EMA 50 (untuk buy) → tutup manual.

### C. Smart Money / Liquidity (SMC)

**Kapan:** semua sesi. Ini satu-satunya strategi yang boleh dipakai di sesi Asia.
**Ide:** likuiditas di-sweep dulu, baru harga balik arah.

Checklist entry (semua harus ✅):
- [ ] Ada **liquidity pool** jelas: Asia high/low, high/low kemarin, atau equal highs/lows
- [ ] Harga **menyapu** pool itu (wick menembus) lalu **close kembali di sisi asal** — ini sweep
- [ ] Terjadi **Market Structure Shift (MSS)**: close M15 menembus swing point terakhir
      ke arah berlawanan dari sweep
- [ ] Ada **FVG (fair value gap)** atau **order block** yang ditinggalkan oleh leg MSS
- [ ] Entry saat harga **retrace ke FVG/OB** tersebut
- [ ] Bukan di window blackout berita

**SL:** di luar ujung wick sweep + buffer 0,3 × ATR.
**TP:** liquidity pool berlawanan berikutnya. Minimum RR 1,5 — kalau pool terdekat
memberi RR < 1,5, **skip**.
**Invalidasi:** close M15 di luar ujung sweep → struktur gagal, tutup.

---

## 6. Yang secara eksplisit DILARANG

Daftar ini lahir dari cara akun kecil biasanya mati:

- ❌ Trading tanpa mengisi bias H4/H1 lebih dulu
- ❌ Entry di tengah candle M15 yang belum close
- ❌ Menambah posisi ke arah yang rugi
- ❌ Revenge trading setelah loss (aturan §3.4 berlaku otomatis)
- ❌ Menaikkan lot untuk "balikin" kerugian
- ❌ Trading saat sedang marah, ngantuk, atau di bawah tekanan waktu
- ❌ Buka posisi 15 menit sebelum rilis data high-impact
- ❌ Pindah ke timeframe lebih kecil (M5/M1) untuk "membenarkan" entry yang tidak lolos checklist
- ❌ Mengubah aturan plan ini di tengah minggu berjalan

Perubahan plan hanya boleh dilakukan **saat review bulanan**, berdasarkan data jurnal
minimal 30 trade — bukan berdasarkan perasaan setelah satu minggu jelek.

---

## 7. Kalender berita & blackout

**Aturan blackout:** flat (tidak ada posisi terbuka, tidak ada entry baru)
dari **15 menit sebelum** sampai **15 menit sesudah** rilis high-impact.

Event yang wajib dihormati, urut dampaknya ke gold:

| Event | Dampak tipikal | Catatan |
|---|---|---|
| **FOMC rate decision + SEP** | **$30–80** | Blackout diperpanjang: 30 menit sebelum, 60 menit sesudah |
| **US CPI (Core CPI m/m)** | $15–50 | Deviasi ±0,1% saja = gold gerak $20–40 |
| **Non-Farm Payrolls** | $15–50 | Sering ada spike dua arah dalam 5 menit pertama |
| **Pidato Ketua Fed (Warsh)** | $10–40 | **Diperlakukan high-impact.** Tanpa forward guidance, tiap kalimat = informasi baru ([MACRO_FED_WARSH.md](MACRO_FED_WARSH.md)) |
| PPI, Retail Sales, PCE | $10–25 | |
| Jobless Claims (mingguan) | $5–15 | Boleh tetap trading, tapi ketatkan SL |

**Tanggal terdekat yang sudah pasti:**
- **12 Agustus 2026** — US CPI (data Juli)
- **4 September 2026** — NFP (data Agustus)
- **15–16 September 2026** — FOMC + Summary of Economic Projections

Setiap Minggu malam: buka kalender ekonomi, tandai semua event high-impact minggu itu
di jurnal, hitung window blackout-nya dalam WIB.

---

## 8. Validasi sebelum uang sungguhan

Urutannya tidak boleh dilompati:

1. **Backtest** tiap strategi terpisah, minimal **200 trade** atau 12 bulan data M15.
   Pakai `python -m xauusd.run` (lihat README).
   Kriteria lolos: **Profit Factor ≥ 1,3**, **max drawdown ≤ 15%**, **expectancy > 0,15R**.
2. **Forward test di demo** minimal **1 bulan / 30 trade**, dengan jurnal lengkap.
   Kriteria lolos: hasil tidak menyimpang > 30% dari backtest, dan **kepatuhan checklist ≥ 90%**.
3. **Live dengan risiko 0,25%** selama 30 trade.
4. Baru naik ke risiko penuh 1%.

Kalau di tahap mana pun kriteria tidak terpenuhi → **turun satu tahap**, jangan maju.

---

## 9. Jurnal — wajib diisi tiap trade

Minimum yang dicatat (template ada di `journal/template.csv`):

`tanggal · waktu WIB · sesi · strategi · arah · bias H4 · bias H1 · entry · SL · TP ·
lot · risiko $ · hasil R · checklist lolos? (Y/N) · screenshot · catatan emosi`

Kolom **"checklist lolos? (Y/N)"** adalah kolom terpenting di seluruh jurnal.

Metrik yang dinilai tiap akhir minggu — perhatikan urutannya:

1. **Tingkat kepatuhan checklist** (target ≥ 90%)
2. **Expectancy dalam R**
3. **Profit factor**
4. Baru setelah itu: P/L dalam dollar

Trader profesional dinilai dari proses, bukan dari P/L minggu itu. Trade yang lolos
checklist tapi rugi = **trade bagus**. Trade yang melanggar checklist tapi untung =
**trade buruk**, dan harus ditulis sebagai kesalahan di jurnal.

---

## 10. Review

- **Harian** (10 menit): berapa trade, patuh checklist?, satu pelajaran.
- **Mingguan** (30 menit): 4 metrik §9, strategi mana yang jalan, sesi mana yang paling
  produktif, cek regime pasar berubah atau tidak.
- **Bulanan** (60 menit): review §1 (konteks pasar), evaluasi tiap strategi dari data
  ≥ 30 trade, baru boleh mengubah aturan plan. Catat versi dan alasan perubahannya.

---

## Tanda tangan

Aturan di atas berlaku sejak hari plan ini dibaca. Pelanggaran dicatat di jurnal
sebagai pelanggaran, bukan dirasionalisasi.

Versi 1.0 · Review berikutnya: 1 September 2026
