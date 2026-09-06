"""Workspace and command policy for autonomous build/test repair."""
from __future__ import annotations

import re
import shlex
from pathlib import Path

SAFE = "SAFE"
DESTRUCTIVE = "DESTRUCTIVE"

_DENY = (
    r"\brm\s+-[^\n]*r", r"\b(?:mkfs|format|fdisk|diskpart|parted)\b",
    r"\bgit\s+(?:push|reset)\b[^\n]*--force", r"\b(?:shutdown|reboot|killall|pkill)\b",
    r"(?:^|[\s\"'=])/(?:etc|usr|var|System)(?:/|$)",
    r"\b(?:curl|wget|nc|netcat|ssh|scp)\b",
)


class GuardrailError(PermissionError):
    pass


def classify_command(command):
    text = command if isinstance(command, str) else " ".join(command)
    return DESTRUCTIVE if any(re.search(pattern, text, re.I) for pattern in _DENY) else SAFE


def validate_workspace_path(workspace_root, target):
    root = Path(workspace_root).resolve()
    path = Path(target)
    resolved = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not resolved.is_relative_to(root):
        raise GuardrailError("File path is outside the active project workspace.")
    return resolved


def require_confirmation(command, require_confirmation=True, confirmed=False):
    if require_confirmation and classify_command(command) == DESTRUCTIVE and not confirmed:
        raise GuardrailError("Destructive command requires explicit confirmation.")
    return True


def command_args(command):
    args = shlex.split(command) if isinstance(command, str) else list(command)
    if not args:
        raise ValueError("Command cannot be empty.")
    return args
