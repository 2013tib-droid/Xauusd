---
name: brief
description: Susun briefing pra-entry XAUUSD M15 — kondisi teknikal dari data M15 terbaru, konteks makro (DXY/yield), kalender blackout, dan judul berita terkini, dirender jadi satu halaman HTML. Pakai saat user minta "cek XAUUSD sekarang", "ada setup nggak", "briefing", "boleh entry nggak", atau memanggil /brief. Bukan untuk backtest — itu tugas `python -m xauusd.run`.
---

# Briefing pra-entry XAUUSD M15

Tujuanmu: menjawab **"menurut rulebook, ada setup yang sah sekarang atau tidak?"** —
lalu menyerahkan keputusan ke user. Kamu menyusun konteks; user yang menekan tombol.

Rulebook-nya `docs/TRADING_PLAN.md`. Kamu tidak boleh mengarang aturan baru,
melonggarkan checklist, atau menyarankan entry yang tidak lolos §5.

## Langkah

### 1. Kumpulkan input

Yang dibutuhkan, tanyakan sekaligus dalam satu pesan (jangan satu per satu):

- **CSV M15 terbaru** — path-nya. Kalau user tidak punya yang baru, minta export ulang
  dari MT5 (`Tools → Quotes/Bars`, lihat `docs/DATA.md`). Data basi = briefing basi.
- **Zona waktu server broker** — mis. `Etc/GMT-3`. Kalau sudah pernah disebut di sesi
  ini atau tercatat di `docs/DATA.md`, pakai itu, jangan tanya ulang.
- **Angka makro dari TradingView** — DXY, US10Y, US20Y: harga terakhir + perubahan
  harian dalam persen. Minta apa adanya, mis. "DXY 99.30 turun 0,25%".
- **Equity akun**, kalau berubah dari sebelumnya. Default $1.000, risiko 1%.

Kalau user tidak mengisi bagian makro, tetap lanjut — briefing tetap sah, blok
makronya saja yang kosong. Jangan mengarang angka DXY atau yield. **Tidak pernah.**

### 2. Cari berita — judul saja

Pakai WebSearch untuk:
- headline terkini soal gold / Fed / dollar / yield (cari yang beberapa jam terakhir)
- event high-impact yang akan rilis hari ini dan besok (CPI, NFP, FOMC, pidato Fed)

Susun jadi `news.json`:

```json
{
  "calendar": [
    {"when_utc": "2026-08-12 12:30", "event": "US CPI (data Juli)", "impact": "high"},
    {"when_utc": "2026-09-16 18:00", "event": "FOMC + SEP", "impact": "high",
     "before_min": 30, "after_min": 60}
  ],
  "headlines": [
    {"title": "...", "source": "Reuters", "time": "2 jam lalu", "url": "https://..."}
  ]
}
```

`when_utc` **harus UTC** — konversi dulu kalau sumbernya menyebut WIB atau ET.
FOMC pakai window 30/60 sesuai §7; event lain biarkan default 15/15.

**Batas keras: jangan menyimpulkan arah dari berita.** Tampilkan judulnya, biarkan
user yang menilai. Kalau kamu tergoda menulis "sentimen bullish" — jangan. Itu bagian
yang paling sering salah, dan user sudah memilih untuk tidak memakainya.

### 3. Jalankan

```bash
python3 -m xauusd.now \
    --data <csv> --source-tz <tz> \
    --macro DXY=99.30:-0.25 --macro US10Y=4.12:1.8 --macro US20Y=4.61:1.4 \
    --news news.json --equity 1000 --out briefing.html
```

Format makro: `SIMBOL=harga:perubahan_persen`. Turun = negatif.

### 4. Sampaikan

Kirim `briefing.html` ke user dengan SendUserFile (`display: "render"`), lalu
ringkas dalam **maksimal 4 kalimat**: ada setup atau tidak, arah dan levelnya,
dan peringatan paling penting kalau ada.

Jangan mengulang seluruh isi halaman dalam bentuk teks — halamannya sudah ada.

## Yang tidak boleh

- **Jangan menyarankan entry saat blackout aktif.** §7 bilang flat, titik.
- **Jangan bilang "ada setup" kalau `--strategy` tidak mengeluarkan sinyal.** Tidak
  ada setup adalah jawaban yang sah dan paling sering benar. Sampaikan apa adanya.
- **Jangan menutupi lot yang di bawah minimum.** Kalau setup tak terjangkau modal,
  itu fakta penting (§3.2), bukan detail yang disembunyikan.
- **Jangan pakai bar M15 yang belum close.** CLI sudah membuangnya otomatis; jangan
  pakai `--keep-forming-bar` kecuali user memintanya eksplisit.
- **Jangan menaikkan risiko** di atas yang ada di rulebook karena "setup-nya bagus".

## Kalau user minta dijadwalkan

Briefing butuh CSV yang baru di-export, jadi penjadwalan otomatis hanya masuk akal
kalau user punya cara meng-export CSV otomatis. Kalau tidak, katakan terus terang —
jadwal yang membaca data basi lebih berbahaya daripada tidak ada jadwal sama sekali.
