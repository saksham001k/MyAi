"""Add portable directories, documentation and launchers to the app build."""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
destination = root / "dist" / "MyAi"
for name in ("data", "models", "runtime"):
    (destination / name).mkdir(parents=True, exist_ok=True)
    (destination / name / "PLACE_FILES_HERE.txt").write_text(
        f"MyAi {name} directory. See docs/SETUP.md.\n", encoding="utf-8")
for name in ("README.md", "LICENSE", "Start-MyAi.command", "Start-MyAi.bat", "start.sh"):
    shutil.copy2(root / name, destination / name)
shutil.copytree(root / "docs", destination / "docs", dirs_exist_ok=True)
