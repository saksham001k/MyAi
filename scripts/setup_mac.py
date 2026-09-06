#!/usr/bin/env python3
"""Prepare an Apple Silicon MyAi workspace, then launch it. Python 3.10+."""
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MODEL = "Qwen3-4B-Q4_K_M.gguf"
MODEL_SHA = "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"
MODEL_URL = "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/" + MODEL
RELEASES = "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=20"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def download(url, path, digest):
    """Resume interrupted downloads, but never accept an unverified result."""
    path = Path(path)
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Download has no valid publisher SHA-256")
    if not url.startswith("https://"):
        raise ValueError("Downloads require HTTPS")
    if path.exists():
        if path.is_file() and sha256(path) == digest:
            print(f"Already verified: {path.name}", flush=True)
            return
        raise ValueError(f"Existing file does not match: {path}. It was not overwritten.")
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    subprocess.run(["curl", "--fail", "--location", "--proto", "=https", "--proto-redir", "=https",
                    "--retry", "3", "--connect-timeout", "30", "--continue-at", "-",
                    "--output", str(partial), url], check=True)
    if sha256(partial) != digest:
        partial.unlink()
        raise ValueError(f"Checksum failed for {path.name}. Run setup again to download a fresh copy.")
    os.replace(partial, path)


def choose_asset(releases):
    for release in releases:
        if release.get("draft"):
            continue
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if ("macos-arm64" in name and name.endswith((".tar.gz", ".zip"))
                    and (asset.get("digest") or "").startswith("sha256:")
                    and asset.get("browser_download_url", "").startswith(
                        "https://github.com/ggml-org/llama.cpp/releases/download/")):
                return release["tag_name"], asset
    raise ValueError("No checksummed macOS ARM64 runtime found in official releases. No files changed; share this message.")


def safe_path(root, name):
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name:
        raise ValueError("Unsafe archive path")
    target = root.joinpath(*relative.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Archive path escapes destination")
    return target


def extract(archive, root):
    """Extract regular files/directories and confined symlinks, never device files."""
    root.mkdir(parents=True, exist_ok=True)
    links = []
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            for item in bundle.infolist():
                target = safe_path(root, item.filename)
                mode = item.external_attr >> 16
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                elif mode & 0o170000 == 0o120000:
                    links.append((target, bundle.read(item).decode()))
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(item) as src, target.open("xb") as dst:
                        shutil.copyfileobj(src, dst)
                    target.chmod(0o755 if mode & 0o111 else 0o644)
    else:
        with tarfile.open(archive) as bundle:
            for item in bundle:
                target = safe_path(root, item.name)
                if item.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif item.issym():
                    links.append((target, item.linkname))
                elif item.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.extractfile(item) as src, target.open("xb") as dst:
                        shutil.copyfileobj(src, dst)
                    target.chmod(0o755 if item.mode & 0o111 else 0o644)
                else:
                    raise ValueError("Unsupported archive entry; installation stopped")
    # Create symlinks only after file writes and validate every final target.
    for target, link in links:
        if Path(link).is_absolute() or not (target.parent / link).resolve().is_relative_to(root.resolve()):
            raise ValueError("Unsafe archive symlink")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(link)
    for target, _ in links:
        if not target.resolve().is_relative_to(root.resolve()):
            raise ValueError("Unsafe archive symlink chain")


def install_runtime(root):
    destination = root / "runtime" / "darwin-arm64"
    if destination.exists():
        if (destination / "llama-server").is_file():
            print("Keeping the existing runtime.", flush=True)
            return
        if any(destination.iterdir()):
            raise ValueError(f"Runtime folder is incomplete: {destination}. Existing files were preserved.")
        destination.rmdir()
    request = urllib.request.Request(RELEASES, headers={"User-Agent": "MyAi-setup/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        tag, asset = choose_asset(json.load(response))
    print(f"Downloading official llama.cpp runtime: {tag}", flush=True)
    cache = root / "data" / "downloads"
    archive = cache / Path(asset["name"]).name
    download(asset["browser_download_url"], archive, asset["digest"].split(":", 1)[1])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".myai-setup-", dir=destination.parent) as tmp:
        stage = Path(tmp) / "installed"
        extract(archive, stage / "vendor")
        servers = [p for p in (stage / "vendor").rglob("llama-server") if p.is_file() and not p.is_symlink()]
        if len(servers) != 1:
            raise ValueError("Expected one llama-server executable in the downloaded runtime")
        servers[0].chmod(0o755)
        relative = servers[0].relative_to(stage).as_posix()
        wrapper = stage / "llama-server"
        wrapper.write_text('#!/bin/sh\nBASE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\nexec "$BASE"/' + shlex.quote(relative) + ' "$@"\n')
        wrapper.chmod(0o755)
        (stage / "source.json").write_text(json.dumps({"release": tag, "asset": asset["name"], "sha256": asset["digest"]}, indent=2))
        os.replace(stage, destination)


def main():
    if sys.version_info < (3, 10):
        raise ValueError("Python 3.10 or newer is required. Share this message for the next step.")
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("Run this setup in a native Terminal on your Apple Silicon Mac.")
    if shutil.which("curl") is None:
        raise ValueError("curl is unavailable on this computer")
    if shutil.disk_usage(ROOT).free < 7 * 1024 ** 3:
        raise ValueError("Keep at least 7 GiB free before setup.")
    (ROOT / "data").mkdir(exist_ok=True)
    # Prevent simultaneous setup runs from writing the same partial files.
    lock = ROOT / "data" / "setup.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("Another setup may be running. If it was interrupted, close it and remove data/setup.lock before retrying.") from None
    os.close(fd)
    try:
        install_runtime(ROOT)
        print("Checking the runtime on this Mac…", flush=True)
        subprocess.run([str(ROOT / "runtime/darwin-arm64/llama-server"), "--version"], check=True, timeout=30)
        print("Downloading Qwen3-4B Q4_K_M (about 2.5 GB); interrupted downloads can resume.", flush=True)
        download(MODEL_URL, ROOT / "models" / MODEL, MODEL_SHA)
    finally:
        lock.unlink(missing_ok=True)
    print("Setup complete. In MyAi, choose Qwen3-4B, 4096 context, GPU, then Load model. Keep this terminal open.", flush=True)
    os.execv(sys.executable, [sys.executable, str(ROOT / "run.py")])


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        sys.exit(f"Setup stopped: {exc}\nShare this message so we can fix the exact problem.")
