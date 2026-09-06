#!/bin/sh
set -eu
BASE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ "$(uname -m)" != arm64 ]; then
  echo "This build needs an Apple Silicon Mac."
  exit 1
fi
exec "$BASE/Apps/darwin-arm64/MyAi" --root "$BASE/Workspace" "$@"
