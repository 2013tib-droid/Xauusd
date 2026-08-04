# Briefing pra-entry

Backtester (`xauusd.run`) menjawab *"strategi ini layak dipakai?"*.
Briefing (`xauusd.now`) menjawab pertanyaan yang berbeda: *"sekarang ada setup yang sah?"*

Ia **tidak** menaruh order, tidak terhubung ke broker, dan tidak menebak arah pasar.
Yang dilakukannya: mengumpulkan hal-hal yang seharusnya kamu cek manual sebelum entry —
bias H4/H1, level kunci, checklist tiga strategi, ukuran lot, window blackout, konteks
makro — lalu menaruhnya di satu halaman supaya tidak ada yang terlewat karena buru-buru.

## Cara pakai

```bash
python3 -m xauusd.now \
    --data data/XAUUSD_M15.csv --source-tz Etc/GMT-3 \
    --macro DXY=99.30:-0.25 --macro US10Y=4.12:1.8 --macro US20Y=4.61:1.4 \
    --news data/news.json --equity 1000 --out briefing.html --open
```

Lebih gampang: buka sesi Claude di repo ini dan ketik **`/brief`** — skill-nya akan
menanyakan yang perlu, mencarikan berita terkini, menjalankan perintah di atas, dan
menampilkan hasilnya.

## Argumen yang penting

| Argumen | Isi |
|---|---|
| `--data` | CSV M15 terbaru dari MT5. Export ulang tiap kali — lihat [DATA.md](DATA.md) |
| `--source-tz` | zona waktu server broker, mis. `Etc/GMT-3`. Salah isi = semua filter sesi meleset |
| `--macro` | boleh diulang. Format `SIMBOL=harga:perubahan_persen` |
| `--news` | berkas JSON kalender + judul berita (format di bawah) |
| `--equity`, `--risk` | untuk menghitung lot. Default $1.000 dan 1% |
| `--out`, `--json` | halaman HTML, dan opsional briefing mentah sebagai JSON |
| `--open` | langsung buka di browser |

## Angka makro diisi manual — kenapa

Skrip ini sengaja tidak mengambil DXY dan yield dari internet. Alasannya:

1. Untuk konfirmasi arah, yang dibutuhkan cuma **naik/turun dan seberapa kencang**.
   Presisi empat desimal tidak mengubah keputusan apa pun.
2. Sumber data gratis sering berbeda dari chart yang kamu lihat, dan perbedaan diam-diam
   lebih berbahaya daripada mengetik angka sendiri.
3. Mengetik angkanya memaksamu **melihat** chart-nya. Itu bukan kerugian.

Simbol yang dikenal: `DXY`, `US02Y`, `US10Y`, `US20Y`, `US30Y`, `DE10Y`, `USDJPY`,
`SPX`, `VIX`. Simbol lain tetap diterima dan diperlakukan berkorelasi terbalik dengan gold.

## Cara skor makro dihitung

Tiap instrumen dinilai dari perubahan hariannya, memakai ambang yang berbeda per jenis —
DXY bergerak 0,3% itu besar, yield 2% masih rutin:

| Jenis | Datar (0) | Sedang (1) | Kuat (2) |
|---|---|---|---|
| Dollar (DXY, USDJPY) | < 0,15% | 0,15–0,40% | > 0,40% |
| Yield (US10Y, US20Y, …) | < 0,80% | 0,80–2,00% | > 2,00% |
| Lainnya | < 0,30% | 0,30–1,00% | > 1,00% |

Nilainya diberi tanda sesuai arah, lalu **dibalik** untuk instrumen yang berkorelasi
terbalik dengan gold. Jumlah seluruhnya = skor makro. Positif berarti konteks mendukung
buy, negatif mendukung sell.

Kalau skor melawan arah setup dan besarnya ≥ 2, briefing memunculkan peringatan.
**Peringatan itu tidak membatalkan setup** — korelasi gold dengan dollar dan yield itu
nyata tapi berubah-ubah menurut rezim, dan sering putus total saat ada arus safe-haven.
Anggap ia alasan untuk menuntut checklist yang benar-benar bersih, bukan veto.

Semua ambang di atas ada di `xauusd/macro.py` dan boleh kamu ubah kalau tidak setuju.

## Format berkas berita

```json
{
  "calendar": [
    {"when_utc": "2026-08-12 12:30", "event": "US CPI (data Juli)", "impact": "high"},
    {"when_utc": "2026-09-16 18:00", "event": "FOMC + SEP", "impact": "high",
     "before_min": 30, "after_min": 60}
  ],
  "headlines": [
    {"title": "Gold holds near $4,000 as traders await CPI",
     "source": "Reuters", "time": "2 jam lalu", "url": "https://..."}
  ]
}
```

`when_utc` **harus UTC** — bukan WIB, bukan waktu server broker. Window blackout default
15 menit sebelum dan sesudah (TRADING_PLAN §7); `before_min`/`after_min` menimpanya untuk
event yang butuh window lebih lebar seperti FOMC.

Judul berita ditampilkan apa adanya. Alat ini tidak menyimpulkan bullish/bearish dari
berita, dan itu disengaja: menerjemahkan headline jadi arah adalah bagian yang paling
sering salah.

## Yang dijamin dan yang tidak

Dijamin — dikunci oleh `tests/test_brief.py`:

- Sinyal hanya dievaluasi pada bar M15 yang **sudah close**. Bar berjalan dibuang.
- Ukuran lot dihitung fungsi yang sama persis dengan backtester (`engine.size_position`),
  jadi angka yang kamu lihat sebelum entry = angka yang diuji.
- Setup dengan RR di bawah 1,5 tidak akan pernah muncul.
- Setup yang lot-nya di bawah minimum broker tetap ditampilkan, tapi ditandai tidak
  terjangkau — bukan disembunyikan.
- Judul berita dari luar di-escape; URL non-`http(s)` tidak dijadikan tautan.

Tidak dijamin:

- **Bahwa setup-nya akan profit.** Briefing memotret kondisi, bukan meramal.
- **Bahwa tidak ada setup berarti pasar akan diam.** Artinya cuma: tidak ada yang lolos
  checklist rulebook-mu.
- **Bahwa korelasi makro akan bertahan.** Ia berubah menurut rezim.
- **Bahwa berita yang ditampilkan lengkap.** Selalu ada rilis yang tidak terjaring.

Halaman ini tidak menggantikan checklist di TRADING_PLAN §5. Kalau checklist gagal,
setup tidak sah — walaupun briefing menampilkannya.
