# news/

Brief makro bertanggal yang dihasilkan agen `gold-news`.

Panggil agennya dari Claude Code:

```
> pakai agen gold-news untuk update berita gold minggu ini
```

Tiap brief ditulis sebagai `YYYY-MM-DD-gold.md`. Isinya adalah **konteks**, bukan
sinyal trading — keputusan tetap mengikuti `docs/TRADING_PLAN.md`.

Catatan di `docs/` (misal `MACRO_FED_WARSH.md`) adalah snapshot bertanggal dari
berita lama. Kalau brief yang lebih baru bertentangan dengannya, **brief yang menang** —
catatan lama tidak perlu dibela. Yang mengikat cuma `docs/TRADING_PLAN.md`, dan
perubahan ke sana diputuskan user, bukan oleh brief.
