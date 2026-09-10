#!/usr/bin/env python3
"""Short, repeatable local commands that need no AI session."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['start', 'check', 'test'])
    args, extra = p.parse_known_args()
    root = Path(__file__).resolve().parents[1]
    python = root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    executable = str(python) if python.exists() else sys.executable
    commands = {'start': ['run.py'], 'check': ['scripts/doctor.py'], 'test': ['-m', 'unittest', 'discover', '-s', 'tests', '-v']}
    return subprocess.call([executable, *commands[args.action], *extra], cwd=root)


if __name__ == '__main__':
    raise SystemExit(main())
