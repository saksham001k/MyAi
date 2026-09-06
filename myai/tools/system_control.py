"""Safe local diagnostics and command execution tools."""
import os
import platform
import shlex
import subprocess
import re

try:
    import psutil
except ImportError:  # Optional until the tools are used.
    psutil = None


def inspect_system(process_limit=50):
    """Return CPU, memory, disk, and active-process information."""
    if psutil is None:
        raise RuntimeError("Install psutil to use system inspection.")
    if type(process_limit) is not int or not 1 <= process_limit <= 500:
        raise ValueError("process_limit must be between 1 and 500")
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(os.getcwd())
    processes = []
    for process in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent"]):
        try:
            processes.append(process.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    processes.sort(key=lambda item: item.get("cpu_percent") or 0, reverse=True)
    return {
        "platform": platform.platform(),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "cpu_count": psutil.cpu_count(),
        "memory": {
            "total": memory.total,
            "available": memory.available,
            "used": memory.used,
            "percent": memory.percent,
        },
        "disk": {
            "total": disk.total,
            "free": disk.free,
            "used": disk.used,
            "percent": disk.percent,
        },
        "processes": processes[:process_limit],
    }


class ConfirmationRequired(PermissionError):
    """Raised before a potentially destructive command runs."""


class CatastrophicCommand(PermissionError):
    """Raised for commands that must never be executed by the local agent."""


_CATASTROPHIC_PATTERNS = (
    r"(^|[\s;&|])rm\s+(-[^\s]*[rf][^\s]*\s+)*(/\s*$|/\*|--no-preserve-root)",
    r"(^|[\s;&|])(?:mkfs(?:\.[\w-]+)?|format(?:\.com)?)(?:\s|$)",
    r"(^|[\s;&|])(?:diskpart|fdisk|parted)(?:\s|$)",
    r"(^|[\s;&|])(?:dd\s+[^;\n]*\bof=/dev/(?:sd[a-z]|nvme\d+n\d+)|wipefs)(?:\s|$)",
)
_NETWORK_COMMANDS = {
    "curl", "wget", "nc", "netcat", "ssh", "scp", "sftp", "telnet",
    "ftp", "http", "httpie", "aria2c",
}


def is_catastrophic(command_or_action):
    """Return True when an action matches an absolute no-execution blacklist."""
    text = command_or_action if isinstance(command_or_action, str) else " ".join(command_or_action)
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in _CATASTROPHIC_PATTERNS)


def classify_risk(command_or_action):
    """Classify a command as LOW, MEDIUM, or HIGH risk."""
    text = command_or_action if isinstance(command_or_action, str) else " ".join(command_or_action)
    high = (
        r"\brm\s+-[^\n]*r", r"\b(del|rmdir)\b", r"\b(format|mkfs)\b",
        r"\b(kill|pkill|taskkill|shutdown|reboot)\b", r"\b(sudo|chmod\s+777)\b",
        r"\b(reg(\.exe)?|setx)\b", r"\b(export|set)\s+(PATH|Path)\b",
    )
    medium = (r"\bmv\b", r"\bcp\b", r"\btouch\b", r"\bmkdir\b", r"\bwrite\b")
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in high):
        return "HIGH"
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in medium):
        return "MEDIUM"
    return "LOW"


def classify_command(command):
    """Backward-compatible high-risk predicate used by the existing server."""
    return "high" if classify_risk(command) == "HIGH" else "normal"


def require_approval(command_or_action, approved=False):
    """Raise unless a high-risk action has explicit approval."""
    if is_catastrophic(command_or_action):
        raise CatastrophicCommand("Command blocked by the catastrophic-command safety policy.")
    if classify_risk(command_or_action) == "HIGH" and approved is not True:
        raise ConfirmationRequired(
            "Confirmation required for a high-risk command."
        )


def is_network_command(command_or_action):
    args = shlex.split(command_or_action) if isinstance(command_or_action, str) else list(command_or_action)
    executable = os.path.basename(args[0]).lower() if args else ""
    text = " ".join(args)
    return executable in _NETWORK_COMMANDS or bool(
        re.search(r"\bgit\s+(?:clone|fetch|pull|push|remote|submodule)\b", text, re.IGNORECASE)
    )


def execute_command(command, timeout=30, confirm=False, force=False,
                    confirmation_token=None):
    """Run one executable with arguments, never through a shell."""
    if not isinstance(command, (str, list, tuple)):
        raise TypeError("command must be a string or an argument sequence")
    if type(timeout) not in (int, float) or not 0 < timeout <= 30:
        raise ValueError("timeout must be between 0 and 30 seconds")
    args = shlex.split(command) if isinstance(command, str) else list(command)
    if not args or any(not isinstance(arg, str) or not arg for arg in args):
        raise ValueError("command must contain a non-empty executable")
    require_approval(args, approved=confirm)
    if is_network_command(args) and not (
        force is True or confirmation_token == "KISS-CONFIRMED"
    ):
        raise ConfirmationRequired(
            "Network commands require force=True or the KISS-CONFIRMED token."
        )
    try:
        completed = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": None,
            "stdout": (exc.stdout or ""),
            "stderr": (exc.stderr or "") + "\nCommand timed out.",
        }
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
