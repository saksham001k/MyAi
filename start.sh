#!/bin/sh
set -e
cd "$(dirname "$0")"
if [ -x "./MyAi" ]; then
  exec ./MyAi
fi
exec python3 run.py
