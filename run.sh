#!/usr/bin/env bash
# Quick launcher for Telegram High-Speed Downloader (Flutter + Python FastAPI)
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

# 1. Classic Terminal CLI mode
if [[ "$1" == "--cli" || "$1" == "-c" || "$1" == "--channel" || "$1" == "--logout" ]]; then
    if [[ "$1" == "--cli" ]]; then
        shift
    fi
    python3 main.py "$@"
    exit 0
fi

# 2. Native Flutter GUI mode (Desktop or connected device)
if [[ "$1" == "--flutter" || "$1" == "--app" ]]; then
    shift
    echo "Starting Native Flutter App..."
    cd frontend && flutter run "$@"
    exit 0
fi

# 3. Default / Mobile / Web Server Mode
PORT=8000
lsof -ti:$PORT | xargs kill -9 2>/dev/null || true

LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "127.0.0.1")
URL="http://${LOCAL_IP}:${PORT}"

echo ""
echo "======================================================="
echo "⚡ TELEGRAM HIGH-SPEED DOWNLOADER (FLUTTER + FASTAPI)"
echo "======================================================="
echo "👉 Open on your Phone, Tablet or PC:"
echo "   $URL"
echo ""

# Generate ASCII terminal QR code for convenient mobile phone scanning
python3 -c "
import qrcode
qr = qrcode.QRCode(border=1)
qr.add_data('$URL')
qr.make(fit=True)
qr.print_ascii(invert=True)
" 2>/dev/null || true

echo "📷 Point your phone's camera at this QR code to open!"
echo "======================================================="
echo ""

python3 server.py
