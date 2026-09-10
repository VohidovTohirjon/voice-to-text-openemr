#!/usr/bin/env bash
#
# Demoni bir buyruq bilan ko'taradi.
#
#   ./run.sh          xizmatni ishga tushiradi, Whisper'ni qizdiradi, extension'ni yig'adi
#   ./run.sh stop     xizmatni to'xtatadi
#   ./run.sh status   holatni ko'rsatadi
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

PORT="${ASR_PORT:-8000}"
LOG="/tmp/openemr-asr.log"
PIDFILE="/tmp/openemr-asr.pid"

g() { printf '\033[32m%s\033[0m\n' "$*"; }
y() { printf '\033[33m%s\033[0m\n' "$*"; }
r() { printf '\033[31m%s\033[0m\n' "$*"; }
b() { printf '\033[1m%s\033[0m\n' "$*"; }
step() { printf '\033[36m▸\033[0m %s\n' "$*"; }

port_pid() { lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -1; }

# ---------------------------------------------------------------- stop / status
if [[ "${1:-}" == "stop" ]]; then
  pid="$(port_pid "$PORT")"
  if [[ -z "$pid" ]]; then y "Port $PORT da hech narsa ishlamayapti."; exit 0; fi
  if [[ -f "$PIDFILE" && "$(cat "$PIDFILE")" == "$pid" ]]; then
    kill "$pid" 2>/dev/null
    # Haqiqatan o'lishini kutamiz: aks holda keyingi `stop` uni port ustida
    # topib, o'zimizniki emas deb o'ylaydi va to'xtatishdan bosh tortadi.
    for _ in $(seq 1 20); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.25
    done
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null; sleep 0.5
    fi
    rm -f "$PIDFILE"
    g "To'xtatildi (PID $pid)."
  else
    r "Port $PORT da BOSHQA jarayon turibdi — men uni to'xtatmayman:"
    ps -p "$pid" -o pid,command | tail -1
  fi
  exit 0
fi

if [[ "${1:-}" == "status" ]]; then
  pid="$(port_pid "$PORT")"
  if [[ -z "$pid" ]]; then y "Xizmat ishlamayapti."; exit 1; fi
  ps -p "$pid" -o pid,command | tail -1
  curl -s "http://127.0.0.1:$PORT/" || r "  javob bermayapti"
  echo
  exit 0
fi

# ---------------------------------------------------------------------- 1. port
b "OpenEMR Voice Capture — demoni ko'taryapman"
echo

step "Port $PORT tekshirilyapti"
pid="$(port_pid "$PORT")"
if [[ -n "$pid" ]]; then
  cmd="$(ps -p "$pid" -o command= | head -1)"
  if [[ "$cmd" == *"api:app"* ]]; then
    g "  Bizning xizmat allaqachon ishlayapti (PID $pid) — qayta ishlatilyapti."
    ALREADY=1
  else
    r "  Port $PORT band, va bu BOSHQA loyiha:"
    echo "     PID $pid  ${cmd:0:96}"
    echo
    y "  Avtomatik to'xtatmayman. Ikki yo'l bor:"
    echo "     1) O'sha jarayonni o'zingiz to'xtating:   kill $pid"
    echo "     2) Boshqa portda ishga tushiring:         ASR_PORT=8100 ./run.sh"
    echo
    y "     Eslatma: kengaytma 8000 ni kutadi. Boshqa port ishlatsangiz,"
    y "     validatsiya sahifasini ?api=http://127.0.0.1:8100 bilan oching."
    exit 1
  fi
fi

# ------------------------------------------------------------------- 2. talablar
if [[ -z "${ALREADY:-}" ]]; then
  step "Python paketlari tekshirilyapti"
  missing="$(python3 - <<'PY'
import importlib
need = {"fastapi":"fastapi","uvicorn":"uvicorn","whisper":"openai-whisper",
        "multipart":"python-multipart"}
print(" ".join(pkg for mod,pkg in need.items()
                if not importlib.util.find_spec(mod)))
