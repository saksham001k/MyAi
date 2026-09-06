"""Cross-platform OS, architecture, and bundled runtime resolution."""
from __future__ import annotations

import os
import platform
from pathlib import Path


def detect_platform() -> dict[str, str]:
    system = platform.system().lower()
    current_os = "windows" if system == "windows" else "macos" if system == "darwin" else "linux"
    arch = "arm64" if platform.machine().lower() in {"arm64", "aarch64"} else "x64"
    return {
        "os": current_os,
        "arch": arch,
        "runtime_tag": f"{'win' if current_os == 'windows' else 'darwin' if current_os == 'macos' else 'linux'}-{arch}",
        "executable": "llama-server.exe" if current_os == "windows" else "llama-server",
    }


def resolve_runtime_binary(root: str | Path, binary: str = "llama-server") -> Path:
    info = detect_platform()
    name = info["executable"] if binary == "llama-server" else binary
    return Path(root).resolve() / "runtime" / info["runtime_tag"] / name


def paths_equal(left: str | Path, right: str | Path) -> bool:
    a, b = Path(left).resolve(), Path(right).resolve()
    return os.path.normcase(a) == os.path.normcase(b)
