#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT"

OS="$(uname -s)"
ARCH="$(uname -m)"
case "$OS" in
  Darwin) OS_TAG="darwin" ;;
  Linux) OS_TAG="linux" ;;
  *) echo "Unsupported POSIX operating system: $OS" >&2; exit 1 ;;
esac
case "$ARCH" in
  x86_64|amd64) ARCH_TAG="x64" ;;
  arm64|aarch64) ARCH_TAG="arm64" ;;
  *) echo "Unsupported CPU architecture: $ARCH" >&2; exit 1 ;;
esac

RUNTIME_BIN="runtime/${OS_TAG}-${ARCH_TAG}/llama-server"
if [ -f "$RUNTIME_BIN" ]; then chmod +x "$RUNTIME_BIN"; fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 run.py "$@"
elif command -v node >/dev/null 2>&1 && [ -f "dist/cli.js" ]; then
  exec node dist/cli.js "$@"
else
  echo "Error: Python 3 or Node.js is required." >&2
  exit 1
fi
