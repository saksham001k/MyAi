#!/bin/sh
set -eu
BASE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ "$(uname -m)" != x86_64 ]; then
  echo "This build needs x86_64 Linux."
  exit 1
fi
exec "$BASE/Apps/linux-x86_64/MyAi" --root "$BASE/Workspace" "$@"
