# Konteks repo untuk Claude

Perangkat trading XAUUSD M15 untuk **akun kecil** (< $1.000, risiko 1%). Isinya tiga hal:
rulebook, backtester, dan briefing pra-entry.

**Tidak ada bot di sini.** Repo ini tidak terhubung ke broker dan tidak pernah menaruh
order. Eksekusi trade dilakukan manual oleh user di MT5. Jangan menawarkan membuat EA
kecuali diminta eksplisit.

## Aturan tertinggi

`docs/TRADING_PLAN.md` adalah rulebook yang mengikat. Kalau ada pertanyaan soal boleh
tidaknya sesuatu, jawabannya ada di sana — jangan mengarang aturan baru, melonggarkan
checklist, atau menaikkan risiko karena "setup-nya bagus".

Beberapa pasal yang paling sering relevan:
- **§3.2** — lot minimum 0.01 sering membuat setup tak terjangkau modal $1.000. Ini fakta
  yang harus disampaikan, bukan disembunyikan.
- **§4** — kalau bias H4 dan H1 berlawanan, hanya strategi `smc` yang boleh dipakai.
- **§5** — entry hanya di candle M15 yang sudah close, RR minimum 1,5.
- **§7** — blackout berita: flat 15 menit sebelum sampai 15 menit sesudah rilis
  high-impact (FOMC 30/60). Tidak ada pengecualian.
- **§8** — urutan validasi: backtest → demo → live 0,25% → risiko penuh. Jangan pernah
  menyarankan melompatinya.

## Dua perintah

```bash
# "Strategi ini layak dipakai?" — menguji ke data masa lalu
python3 -m xauusd.run --data data/XAUUSD_M15.csv --source-tz Etc/GMT-3 --strategy all

# "Sekarang ada setup yang sah?" — memotret kondisi terkini jadi halaman HTML
python3 -m xauusd.now --data data/XAUUSD_M15.csv --source-tz Etc/GMT-3 \
    --macro DXY=99.30:-0.25 --macro US10Y=4.12:1.8 --news data/news.json

python3 -m pytest tests/ -q   # 55 tes
```

Untuk briefing, ikuti skill `/brief` (`.claude/skills/brief/SKILL.md`) — di situ ada
prosedur lengkapnya termasuk cara mencari berita dan membangun `news.json`.

## Yang harus dijaga saat mengubah kode

- **Tidak ada lookahead.** Sinyal dikonfirmasi di close bar, dieksekusi di open bar
  berikutnya. Bias H4/H1 digeser satu periode. Ada tes yang mengunci ini — kalau gagal,
  itu bug serius, bukan tes yang rewel.
- **Satu sumber kebenaran untuk sizing.** `engine.size_position` dipakai backtester dan
  briefing. Jangan menulis ulang matematikanya di tempat lain.
- **Asumsi konservatif dipertahankan.** Kalau satu bar menyentuh SL dan TP sekaligus, SL
  yang dianggap kena. Jangan "memperbaiki" ini jadi lebih optimis.
- **Data pasar tidak di-commit** (lihat `.gitignore`).
- Dokumentasi dan pesan commit ditulis dalam **bahasa Indonesia**, mengikuti gaya yang
  sudah ada.

## Nada

User memakai uang sungguhan di akun kecil. Sampaikan hasil apa adanya — termasuk saat
jawabannya "tidak ada setup", "strategi ini belum lolos", atau "modalmu belum cukup untuk
setup ini". Jangan memoles angka, dan jangan menyimpulkan arah pasar dari berita.
