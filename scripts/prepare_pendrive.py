#!/usr/bin/env python3
"""Download the portable bundle and copy models/data to a NEW destination."""
import argparse
import json
import os
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from myai.storage import Store
from scripts.setup_mac import download, extract


def populate(source, destination):
    models = source / "models"
    if not models.is_dir() or not any(models.rglob("*.gguf")):
        raise ValueError("No downloaded GGUF models found in the source workspace")
    workspace = destination / "Workspace"
    shutil.copytree(models, workspace / "models", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("*.part", ".gitkeep"))
    if (source / "data/myai.sqlite3").is_file():
        (workspace / "data").mkdir(parents=True, exist_ok=True)
        Store(source / "data").backup(workspace / "data/myai.sqlite3")
    if (source / "data/creations").is_dir():
        shutil.copytree(source / "data/creations", workspace / "data/creations")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True, help="NEW folder, e.g. /Volumes/DRIVE/MyAi")
    parser.add_argument("--source", type=Path, default=ROOT)
    args = parser.parse_args()
    destination = args.destination.expanduser().resolve()
    source = args.source.expanduser().resolve()
    if destination.exists():
        raise ValueError("Destination already exists. Use a new folder; existing files are never overwritten.")
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("The destination must be separate from the source workspace")
    if not destination.parent.is_dir():
        raise ValueError("Destination parent does not exist. Check the pendrive is mounted.")
    print("MyAi must be closed before preparation. The source workspace will be kept.", flush=True)
    req = urllib.request.Request("https://api.github.com/repos/saksham001k/MyAi/releases?per_page=20", headers={"User-Agent": "MyAi-portable-setup"})
    with urllib.request.urlopen(req, timeout=30) as response:
        releases = json.load(response)
    matches = [(r, a) for r in releases if not r["draft"] and r["tag_name"].startswith("portable-")
               for a in r["assets"] if a["name"] == "MyAi-Portable.zip" and (a.get("digest") or "").startswith("sha256:")]
    if not matches:
        raise ValueError("No verified portable bundle published yet. Nothing was copied.")
    release, asset = matches[0]
    if not asset["browser_download_url"].startswith("https://github.com/saksham001k/MyAi/releases/download/"):
        raise ValueError("Unexpected bundle publisher")
    required = sum(p.stat().st_size for p in (source / "models").rglob("*") if p.is_file())
    required += sum(p.stat().st_size for p in (source / "data/creations").rglob("*") if p.is_file())
    if shutil.disk_usage(destination.parent).free < required + 4 * 1024 ** 3:
        raise ValueError("Not enough space: allow all models plus 4 GiB for apps/runtimes")
    archive = source / "data/downloads" / (release["tag_name"] + ".zip")
    download(asset["browser_download_url"], archive, asset["digest"].split(":", 1)[1])
    with tempfile.TemporaryDirectory(prefix=".myai-copy-", dir=destination.parent) as tmp:
        stage = Path(tmp) / "MyAi"
        extract(archive, stage)
        for tag in ("darwin-arm64", "windows-x86_64", "linux-x86_64"):
            if not (stage / "Apps" / tag).is_dir() or not (stage / "Workspace/runtime" / tag / "runtime.json").is_file():
                raise ValueError("Portable bundle is missing a platform")
        print("Copying models and saved data. This may take several minutes…", flush=True)
        populate(source, stage)
        os.rename(stage, destination)
    print(f"Prepared: {destination}\nUse Start-Mac.command, Start-Windows.bat, or Start-Linux.sh.\nClose MyAi before ejecting. Physical-drive operation remains unverified.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.exit(f"Preparation stopped: {exc}")
