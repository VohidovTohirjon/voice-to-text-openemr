#!/usr/bin/env bash
# Hosted site: the overview page for the manager plus the live demo.
#
#   /            overview: results, diagrams, deck
#   /demo/       the encounter form with the voice panel, no extension needed
#   /api/asr     speech endpoint (functions/api/asr.js, built by wrangler)
#
# Output goes to dist/site (not in git).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

OUT=dist/site
rm -rf "$OUT"; mkdir -p "$OUT/assets" "$OUT/demo" "$OUT/py"

# overview
cp site/index.html site/_headers site/robots.txt "$OUT/"
cp docs/diagrams/[1-6]-*.png docs/diagrams/ekran-*.png "$OUT/assets/"
cp docs/OpenEMR-ovozli-yozuv.pptx "$OUT/MedVoice-taqdimot.pptx"
cp docs/diagrams/arxitektura-diagrammalar.pdf "$OUT/MedVoice-diagrammalar.pdf"

# live demo: the same panel the Chrome extension injects, plus the in-browser engine
cp web/demo.html "$OUT/demo/index.html"
cp web/demo.js web/engine.js web/engine-worker.js "$OUT/"
cp extension/scanner.js extension/content.js "$OUT/"
python3 -I scripts/build-nlp-bundle.py "$OUT/py/nlp-bundle.json"

# Only the files the hosted app needs may ship. Anything else (service code,
# tests, env files, notes) fails the build instead of going public.
ALLOWED='^\./(index\.html|_headers|robots\.txt|demo\.js|engine\.js|engine-worker\.js|scanner\.js|content\.js|MedVoice-taqdimot\.pptx|MedVoice-diagrammalar\.pdf|demo/index\.html|py/nlp-bundle\.json|assets/[^/]+\.png)$'
unexpected="$(cd "$OUT" && find . -type f | grep -Ev "$ALLOWED" || true)"
if [[ -n "$unexpected" ]]; then
  echo "XATO: dist/site ichida kutilmagan fayllar bor:" >&2
  echo "$unexpected" >&2
  exit 1
fi
# Look for an actual credential (a key block, or a name assigned a long literal),
# not for the bare word "password" that the form scanner uses to skip such fields.
SECRET='BEGIN ([A-Z]+ )?PRIVATE KEY|(api[_-]?key|secret|token|passwd|password)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"']{8,}'
if grep -rIn -E "$SECRET" "$OUT" --include='*.js' --include='*.html' --include='*.json' >&2; then
  echo "XATO: sirga o'xshash matn topildi." >&2
  exit 1
fi
echo "dist/site tayyor: $(find "$OUT" -type f | wc -l | tr -d ' ') fayl, $(du -sh "$OUT" | cut -f1)"
