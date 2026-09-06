"""CI: assemble one native app plus pinned inference runtimes into a part ZIP."""
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from myai.engine import platform_tag
from scripts.setup_mac import download, extract


def zip_tree(source, destination):
    """Dereference file symlinks for exFAT; retain Unix mode metadata in ZIP."""
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source))


def main():
    tag = platform_tag()
    sources = json.loads((ROOT / "runtimes.lock.json").read_text())[tag]
    part = ROOT / "dist" / "portable-part"
    apps = part / "Apps" / tag
    shutil.copytree(ROOT / "dist/MyAi", apps)
    runtime = part / "Workspace/runtime" / tag
    runtime.mkdir(parents=True)
    mapping = {}
    for source in sources:
        cache = ROOT / "build/downloads" / source["name"]
        download(source["url"], cache, source["sha256"])
        vendor = runtime / source["executable"].split(".")[0]
        extract(cache, vendor)
        matches = [p for p in vendor.rglob(source["executable"]) if p.is_file() and not p.is_symlink()]
        if len(matches) != 1:
            raise RuntimeError(f"Expected one {source['executable']} in archive")
        binary = matches[0]
        binary.chmod(0o755)
        mapping[source["executable"]] = binary.relative_to(runtime).as_posix()
        # Verify native loading and shared-library resolution; no AI model required.
        subprocess.run([str(binary), "--help"], cwd=binary.parent, check=True,
                       stdout=subprocess.DEVNULL, timeout=60)
    (runtime / "runtime.json").write_text(json.dumps(mapping, indent=2))
    (runtime / "sources.json").write_text(json.dumps(sources, indent=2))
    # Check the frozen application against the same shared-workspace layout.
    subprocess.run([sys.executable, str(ROOT / "scripts/smoke_package.py"),
                    str(apps / ("MyAi.exe" if sys.platform == "win32" else "MyAi"))], check=True)
    zip_tree(part, ROOT / "dist" / f"MyAi-{tag}.zip")
    print(f"Packaged and smoke-tested {tag}")


if __name__ == "__main__":
    main()
