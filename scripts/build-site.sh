#!/usr/bin/env bash
# Rahbar uchun sayt: kodsiz, faqat diagramma, skrinshot va taqdimot.
# Natija dist/site ga tushadi (git'da yo'q).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

OUT=dist/site
rm -rf "$OUT"; mkdir -p "$OUT/assets"

cp site/index.html site/_headers site/robots.txt "$OUT/"
cp docs/diagrams/[1-6]-*.png docs/diagrams/ekran-*.png "$OUT/assets/"
cp docs/OpenEMR-ovozli-yozuv.pptx "$OUT/MedVoice-taqdimot.pptx"
cp docs/diagrams/arxitektura-diagrammalar.pdf "$OUT/MedVoice-diagrammalar.pdf"

# Kod yoki sirli narsa tasodifan tushib qolmasin.
if find "$OUT" \( -name '*.py' -o -name '*.js' -o -name '*.json' -o -name '.env*' -o -name '*.md' \) | grep -q .; then
  echo "XATO: dist/site ichida kod yoki sozlama fayli bor:" >&2
  find "$OUT" \( -name '*.py' -o -name '*.js' -o -name '*.json' -o -name '.env*' -o -name '*.md' \) >&2
  exit 1
fi
echo "dist/site tayyor: $(find "$OUT" -type f | wc -l | tr -d ' ') fayl, $(du -sh "$OUT" | cut -f1)"
