"""Portable host hardware detection for llama.cpp runtime settings."""
from shutil import which
import ctypes
import os
import platform
import subprocess
from typing import NamedTuple


class HardwareInfo(NamedTuple):
    backend: str
    gpu_layers: int
    threads: int


class MemoryInfo(NamedTuple):
    total_mb: int | None
    available_mb: int | None
    vram_mb: int | None
    source: str


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


def _linux_memory():
    info = {}
    try:
        for line in _read_meminfo().splitlines():
            key, raw = line.split(":", 1)
            parts = raw.strip().split()
            if parts and parts[0].isdigit():
                info[key] = int(parts[0])
    except OSError:
        return None, None, "unavailable"
    total = info.get("MemTotal")
    available = info.get("MemAvailable", info.get("MemFree"))
    if total is None:
        return None, None, "unavailable"
    return total // 1024, (available // 1024 if available is not None else None), "/proc/meminfo"


def _read_meminfo():
    with open("/proc/meminfo", encoding="ascii", errors="ignore") as stream:
        return stream.read()


def _darwin_memory():
    total_raw = _command_output(["sysctl", "-n", "hw.memsize"])
    try:
        total_mb = int(total_raw) // (1024 * 1024)
    except ValueError:
        return None, None, "unavailable"
    vm = _command_output(["vm_stat"])
    page_bytes = 4096
    pages = {}
    for line in vm.splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        digits = "".join(ch for ch in raw if ch.isdigit())
        if digits:
            pages[key.strip()] = int(digits)
        if "page size of" in line.lower():
            size_digits = "".join(ch for ch in line if ch.isdigit())
            if size_digits:
                page_bytes = int(size_digits)
    free = pages.get("Pages free", 0) + pages.get("Pages speculative", 0) + pages.get("Pages purgeable", 0)
    available_mb = (free * page_bytes) // (1024 * 1024) if free else None
    return total_mb, available_mb, "sysctl/vm_stat"


def _windows_memory():
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    try:
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None, None, "unavailable"
    except (AttributeError, OSError):
        return None, None, "unavailable"
    return (status.ullTotalPhys // (1024 * 1024),
            status.ullAvailPhys // (1024 * 1024),
            "GlobalMemoryStatusEx")


def memory_snapshot():
    """Return total/available RAM in MiB. Missing fields stay null instead of guessed."""
    system = platform.system().lower()
    vram = _nvidia_vram_mb() or None
    if system == "linux":
        total, available, source = _linux_memory()
    elif system == "darwin":
        total, available, source = _darwin_memory()
    elif system == "windows":
        total, available, source = _windows_memory()
    else:
        total, available, source = None, None, "unavailable"
    if system == "darwin" and platform.machine().lower() in {"arm64", "aarch64"}:
        # Unified memory: VRAM is not a separate pool we can query here.
        vram = total
        source = source + "+unified"
    return MemoryInfo(total, available, vram, source)


def recommend_context(available_mb, model_bytes, backend="cpu"):
    """Pick a context window that is likely to fit. Returns None if unknown/too tight.

    Formula (documented estimate, not a guarantee):
    usable = available RAM minus 2 GiB OS reserve (or 25% if RAM < 8 GiB)
    leftover = usable - 1.25 * model file size
    context needs leftover >= 256 MiB per 2048 tokens (CPU) or 128 MiB (GPU).
    """
    if not available_mb or available_mb < 0 or not model_bytes:
        return None
    reserve = 2048 if available_mb >= 8192 else max(512, available_mb // 4)
    usable = available_mb - reserve
    model_mb = model_bytes / (1024 * 1024)
    leftover = usable - model_mb * 1.25
    per_2k = 128 if backend in {"metal", "cuda", "vulkan"} else 256
    if leftover < per_2k:
        return None
    for ctx in (16384, 8192, 4096, 2048):
        if leftover >= per_2k * (ctx / 2048):
            return ctx
    return 2048


def recommend_model(models, memory=None, hardware=None):
    """Choose the smallest catalog model that appears to fit available RAM."""
    memory = memory or memory_snapshot()
    hardware = hardware or detect_hardware()
    available = memory.available_mb or memory.total_mb
    if not available:
        return {
            "model_id": None,
            "context": None,
            "reason": "Available memory could not be measured on this computer.",
        }
    ranked = sorted(
        (m for m in models if m.get("size_bytes_approx") or m.get("installed_bytes")),
        key=lambda m: m.get("installed_bytes") or m.get("size_bytes_approx") or 10**18,
    )
    for item in ranked:
        size = item.get("installed_bytes") or item.get("size_bytes_approx")
        context = recommend_context(available, size, hardware.backend)
        min_ram = int(item.get("min_ram_gb") or 0) * 1024
        if context is None:
            continue
        if min_ram and (memory.total_mb or available) < min_ram:
            continue
        return {
            "model_id": item.get("id"),
            "filename": item.get("filename"),
            "context": min(context, int(item.get("recommended_context") or context)),
            "gpu_layers": hardware.gpu_layers,
            "backend": hardware.backend,
            "reason": (
                f"Conservative fit for ~{available} MiB available RAM using "
                "file-size * 1.25 plus KV-cache headroom. Not a quality ranking."
            ),
        }
    return {
        "model_id": None,
        "context": 2048,
        "gpu_layers": 0,
        "backend": "cpu",
        "reason": (
            f"No catalog model looks safe for ~{available} MiB available RAM. "
            "Use a smaller GGUF or close other programs."
        ),
    }
