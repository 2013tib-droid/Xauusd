#!/usr/bin/env bash
# Susun situs statis ke _site/.
#
# Halaman web memuat docs/TRADING_PLAN.md dan docs/DATA.md lewat fetch(), jadi
# keduanya harus berada di sebelah index.html. Menyalinnya di sini — bukan
# menduplikasi berkasnya di repo — membuat dokumen tetap punya satu sumber
# kebenaran: yang dibaca di GitHub sama persis dengan yang dibaca di situs.
#
#   bash web/build.sh && python3 -m http.server -d _site 8000
#
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out="$root/_site"

rm -rf "$out"
mkdir -p "$out"

cp "$root/web/index.html" "$out/"
cp "$root/web/app.css" "$out/"
cp -r "$root/web/js" "$out/"
cp -r "$root/docs" "$out/"

# Fixture uji tidak ikut dipublikasikan: gunanya cuma untuk parity.mjs, dan
# ukurannya lebih besar dari seluruh situs.
echo "Situs siap di $out"
