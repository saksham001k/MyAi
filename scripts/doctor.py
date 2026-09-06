#!/usr/bin/env python3
"""Check a workspace before attempting real inference or a pendrive test."""
import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from myai.engine import Engine, platform_tag


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    engine = Engine(root)
    checks = [("Python 3.10+", sys.version_info >= (3, 10)),
              ("Workspace writable", os.access(root, os.W_OK)),
              (f"Runtime for {platform_tag()}", engine.binary.is_file()),
              ("Runtime executable", engine.binary.is_file() and os.access(engine.binary, os.X_OK)),
              ("At least one GGUF model", bool(engine.models()))]
    for label, ok in checks:
        print(f"{'PASS' if ok else 'MISSING'}  {label}")
    print(f"Free storage: {shutil.disk_usage(root).free / 1024 ** 3:.1f} GiB")
    print("These checks do not verify model compatibility, available RAM, GPU drivers, or inference quality.")
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
