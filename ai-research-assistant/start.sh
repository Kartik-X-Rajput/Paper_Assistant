#!/usr/bin/env bash
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then exec python3 run.py; fi
echo "Python 3.10+ is required: https://www.python.org/downloads/"; read -r -p "Press Enter to close"
