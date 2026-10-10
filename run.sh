#!/usr/bin/env bash
# Quick launcher for Telegram High-Speed Downloader Pro
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

# If CLI argument or terminal flags are supplied, run terminal main.py
if [[ "$1" == "--cli" || "$1" == "-c" || "$1" == "--channel" || "$1" == "--logout" ]]; then
    if [[ "$1" == "--cli" ]]; then
        shift
    fi
    python3 main.py "$@"
else
    python3 app.py "$@"
fi
