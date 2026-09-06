#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ -x "./MyAi" ]; then
  exec ./MyAi
fi
if command -v python3 >/dev/null 2>&1; then
  exec python3 run.py
fi
echo "Python 3.10+ is required for this source checkout. Use a packaged build to run without Python."
read -r -p "Press Enter to close."
