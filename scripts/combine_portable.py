"""Combine three verified platform parts into one model-free pendrive bundle."""
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.setup_mac import extract
from scripts.package_portable import zip_tree


def main():
    target = ROOT / "dist" / "MyAi-Portable"
    target.mkdir(parents=True)
    for tag in ("darwin-arm64", "windows-x86_64", "linux-x86_64"):
        matches = list((ROOT / "incoming").rglob(f"MyAi-{tag}.zip"))
        if len(matches) != 1:
            raise RuntimeError(f"Missing or duplicate platform part: {tag}")
        extract(matches[0], target)
    for source in (ROOT / "portable").iterdir():
        shutil.copy2(source, target / source.name)
        if source.suffix in (".command", ".sh"):
            (target / source.name).chmod(0o755)
    shutil.copytree(ROOT / "docs", target / "docs")
    shutil.copy2(ROOT / "LICENSE", target / "LICENSE")
    shutil.copytree(ROOT / "third_party", target / "third_party")
    (target / "Workspace/models").mkdir(parents=True)
    (target / "Workspace/data").mkdir(parents=True)
    (target / "README.txt").write_text("MyAi portable bundle. Models are not included. Use prepare_pendrive.py to copy your downloaded models and conversations. See docs/PENDRIVE.md.\n")
    archive = ROOT / "dist/MyAi-Portable.zip"
    zip_tree(target, archive)
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            digest.update(chunk)
    (ROOT / "dist/SHA256SUMS.txt").write_text(digest.hexdigest() + "  MyAi-Portable.zip\n")


if __name__ == "__main__":
    main()
