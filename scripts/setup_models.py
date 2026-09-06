#!/usr/bin/env python3
"""Install optional coding/image/video model packs, with publisher hash verification."""
import argparse
import json
import os
import platform
import re
import shlex
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.setup_mac import ROOT, download, extract

PACKS = {
    "code-small": [("Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF", "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf", "")],
    "code": [("Qwen/Qwen2.5-Coder-3B-Instruct-GGUF", "qwen2.5-coder-3b-instruct-q4_k_m.gguf", "")],
    "image": [("stable-diffusion-v1-5/stable-diffusion-v1-5", "v1-5-pruned-emaonly.safetensors", "images/")],
    "image-xl": [("stabilityai/stable-diffusion-xl-base-1.0", "sd_xl_base_1.0.safetensors", "images/")],
    "video": [
        ("Comfy-Org/Wan_2.1_ComfyUI_repackaged", "split_files/diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors", "video/"),
        ("Comfy-Org/Wan_2.1_ComfyUI_repackaged", "split_files/vae/wan_2.1_vae.safetensors", "video/"),
        ("city96/umt5-xxl-encoder-gguf", "umt5-xxl-encoder-Q4_K_M.gguf", "video/")],
}


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "MyAi-model-setup/0.2"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def model_asset(repo, filename):
    info = fetch_json(f"https://huggingface.co/api/models/{repo}?blobs=true")
    matches = [s for s in info["siblings"] if s["rfilename"].lower() == filename.lower()]
    if len(matches) != 1:
        raise ValueError(f"Publisher file changed or unavailable: {repo}/{filename}")
    item = matches[0]
    digest = item.get("lfs", {}).get("sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Publisher SHA-256 unavailable; download refused")
    revision = info["sha"]
    url = f"https://huggingface.co/{repo}/resolve/{revision}/" + urllib.parse.quote(item["rfilename"], safe="/")
    return url, digest, item.get("size", item.get("lfs", {}).get("size", 0))


def install_diffusion():
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("Automatic diffusion runtime setup currently requires Apple Silicon macOS")
    folder = ROOT / "runtime/darwin-arm64"
    if (folder / "sd-cli").is_file():
        return
    releases = fetch_json("https://api.github.com/repos/leejet/stable-diffusion.cpp/releases?per_page=20")
    assets = [a for r in releases if not r.get("draft") for a in r.get("assets", [])
              if re.search(r"(macos|darwin|osx)", a["name"], re.I)
              and re.search(r"(arm64|aarch64)", a["name"], re.I)
              and a["name"].endswith((".zip", ".tar.gz"))
              and (a.get("digest") or "").startswith("sha256:")]
    if not assets:
        raise ValueError("No verified Apple Silicon diffusion binary available upstream. Model downloads can still run without --runtime; runtime installation remains pending.")
    asset = assets[0]
    url = asset["browser_download_url"]
    if not url.startswith("https://github.com/leejet/stable-diffusion.cpp/releases/download/"):
        raise ValueError("Unexpected runtime publisher")
    archive = ROOT / "data/downloads" / Path(asset["name"]).name
    download(url, archive, asset["digest"].split(":", 1)[1])
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / "diffusion-vendor"
    if destination.exists():
        raise ValueError("An incomplete diffusion runtime exists; preserved for inspection")
    with tempfile.TemporaryDirectory(dir=folder) as tmp:
        stage = Path(tmp) / "vendor"
        extract(archive, stage)
        servers = [p for p in stage.rglob("sd-cli") if p.is_file() and not p.is_symlink()]
        if len(servers) != 1:
            raise ValueError("The runtime archive does not contain one sd-cli")
        relative = servers[0].relative_to(stage).as_posix()
        servers[0].chmod(0o755)
        os.replace(stage, destination)
    launcher = folder / "sd-cli"
    launcher.write_text('#!/bin/sh\nBASE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\nexec "$BASE"/' + shlex.quote("diffusion-vendor/" + relative) + ' "$@"\n')
    launcher.chmod(0o755)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packs", nargs="+", choices=PACKS)
    parser.add_argument("--runtime", action="store_true", help="Also install a verified Apple Silicon diffusion runtime")
    args = parser.parse_args()
    (ROOT / "data").mkdir(exist_ok=True)
    lock = ROOT / "data" / "setup.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        if args.runtime:
            install_diffusion()
        for pack in dict.fromkeys(args.packs):
            for repo, filename, subdir in PACKS[pack]:
                print(f"Preparing {repo}/{filename}", flush=True)
                url, digest, size = model_asset(repo, filename)
                destination = ROOT / "models" / subdir / Path(filename).name
                if not destination.exists() and shutil.disk_usage(ROOT).free < size + 1024 ** 3:
                    raise ValueError("Not enough free disk space for this model")
                download(url, destination, digest)
        print("Selected model packs installed. Restart MyAi or refresh its model list.")
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.exit(f"Setup stopped: {exc}")
