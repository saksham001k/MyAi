"""Bounded child-process execution with strict local safety policy."""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import signal
import time
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
        args = shlex.split(command)
    else:
        args = list(command)
    if not args or any(not isinstance(item, str) or not item for item in args):
        raise ValueError("command must contain a non-empty executable")
    return args


def _process_command(command: str | Sequence[str]) -> list[str]:
    if not isinstance(command, str):
        return _arguments(command)
    if os.name == "nt":
        return [os.environ.get("ComSpec", "cmd.exe"), "/d", "/s", "/c", command]
    return ["/bin/sh", "-c", command]


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
        process_args = _process_command(request.command)
        cwd = request.cwd.resolve()
        if not cwd.is_relative_to(self.root):
            raise ValueError("Sandbox working directory must be inside the workspace.")
        ensure_policy(request, args)
        env = {"PATH": os.environ.get("PATH", "")}
        if request.env:
            env.update({str(key): str(value) for key, value in request.env.items()})
        try:
            completed = subprocess.run(
                process_args, cwd=cwd, env=env, shell=False, capture_output=True,
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


def parse_traceback(stderr: str) -> list[dict]:
    """Extract common Python and JS/TS failure locations from process output."""
    pattern = re.compile(
        r'(?:(?:File\s+["\']([^"\']+)["\'],\s+line\s+(\d+))|'
        r'((?:[A-Za-z]:[\\/]|/|\.{0,2}[\\/])?[^()\s"\']+\.(?:py|js|jsx|ts|tsx)):(\d+)(?::(\d+))?)'
    )
    lines = stderr.splitlines()
    results = []
    for index, line in enumerate(lines):
        match = pattern.search(line)
        if not match:
            continue
        file_path = match.group(1) or match.group(3)
        line_number = int(match.group(2) or match.group(4))
        results.append({
            "file": file_path,
            "line": line_number,
            "column": int(match.group(5)) if match.group(5) else None,
            "message": line.strip(),
            "context": "\n".join(lines[index:index + 3]),
        })
    return results


class ExecutionSandbox:
    """Run local build/test commands with hard timeouts and captured output."""

    def __init__(self, workspace_root, timeout=15):
        self.workspace_root = Path(workspace_root).resolve()
        self.timeout = timeout
        if timeout <= 0:
            raise ValueError("timeout must be positive")

    def run(self, command, timeout=None, cwd=None, env=None):
        args = _arguments(command)
        process_args = _process_command(command)
        working = (Path(cwd) if cwd else self.workspace_root).resolve()
        if not working.is_relative_to(self.workspace_root):
            raise ValueError("Working directory must be inside the project workspace.")
        ensure_policy(ExecutionRequest(args, working, timeout or self.timeout), args)
        started = time.monotonic()
        process = subprocess.Popen(
            process_args, cwd=working, env={**{"PATH": os.environ.get("PATH", "")}, **(env or {})},
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, shell=False,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout or self.timeout)
        except subprocess.TimeoutExpired as exc:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/pid", str(process.pid), "/f", "/t"],
                    capture_output=True, check=False,
                )
            else:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
            stdout, stderr = process.communicate()
            stdout = stdout or (exc.stdout or "")
            stderr = (stderr or (exc.stderr or "")) + "\nCommand timed out."
            return {
                "command": tuple(args), "exit_code": None, "stdout": stdout,
                "stderr": stderr, "timed_out": True,
                "duration": time.monotonic() - started, "traceback": parse_traceback(stderr),
            }
        return {
            "command": tuple(args), "exit_code": process.returncode, "stdout": stdout,
            "stderr": stderr, "timed_out": False,
            "duration": time.monotonic() - started, "traceback": parse_traceback(stderr),
        }
