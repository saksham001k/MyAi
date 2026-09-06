"""Portable host hardware detection for llama.cpp runtime settings."""
from shutil import which
import os
import platform
import subprocess
from typing import NamedTuple


class HardwareInfo(NamedTuple):
    backend: str
    gpu_layers: int
    threads: int


def _command_output(command):
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()


def _nvidia_vram_mb():
    if not which("nvidia-smi"):
        return 0
    output = _command_output(["nvidia-smi", "--query-gpu=memory.total",
                              "--format=csv,noheader,nounits"])
    values = []
    for line in output.splitlines():
        try:
            values.append(int(float(line.strip())))
        except ValueError:
            continue
    return max(values, default=0)


def _gpu_layers_from_vram(vram_mb):
    # A conservative estimate that leaves room for the OS and llama.cpp buffers.
    return max(1, min(999, vram_mb // 256))


def detect_hardware():
    """Return the best available backend and llama.cpp runtime settings."""
    cpu_threads = max(1, os.cpu_count() or 1)
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return HardwareInfo("metal", 999, max(1, cpu_threads - 1))

    vram_mb = _nvidia_vram_mb()
    if vram_mb:
        return HardwareInfo("cuda", _gpu_layers_from_vram(vram_mb),
                            max(1, cpu_threads - 1))

    if which("vulkaninfo") and _command_output(["vulkaninfo", "--summary"]):
        return HardwareInfo("vulkan", 999, max(1, cpu_threads - 1))

    return HardwareInfo("cpu", 0, cpu_threads)
