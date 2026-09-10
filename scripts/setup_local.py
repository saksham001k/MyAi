#!/usr/bin/env python3
"""Install local app dependencies; no account, API key or model download."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', action='store_true', help='Also install optional Playwright Chromium')
    parser.add_argument('--developer', action='store_true', help='Also install/build the optional TypeScript worker (needs npm)')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    target = root / '.venv'
    if sys.version_info < (3, 10):
        raise SystemExit('Python 3.10+ is required.')
    python = target / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(target)
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(root / 'requirements.txt')], check=True)
    if args.browser:
        subprocess.run([str(python), '-m', 'pip', 'install', 'playwright>=1.40,<2'], check=True)
        subprocess.run([str(python), '-m', 'playwright', 'install', 'chromium'], check=True)
    if args.developer:
        npm = 'npm.cmd' if os.name == 'nt' else 'npm'
        subprocess.run([npm, 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], cwd=root, check=True)
        subprocess.run([npm, 'run', 'build'], cwd=root, check=True)
    print('\nSetup complete. No model weights downloaded and no paid service configured.')
    print('Start: python3 scripts/local.py start')
    print('Check: python3 scripts/local.py check')


if __name__ == '__main__':
    main()
