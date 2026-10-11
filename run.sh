#!/usr/bin/env bash
# Quick launcher for the terminal-only Telegram downloader
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

# The terminal distribution has one entry point. No UI server or framework is
# installed or launched from this checkout.
if [[ "$1" == "--cli" ]]; then
    shift
fi
python3 main.py "$@"