PY
)"
  if [[ -n "$missing" ]]; then
    y "  Yetishmayapti: $missing"
    step "  O'rnatilyapti..."
    python3 -m pip install --quiet $missing || { r "  O'rnatib bo'lmadi."; exit 1; }
  fi
  g "  Hammasi joyida."

  # ----------------------------------------------------------------- 3. xizmat
  step "Xizmat ko'tarilyapti (port $PORT)"
  # Uchala fd ham yopiladi va jarayon disown qilinadi. Aks holda server
  # ota-skriptning quvurini ushlab qoladi va `./run.sh | tail` qaytmaydi.
  # disown ishlashi uchun bu subshellda emas, asosiy shellda bajarilishi shart.
  pushd asr >/dev/null
  nohup python3 -m uvicorn api:app --host 127.0.0.1 --port "$PORT" \
      >"$LOG" 2>&1 </dev/null &
  SERVER_PID=$!
  disown "$SERVER_PID" 2>/dev/null || true
  popd >/dev/null
  echo "$SERVER_PID" >"$PIDFILE"

  for i in $(seq 1 40); do
    sleep 0.5
    curl -sf -o /dev/null "http://127.0.0.1:$PORT/" && break
    if [[ $i -eq 40 ]]; then
      r "  Ko'tarilmadi. Log: $LOG"; tail -15 "$LOG"; exit 1
    fi
  done
  g "  Tayyor: http://127.0.0.1:$PORT"
fi

# -------------------------------------------------------------- 4. qatlamlar
step "Qaysi qatlamlar tirik"
CAPS="$(curl -s "http://127.0.0.1:$PORT/capabilities")"
printf '%s' "$CAPS" | python3 -c '
import json, sys
d = json.load(sys.stdin)
for k, v in d["layers"].items():
    mark = "\033[32m ok \033[0m" if v["available"] else "\033[33myo\x27q\033[0m"
    print("  [%s] %-20s %s" % (mark, k, v["kind"]))
w = d["whisper"]
print("  [ \033[32mok\033[0m ] %-20s model %s" % ("whisper", w["model"]))
'                 

# ---------------------------------------------------------- 5. Whisper qizdirish
step "Whisper qizdirilyapti (birinchi so'rov sekin — demoda kutmaslik uchun)"
WARM=$(mktemp -t asrwarm).wav
if command -v say >/dev/null && command -v ffmpeg >/dev/null; then
  say -o "${WARM%.wav}.aiff" "Patient reports headache and mild fever for two days." 2>/dev/null
  ffmpeg -y -loglevel error -i "${WARM%.wav}.aiff" -ar 16000 -ac 1 "$WARM" 2>/dev/null
  if [[ -s "$WARM" ]]; then
    t0=$(python3 -c 'import time;print(time.time())')
    out=$(curl -s -X POST "http://127.0.0.1:$PORT/transcribe" -F "file=@$WARM" \
          | python3 -c 'import json,sys; print(json.load(sys.stdin)["transcription"][:60])' 2>/dev/null)
    t1=$(python3 -c 'import time;print(time.time())')
    if [[ -n "$out" ]]; then
      g "  Model xotirada ($(python3 -c "print(f'{$t1-$t0:.1f}')") s): \"$out\""
    else
      y "  Transkripsiya javob bermadi — demoda 'Demo text' tugmasidan foydalaning."
    fi
  fi
  rm -f "$WARM" "${WARM%.wav}.aiff"
else
  y "  say/ffmpeg yo'q — qizdirish o'tkazib yuborildi."
fi

# ------------------------------------------------------------- 6. extension
step "Kengaytma yig'ilyapti"
if npm run build --silent >/dev/null 2>&1; then
  g "  dist/extension tayyor"
else
  r "  Yig'ilmadi — 'npm run build' ni qo'lda ishlating."
fi

# ------------------------------------------------------------------ keyingi qadam
echo
b "Tayyor. Endi:"
echo
echo "  1. Chrome → chrome://extensions → Developer Mode"
echo "  2. 'Load unpacked' → $(pwd)/dist/extension"
echo "  3. OpenEMR encounter sahifasini oching"
echo
echo "  OpenEMR'siz sinash uchun (boshqa terminalda):"
echo "     python3 -m http.server 5180"
echo "     http://127.0.0.1:5180/validation/forms/encounter-soap-vitals.html"
[[ "$PORT" != "8000" ]] && echo "     ...?api=http://127.0.0.1:$PORT"
echo
echo "  Diagrammalar:  open docs/diagrams/"
echo "  Ssenariy:      docs/video-shooting-script-uz.md"
echo "  Log:           tail -f $LOG"
echo "  To'xtatish:    ./run.sh stop"
echo
