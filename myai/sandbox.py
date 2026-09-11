"""Bounded child-process execution with strict local safety policy."""
from __future__ import annotations

import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from .tools.system_control import is_catastrophic


class SandboxPolicyError(PermissionError):
    """Raised when an execution request violates the sandbox policy."""


@dataclass(frozen=True)
class ExecutionRequest:
    command: str | Sequence[str]
    cwd: Path
    timeout: float = 30.0
    env: Mapping[str, str] | None = None
    force: bool = False
    confirmation_token: str | None = None


@dataclass(frozen=True)
class ExecutionResult:
    command: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    duration_seconds: float = 0.0
    traceback: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


_NETWORK_COMMANDS = {
    "curl", "wget", "nc", "netcat", "ssh", "scp", "sftp", "telnet",
    "ftp", "http", "httpie", "aria2c",
}
_NETWORK_GIT_ACTIONS = re.compile(r"\bgit\s+(?:clone|fetch|pull|push|remote|submodule)\b", re.I)
_APPROVAL_TOKEN = "KISS-CONFIRMED"


def _arguments(command: str | Sequence[str]) -> list[str]:
    if isinstance(command, str):
        args = shlex.split(command, posix=(os.name != "nt"))
    else:
        args = list(command)
    if not args or any(not isinstance(item, str) or not item for item in args):
        raise ValueError("command must contain a non-empty executable")
    return args


def is_network_command(args: Sequence[str]) -> bool:
    executable = Path(args[0]).name.lower()
    return executable in _NETWORK_COMMANDS or bool(_NETWORK_GIT_ACTIONS.search(" ".join(args)))


def ensure_policy(request: ExecutionRequest, args: Sequence[str]) -> None:
    if not request.cwd.is_dir():
        raise ValueError("Sandbox working directory does not exist.")
    if request.timeout <= 0 or request.timeout > 300:
        raise ValueError("Sandbox timeout must be between 0 and 300 seconds.")
    if is_catastrophic(args):
        raise SandboxPolicyError("Catastrophic command blocked by the absolute sandbox blacklist.")
    if is_network_command(args) and not (
        request.force or request.confirmation_token == _APPROVAL_TOKEN
    ):
        raise SandboxPolicyError(
            "Network command blocked; only KISS-CONFIRMED or force may authorize it."
        )


class SandboxRunner:
    """Run allow-listed child processes with bounded I/O and inherited-safe env."""

    def __init__(self, root: Path, default_timeout: float = 30.0):
        self.root = root.resolve()
        self.default_timeout = default_timeout

    def run(self, request: ExecutionRequest | str | Sequence[str]) -> ExecutionResult:
        if not isinstance(request, ExecutionRequest):
            request = ExecutionRequest(request, self.root, self.default_timeout)
        args = _arguments(request.command)
        cwd = request.cwd.resolve()
        if not cwd.is_relative_to(self.root):
            raise ValueError("Sandbox working directory must be inside the workspace.")
        ensure_policy(request, args)
        env = {"PATH": os.environ.get("PATH", "")}
        if os.name == "nt":
            for key in ("SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "PATHEXT", "COMSPEC", "TEMP", "TMP"):
                if key in os.environ:
                    env[key] = os.environ[key]
        if request.env:
            env.update({str(key): str(value) for key, value in request.env.items()})
        try:
            completed = subprocess.run(
                args, cwd=cwd, env=env, shell=False, capture_output=True,
                text=True, timeout=request.timeout, check=False,
            )
            return ExecutionResult(tuple(args), completed.returncode,
                                   completed.stdout, completed.stderr)
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = (exc.stderr or "") + "\nCommand timed out."
            return ExecutionResult(tuple(args), None, stdout, stderr, timed_out=True)
        except OSError as exc:
            return ExecutionResult(tuple(args), None, "", str(exc), traceback=str(exc))
